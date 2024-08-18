import math
import utime

class DataManager:
    def __init__(self, config):
        self.config = config

    def correct_temperature_reading(self, temperature):
        return temperature - self.config.TEMPERATURE_OFFSET

    def correct_humidity_reading(self, humidity, temperature, corrected_temperature):
        dewpoint = temperature - ((100 - humidity) / 5)
        corrected_humidity = max(0, min(100, 100 - (5 * (corrected_temperature - dewpoint))))
        return corrected_humidity

    def adjust_to_sea_pressure(self, pressure, temperature, altitude):
        pressure_hpa = pressure / 100
        adjusted_hpa = pressure_hpa + ((pressure_hpa * 9.80665 * altitude) / (287 * (273 + temperature + (altitude / 400))))
        return adjusted_hpa
    
    def adjust_lux_for_growhouse(self, lux):
        # Increase sensitivity for low light conditions
        return lux * 2 if lux < 50 else lux

    def interpret_gas_reading(self, gas):
        # Interpret gas reading for air quality
        if gas < 10000:
            return "Poor"
        elif 10000 <= gas < 30000:
            return "Fair"
        elif 30000 <= gas < 50000:
            return "Good"
        else:
            return "Excellent"
    
    def adjust_cpu_frequency(self, cpu_frequency):
        return cpu_frequency / 1000000
    
    def interpret_mic_reading(self, mic):
        # Normalize the mic reading to a 0-1 range
        # Assuming the mic reading ranges from 30000 to 36000 based on observed values
        normalized = (mic - 30000) / (36000 - 30000)
        
        # Convert to a dB-like scale from 0 to 60
        # This gives us a range of values that might be more intuitive
        db_like = 60 * normalized
    
        return round(db_like, 1)
    
    def describe_light(self, lux):
        if lux < self.config.LIGHT_THRESHOLD_VERY_LOW:
            return "Very Low"
        elif lux < self.config.LIGHT_THRESHOLD_LOW:
            return "Low"
        elif lux < self.config.LIGHT_THRESHOLD_MODERATE:
            return "Moderate"
        elif lux < self.config.LIGHT_THRESHOLD_GOOD:
            return "Good"
        else:
            return "Bright"

    def describe_growhouse_environment(self, temperature, humidity, lux):
        env_status = "Optimal"
        issues = []

        if temperature < 20 or temperature > 30:
            issues.append("Temperature")
            env_status = "Suboptimal"
        if humidity < 50 or humidity > 90:
            issues.append("Humidity")
            env_status = "Suboptimal"

        # Check light conditions
        current_time = utime.localtime()
        current_hour = current_time[3]  # Hour is at index 3 in the time tuple

        start_hour = self.config.LIGHT_SCHEDULE_START_HOUR
        end_hour = self.config.LIGHT_SCHEDULE_END_HOUR

        # Determine if it's daytime based on the schedule
        is_daytime = False
        if start_hour < end_hour:
            # Simple case: start time is before end time
            is_daytime = start_hour <= current_hour < end_hour
        else:
            # Complex case: schedule spans midnight
            is_daytime = current_hour >= start_hour or current_hour < end_hour

        if is_daytime:
            light_status = self.describe_light(lux)
            if lux < self.config.LIGHT_THRESHOLD_LOW:
                issues.append(f"Light ({light_status})")
                env_status = "Suboptimal"
        else:
            light_status = "Night time"

        return env_status, issues, light_status

    def prepare_mqtt_sensor_data_for_publishing(self, m5_watering_unit_data, enviro_plus_data, system_data):
        try:
            mqtt_data, _ = system_data  # Unpack the tuple, ignore the InfluxDB data
            data = {
                "m5-watering-unit": m5_watering_unit_data,
                "enviro-plus": enviro_plus_data,
                "system": mqtt_data["system"],
                "adc": mqtt_data["adc"]
            }
            return data
        except Exception as e:
            print(f"Error in prepare_mqtt_sensor_data_for_publishing: {e}")
            return None
