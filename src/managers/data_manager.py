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
        offset = getattr(self.config, "TEMPERATURE_OFFSET", 0)
        return round(temperature - offset, 2)

    def correct_humidity_reading(self, humidity, temperature, corrected_temperature):
        dewpoint = temperature - ((100 - humidity) / 5)
        corrected_humidity = max(0, min(100, 100 - (5 * (corrected_temperature - dewpoint))))
        offset = getattr(self.config, "HUMIDITY_OFFSET", 0)
        return round(corrected_humidity - offset, 2)

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
        MIC_MIN = getattr(self.config, "MIC_MIN_VALUE", 30000)  # Adjusted based on your silent readings
        MIC_MAX = getattr(self.config, "MIC_MAX_VALUE", 65535)  # Assuming 16-bit ADC

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
        very_low = getattr(self.config, "LIGHT_THRESHOLD_VERY_LOW", 50)
        low = getattr(self.config, "LIGHT_THRESHOLD_LOW", 200)
        moderate = getattr(self.config, "LIGHT_THRESHOLD_MODERATE", 400)
        good = getattr(self.config, "LIGHT_THRESHOLD_GOOD", 600)

        if lux < very_low:
            return "Very Low"
        elif lux < low:
            return "Low"
        elif lux < moderate:
            return "Moderate"
        elif lux < good:
            return "Good"
        else:
            return "Bright"

    def describe_humidity(self, humidity):
        if humidity < 30:
            return "Dry"
        elif humidity < 60:
            return "OK"
        else:
            return "Humid"

    def calculate_dew_point(self, temperature_c, humidity):
        try:
            if humidity <= 0:
                return None
            a = 17.62
            b = 243.12
            gamma = (a * temperature_c / (b + temperature_c)) + math.log(humidity / 100.0)
            dew_point = (b * gamma) / (a - gamma)
            return round(dew_point, 1)
        except Exception:
            return None

    def calculate_vpd(self, temperature_c, humidity):
        try:
            if humidity <= 0:
                return None
            # Saturation vapor pressure (kPa)
            svp = 0.6108 * math.exp((17.27 * temperature_c) / (temperature_c + 237.3))
            vpd = svp * (1 - (humidity / 100.0))
            return round(vpd, 2)
        except Exception:
            return None

    def describe_vpd(self, vpd_kpa):
        if vpd_kpa is None:
            return "N/A"
        vpd_min = getattr(self.config, "VPD_TARGET_MIN", 0.8)
        vpd_max = getattr(self.config, "VPD_TARGET_MAX", 1.2)
        if vpd_kpa < vpd_min:
            return "Low"
        if vpd_kpa > vpd_max:
            return "High"
        return "OK"

    def describe_sound(self, db_value):
        if db_value < 30:
            return "Quiet"
        elif db_value < 60:
            return "Normal"
        elif db_value < 85:
            return "Loud"
        else:
            return "Very Loud"


    def filter_spike(self, sensor_name, value):
        if sensor_name not in self.moving_averages:
            self.moving_averages[sensor_name] = []

        history = self.moving_averages[sensor_name]
        
        if len(history) < self.window_size:
            history.append(value)
            return value
        
        avg = sum(history) / len(history)
        deviation = abs(value - avg)
        
        # Define threshold as a percentage of the average (with floor)
        min_threshold = getattr(self.config, "SENSOR_SPIKE_MIN_THRESHOLD", 1)
        threshold = max(min_threshold, 0.5 * abs(avg))  # 50% deviation threshold

        if deviation > threshold:
            filtered_value = avg
        else:
            filtered_value = value
        
        history.append(filtered_value)
        if len(history) > self.window_size:
            history.pop(0)
        
        return filtered_value
    
    def convert_epoch(self, epoch_value):
        try:
            dst_hours = getattr(self.config, "DST_HOURS", 0)
            time_value = utime.localtime(int(epoch_value) + (dst_hours * 3600))
            return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                time_value[0], time_value[1], time_value[2],
                time_value[3], time_value[4], time_value[5]
            )
        except Exception:
            return epoch_value

    def prepare_mqtt_sensor_data_for_publishing(self, enviro_plus_data, system_data, current_config_data):
        try:
            mqtt_data = system_data
            data = {
                "enviro-plus": enviro_plus_data,
                "system": mqtt_data["system"],
                "adc": mqtt_data["adc"],
                "current_config": current_config_data
            }
            return data
        except Exception as e:
            print(f"Error in prepare_mqtt_sensor_data_for_publishing: {e}")
            return None
