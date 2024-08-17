import machine
from machine import ADC, Pin, freq
import utime
import uasyncio
import gc
import micropython
from managers.led_manager import LEDManager

class SystemManager:
    def __init__(self, config):
        self.client_name = config.MQTT_CLIENT_NAME
        self.ADC_PINS = config.ADC_PINS_TO_MONITOR if hasattr(config, 'ADC_PINS_TO_MONITOR') else []
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

    def set_led(self, led):
        self.led_manager = LEDManager(led)

    async def run(self):
        while True:
            self.update_status()
            await uasyncio.sleep_ms(100)

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
            print(f"Error reading ADC pin {adc_pin}: {e}")
            return 0

    def check_system(self):
        try:
            temp_sensor = machine.ADC(4)
            reading = temp_sensor.read_u16() * (3.3 / 65535)
            temperature = 27 - (reading - 0.706) / 0.001721
            return machine.ADC(29).read_u16() * (3.3 / 65535), temperature
        except Exception as e:
            print(f"Error reading system data: {e}")
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
            print(f"Warning: High memory usage ({ram_usage:.2%}). Performing garbage collection.")
            gc.collect()
        
        if cpu_usage > self.cpu_usage_threshold:
            print(f"Warning: High CPU usage ({cpu_usage:.2%}). Consider optimizing or reducing workload.")
        
        return cpu_usage, ram_usage

    def get_system_data(self):
        self.update_system_data()
        cpu_usage, ram_usage = self.check_resources()
        timestamp = utime.time()

        mqtt_data = {
            "system": {
                "internal_voltage": round(self.internal_voltage, 2),
                "chip_temperature": round(self.chip_temperature, 2),
                "cpu_frequency": self.cpu_freq,
                "cpu_usage": round(cpu_usage * 100, 2),
                "ram_usage": round(ram_usage * 100, 2),
                "timestamp": timestamp,
                "uptime": self.get_uptime_string()
            },
            "adc": {f"adc_{pin}": round(self.adc_readings.get(f"adc_{pin}", 0), 2) for pin in self.ADC_PINS}
        }

        influx_data = [
            {
                "measurement": "system_metrics",
                "tags": {"device": self.client_name},
                "fields": {
                    "internal_voltage": mqtt_data["system"]["internal_voltage"],
                    "chip_temperature": mqtt_data["system"]["chip_temperature"],
                    "cpu_frequency": mqtt_data["system"]["cpu_frequency"],
                    "cpu_usage": mqtt_data["system"]["cpu_usage"],
                    "ram_usage": mqtt_data["system"]["ram_usage"]
                },
                "timestamp": timestamp
            }
        ]

        influx_data.extend([
            {
                "measurement": "adc_readings",
                "tags": {"device": self.client_name, "pin": pin},
                "fields": {"voltage": voltage},
                "timestamp": timestamp
            } for pin, voltage in mqtt_data["adc"].items()
        ])

        return mqtt_data, influx_data

    def print_system_data(self):
        mqtt_data, influx_data = self.get_system_data()
        print("System Data:")
        for category, values in mqtt_data.items():
            print(f"  {category}:")
            for key, value in values.items():
                print(f"    {key}: {value}")
        print("---")
        