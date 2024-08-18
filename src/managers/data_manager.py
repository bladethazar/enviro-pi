import math

class DataManager:
    def __init__(self, config):
        self.config = config

    def correct_temperature_reading(self, temperature):
        return temperature - self.config.TEMPERATURE_OFFSET

    def correct_humidity_reading(self, humidity, temperature, corrected_temperature):
        dewpoint = temperature - ((100 - humidity) / 5)
        return max(0, min(100, 100 - (5 * (corrected_temperature - dewpoint))))

    def adjust_to_sea_pressure(self, pressure, temperature, altitude):
        pressure_hpa = pressure / 100
        adjusted_hpa = pressure_hpa + ((pressure_hpa * 9.80665 * altitude) / (287 * (273 + temperature + (altitude / 400))))
        return adjusted_hpa
    
    def adjust_cpu_frequency(self, cpu_frequency):
        return cpu_frequency / 1000000

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

    def describe_pressure(self, pressure_hpa):
        if pressure_hpa < 970:
            return "storm"
        elif 970 <= pressure_hpa < 990:
            return "rain"
        elif 990 <= pressure_hpa < 1010:
            return "change"
        elif 1010 <= pressure_hpa < 1030:
            return "fair"
        elif pressure_hpa >= 1030:
            return "dry"
        else:
            return "unknown"

    def describe_humidity(self, corrected_humidity):
        return "good" if 40 < corrected_humidity < 80 else "bad"

    def describe_light(self, lux):
        if lux < 50:
            return "dark"
        elif 50 <= lux < 100:
            return "dim"
        elif 100 <= lux < 500:
            return "light"
        elif lux >= 500:
            return "bright"
        else:
            return "unknown"