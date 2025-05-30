import math
import utime
import urequests
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

    def get_weather_data_from_api(self):
        try:
            url = f"{self.config.WEATHER_API_BASE_URL}/current.json" + f"?key={self.config.WEATHER_API_TOKEN}" + f"&q={self.config.WEATHER_FOR}&aqi=yes"
            response = urequests.get(url)

            if response.status_code != 200:
                self.log_manager.log(f"Weather API error: {response.status_code}")
                response.close()
                return None

            raw = response.json()
            response.close()

            current = raw.get("current", {})
            condition = current.get("condition", {})
            airq = current.get("air_quality", {})
            location = raw.get("location", {})

            icon_url = condition.get("icon", "")
            if icon_url.startswith("//"):
                icon_url = "https:" + icon_url  # Make it a valid HTTPS URL

            weather_data = {
                "temp_c": current.get("temp_c"),
                "feelslike_c": current.get("feelslike_c"),
                "condition": condition.get("text", ""),
                "icon_url": icon_url,
                "wind_kph": current.get("wind_kph"),
                "wind_dir": current.get("wind_dir"),
                "pressure_mb": current.get("pressure_mb"),
                "humidity": current.get("humidity"),
                "uv": current.get("uv"),
                "air_quality": {
                    "pm2_5": airq.get("pm2_5"),
                    "pm10": airq.get("pm10"),
                    "co": airq.get("co"),
                    "no2": airq.get("no2"),
                    "o3": airq.get("o3")
                },
                "location": location.get("name"),
                "localtime": location.get("localtime")
            }

            self.log_manager.log("Weather data fetched.")
            return weather_data

        except Exception as e:
            self.log_manager.log(f"Weather fetch error: {e}")
            return None


        
    

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
            filtered_value = avg
        else:
            filtered_value = value
        
        history.append(filtered_value)
        if len(history) > self.window_size:
            history.pop(0)
        
        return filtered_value
    
    def convert_epoch(self, epoch_value):
        if type(int(epoch_value)) is not None:
        # Convert epoch_value to Europe/Berlin timezone
            time_value = utime.localtime(int(epoch_value) + (self.config.DST_HOURS * 3600))
            formatted_time = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                time_value[0], time_value[1], time_value[2],
                time_value[3], time_value[4], time_value[5]
            )
        return formatted_time if not None else epoch_value

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
