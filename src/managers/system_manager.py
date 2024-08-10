# system_manager.py

from machine import ADC, Pin, freq
import utime
import gc
# import micropython

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
        
    def update_uptime(self):
        current_time = utime.ticks_ms()
        self.uptime = current_time - self.start_time

    def get_uptime_seconds(self):
        return self.uptime // 1000

    def get_uptime_minutes(self):
        return self.get_uptime_seconds() // 60

    def get_uptime_hours(self):
        return self.get_uptime_minutes() // 60

    def get_uptime_days(self):
        return self.get_uptime_hours() // 24


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
            adc = ADC(4)  # Internal temperature sensor ADC
            raw = adc.read_u16()
            voltage = (raw * 3.3) / 65535
            temperature = 27 - (voltage - 0.706) / 0.001721
            return voltage, temperature
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
        
        usage = (run_time / total_time) * 100 if total_time > 0 else 0
        self.last_time = end
        self.last_run_time = run_time
        
        return usage

    def get_ram_usage(self):
        gc.collect()
        free = gc.mem_free()
        alloc = gc.mem_alloc()
        total = free + alloc
        return (alloc / total) * 100 if total > 0 else 0

    def get_system_data(self):
            self.update_system_data()
            timestamp = utime.time()

            mqtt_data = {
                "system": {
                    "internal_voltage": round(self.internal_voltage, 2),
                    "chip_temperature": round(self.chip_temperature, 2),
                    "cpu_frequency": self.cpu_freq,
                    "cpu_usage": round(self.estimate_cpu_usage(), 2),
                    "ram_usage": round(self.get_ram_usage(), 2),
                    "timestamp": timestamp,
                    "uptime": f"{self.get_uptime_days()}d [{self.get_uptime_hours()}:{self.get_uptime_minutes()}:{self.get_uptime_minutes()}]"
                },
                "adc": {}
            }

            for pin in self.ADC_PINS:
                mqtt_data["adc"][f"adc_{pin}"] = round(self.adc_readings.get(f"adc_{pin}", 0), 2)

            influx_data = [
                {
                    "measurement": "system_metrics",
                    "tags": {
                        "device": self.client_name,
                    },
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

            for pin, voltage in mqtt_data["adc"].items():
                influx_data.append({
                    "measurement": "adc_readings",
                    "tags": {
                        "device": self.client_name,
                        "pin": pin
                    },
                    "fields": {
                        "voltage": voltage
                    },
                    "timestamp": timestamp
                })

            return mqtt_data, influx_data

    def print_system_data(self):
        mqtt_data, influx_data = self.get_system_data()
        print("MQTT Data:")
        for category, values in mqtt_data.items():
            print(f"  {category}:")
            for key, value in values.items():
                print(f"    {key}: {value}")
        print("---")
        print("InfluxDB Data:")
        for point in influx_data:
            print(f"  Measurement: {point['measurement']}")
            print(f"  Tags: {point['tags']}")
            print(f"  Fields: {point['fields']}")
            print(f"  Timestamp: {point['timestamp']}")
            print("  ---")

# For standalone testing
# if __name__ == "__main__":
#     class Config:
#         ADC_PINS_TO_MONITOR = [26, 27, 28]  # Example pins, adjust as needed
    
#     system_manager = SystemManager(Config())
#     for _ in range(5):
#         system_manager.print_system_data()
#         utime.sleep(1)