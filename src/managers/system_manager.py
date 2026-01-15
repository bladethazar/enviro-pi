import machine
from machine import ADC, Pin, freq
import utime
import ntptime
import uasyncio
import gc
import micropython
from managers.led_manager import LEDManager

class SystemManager:
    def __init__(self, config, log_mgr, data_mgr):
        self.config = config
        self.wdt = machine.WDT(timeout=8000)  # 8 second timeout
        self.last_wdt_feed = utime.ticks_ms()
        self.wdt_feed_interval = 1000 
        self.client_name = self.config.MQTT_CLIENT_NAME
        self.log_mgr = log_mgr
        self.data_mgr = data_mgr
        self.ADC_PINS = self.config.ADC_PINS_TO_MONITOR if hasattr(self.config, 'ADC_PINS_TO_MONITOR') else []
        self.adc_readings = {}
        self.internal_voltage = 0
        self.chip_temperature = 0
        self.cpu_freq = freq()
        self.last_time = utime.ticks_ms()
        self.last_run_time = 0
        self.start_time = utime.ticks_ms()
        self.uptime = 0
        self.mem_alloc_threshold = 0.9  # 90% memory allocation threshold
        self.cpu_usage_threshold = 0.8  # 80% CPU usage threshold
        self.status = "RUNNING"
        self.led_manager = None
        self.processing_tasks = set()
        self.errors = set()
        dst_hours = getattr(self.config, "DST_HOURS", 0)
        self.time_offset = dst_hours * 3600

  
    def feed_watchdog(self):
        current_time = utime.ticks_ms()
        if utime.ticks_diff(current_time, self.last_wdt_feed) >= self.wdt_feed_interval:
            self.wdt.feed()
            self.last_wdt_feed = current_time


    def sync_time(self, max_retries=5):
        for i in range(max_retries):
            try:
                ntptime.settime()
                return True
            except Exception as e:
                self.log_mgr.log(f"Error synchronizing time (attempt {i+1}/{max_retries}): {str(e)}")
                utime.sleep(1)
        
        self.set_time_from_compile()
        return False


    def set_time_from_compile(self):
        compile_time = utime.localtime()
        machine.RTC().datetime((compile_time[0], compile_time[1], compile_time[2], compile_time[6], compile_time[3], compile_time[4], compile_time[5], 0))
        self.log_mgr.log(f"Time set from compile time: {compile_time}")


    def get_local_time(self):
        return utime.localtime(utime.time() + self.time_offset)


    def get_local_hour(self):
        local_time = self.get_local_time()
        return local_time[3]  # Hour is at index 3 in the time tuple

    def format_time(self, time_tuple):
        return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
            time_tuple[0], time_tuple[1], time_tuple[2],
            time_tuple[3], time_tuple[4], time_tuple[5]
        )


    def set_led(self, led):
        self.led_manager = LEDManager(led)

    async def run(self):
        while True:
            self.update_status()
            self.feed_watchdog()
            await uasyncio.sleep_ms(100)

    
    def clear_memory(self):
        self.log_mgr.log("Clearing system memory")
        
        # Clear log buffer
        self.log_mgr.clear_logs()

        # Clear system manager's own caches
        self.adc_readings.clear()
        self.errors.clear()
        self.processing_tasks.clear()
        
        # Perform garbage collection
        gc.collect()
        
        self.log_mgr.log("System memory cleared")


    def restart_system(self):
        self.log_mgr.log("System restart initiated by SystemManager")
        # Perform any necessary cleanup here
        utime.sleep(1)  # Short delay to allow for cleanup
        machine.reset()  # Perform a soft reset of the system


    def update_status(self):
        if self.errors:
            new_status = "ERROR"
        elif self.processing_tasks:
            new_status = "PROCESSING"
        else:
            new_status = "RUNNING"
        
        if new_status != self.status:
            self.status = new_status
            if self.led_manager:
                self.led_manager.update_led(self.status)


    def start_processing(self, task_name):
        self.processing_tasks.add(task_name)
        self.update_status()


    def stop_processing(self, task_name):
        self.processing_tasks.discard(task_name)
        self.update_status()


    def add_error(self, error_name):
        self.errors.add(error_name)
        self.update_status()


    def clear_error(self, error_name):
        self.errors.discard(error_name)
        self.update_status()


    def get_status(self):
        return self.status

    
    def update_uptime(self):
        current_time = utime.ticks_ms()
        self.uptime = utime.ticks_diff(current_time, self.start_time)


    def get_uptime_string(self):
        seconds = self.uptime // 1000
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)
        return f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"


    def check_voltage(self, adc_pin):
        try:
            adc = ADC(Pin(adc_pin))
            raw = adc.read_u16()
            voltage = (raw * 3.3) / 65535
            return voltage
        except Exception as e:
            self.log_mgr.log(f"Error reading ADC pin {adc_pin}: {e}")
            return 0


    def check_system(self):
        try:
            temp_sensor = machine.ADC(4)
            reading = temp_sensor.read_u16() * (3.3 / 65535)
            temperature = 27 - (reading - 0.706) / 0.001721
            temperature = self.data_mgr.filter_spike("chip_temperature", temperature)
            return machine.ADC(29).read_u16() * (3.3 / 65535), temperature
        except Exception as e:
            self.log_mgr.log(f"Error reading system data: {e}")
            return 0, 0


    def update_system_data(self):
        self.internal_voltage, self.chip_temperature = self.check_system()
        self.update_uptime()
        for pin in self.ADC_PINS:
            self.adc_readings[f"adc_{pin}"] = self.check_voltage(pin)


    def estimate_cpu_usage(self):
        def busy_wait():
            start = utime.ticks_us()
            while utime.ticks_diff(utime.ticks_us(), start) < 10000:
                pass
        
        start = utime.ticks_ms()
        busy_wait()
        end = utime.ticks_ms()
        
        run_time = utime.ticks_diff(end, start)
        total_time = utime.ticks_diff(end, self.last_time)
        
        usage = (run_time / total_time) if total_time > 0 else 0
        self.last_time = end
        self.last_run_time = run_time
        
        return usage


    def get_ram_usage(self):
        gc.collect()
        free = gc.mem_free()
        alloc = gc.mem_alloc()
        total = free + alloc
        return alloc / total if total > 0 else 0


    def check_resources(self):
        cpu_usage = self.estimate_cpu_usage()
        ram_usage = self.get_ram_usage()
        
        if ram_usage > self.mem_alloc_threshold:
            self.log_mgr.log(f"Warning: High memory usage ({ram_usage:.2%}). Performing garbage collection.")
            gc.collect()
        
        if cpu_usage > self.cpu_usage_threshold:
            self.log_mgr.log(f"Warning: High CPU usage ({cpu_usage:.2%}). Consider optimizing or reducing workload.")
        
        return cpu_usage, ram_usage


    def get_system_data(self):
        self.update_system_data()
        cpu_usage, ram_usage = self.check_resources()
        timestamp = utime.time()

        mqtt_data = {
            "system": {
                "internal_voltage": round(self.internal_voltage, 2),
                "chip_temperature": round(self.chip_temperature, 2),
                "cpu_frequency": self.data_mgr.adjust_cpu_frequency(self.cpu_freq),
                "cpu_usage": round(cpu_usage * 100, 2),
                "ram_usage": round(ram_usage * 100, 2),
                "timestamp": timestamp,
                "uptime": self.get_uptime_string()
            },
            "adc": {f"adc_{pin}": round(self.adc_readings.get(f"adc_{pin}", 0), 2) for pin in self.ADC_PINS}
        }
        
        return mqtt_data


    def get_current_config_data(self):
        return {
            "temperature_offset": getattr(self.config, "TEMPERATURE_OFFSET", 0),
            "humidity_offset": getattr(self.config, "HUMIDITY_OFFSET", 0),
            "enviro_plus_display_brightness": getattr(self.config, "ENVIRO_PLUS_DISPLAY_BRIGHTNESS", 0.8),
            "mic_min_value": getattr(self.config, "MIC_MIN_VALUE", 30000),
            "mic_max_value": getattr(self.config, "MIC_MAX_VALUE", 65535),
            "mqtt_update_interval": getattr(self.config, "MQTT_UPDATE_INTERVAL", 60)
        }


    def print_system_data(self):
        mqtt_data = self.get_system_data()
        self.log_mgr.log("System Data:")
        for category, values in mqtt_data.items():
            self.log_mgr.log(f"  {category}:")
            for key, value in values.items():
                self.log_mgr.log(f"    {key}: {value}")
        self.log_mgr.log("---")
        