import math
import utime
import ntptime
import machine

class DataManager:
    def __init__(self, config, log_mgr, system_mgr):
        self.config = config
        self.log_manager = log_mgr
        self.system_mgr = system_mgr
        self.moving_averages = {}
        self.window_size = self.config.SENSOR_DATA_AVG_WINDOW_SIZE

    def correct_temperature_reading(self, temperature):
        return round(temperature - self.config.TEMPERATURE_OFFSET, 2)

    def correct_humidity_reading(self, humidity, temperature, corrected_temperature):
        dewpoint = temperature - ((100 - humidity) / 5)
        corrected_humidity = max(0, min(100, 100 - (5 * (corrected_temperature - dewpoint))))
        return round(corrected_humidity - self.config.HUMIDITY_OFFSET, 2)

    def adjust_to_sea_pressure(self, pressure, temperature, altitude):
        pressure_hpa = pressure / 100
        adjusted_hpa = pressure_hpa + ((pressure_hpa * 9.80665 * altitude) / (287 * (273 + temperature + (altitude / 400))))
        return round(adjusted_hpa, 2)
    
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
        # Define the range of the microphone input
        MIC_MIN = self.config.MIC_MIN_VALUE  # Adjusted based on your silent readings
        MIC_MAX = self.config.MIC_MAX_VALUE  # Assuming 16-bit ADC

        # Define the desired dB range
        DB_MIN = 10  # Lowest reading (very quiet room)
        DB_MAX = 110  # Highest reading (very loud)

        # Normalize the mic reading to a 0-1 range
        normalized_mic = max(0, min(1, (self.filter_spike("mic", mic) - MIC_MIN) / (MIC_MAX - MIC_MIN)))

        # Convert to logarithmic dB scale
        # Using a modified formula to give more realistic values
        if normalized_mic > 0:
            db_value = DB_MIN + (DB_MAX - DB_MIN) * (math.log10(1 + 9 * normalized_mic) / math.log10(10))
        else:
            db_value = DB_MIN

        # Ensure the value is within the expected range
        return round(max(DB_MIN, min(DB_MAX, db_value)), 1)
    
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

        current_hour = self.system_mgr.get_local_hour()
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
    

    def filter_spike(self, sensor_name, value):
        if sensor_name not in self.moving_averages:
            self.moving_averages[sensor_name] = []

        history = self.moving_averages[sensor_name]
        
        if len(history) < self.window_size:
            history.append(value)
            return value
        
        avg = sum(history) / len(history)
        deviation = abs(value - avg)
        
        # Define threshold as a percentage of the average
        threshold = 0.5 * avg  # 50% deviation threshold, adjust as needed
        
        if deviation > threshold:
            self.log_manager.log(f"Spike detected in {sensor_name}: {value}. Using average: {avg}")
            filtered_value = avg
        else:
            filtered_value = value
        
        history.append(filtered_value)
        if len(history) > self.window_size:
            history.pop(0)
        
        return filtered_value

    def prepare_mqtt_sensor_data_for_publishing(self, m5_watering_unit_data, dfr_moisture_sensor_data, enviro_plus_data, system_data, current_config_data):
        try:
            mqtt_data = system_data
            # Convert last_watered to Europe/Berlin timezone
            if 'last_watered' in m5_watering_unit_data:
                    last_watered_time = utime.localtime(int(m5_watering_unit_data['last_watered']) + (self.config.DST_HOURS * 3600))
                    formatted_time = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                        last_watered_time[0], last_watered_time[1], last_watered_time[2],
                        last_watered_time[3], last_watered_time[4], last_watered_time[5]
                    )
                    m5_watering_unit_data['last_watered'] = formatted_time
            data = {
                "m5-watering-unit": m5_watering_unit_data,
                "dfr-moisture-sensor": dfr_moisture_sensor_data,
                "enviro-plus": enviro_plus_data,
                "system": mqtt_data["system"],
                "adc": mqtt_data["adc"],
                "current_config": current_config_data
            }
            return data
        except Exception as e:
            print(f"Error in prepare_mqtt_sensor_data_for_publishing: {e}")
            return None
