from config import PicoWConfig


class DataManager:
    def __init__(self) -> None:
        pass
    
    def correct_temperature_reading(self, temperature):
        return temperature - PicoWConfig.TEMPERATURE_OFFSET

    def correct_humidity_reading(self, humidity, temperature, corrected_temperature):
        dewpoint = temperature - ((100 - humidity) / 5)
        return 100 - (5 * (corrected_temperature - dewpoint))

    def adjust_to_sea_pressure(self, pressure, temperature, altitude):
        """
        Adjust pressure based on your altitude.

        credits to @cubapp https://gist.github.com/cubapp/23dd4e91814a995b8ff06f406679abcf
        """
        pressure_hpa = pressure / 100
        # Adjusted-to-the-sea barometric pressure
        adjusted_hpa = pressure_hpa + ((pressure_hpa * 9.80665 * altitude) / (287 * (273 + temperature + (altitude / 400))))
        return adjusted_hpa
    
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
            print(f"Exception in prepare_mqtt_sensor_data_for_publishing: {e}")
            return None


    def describe_pressure(self, pressure_hpa):
        """Convert pressure into barometer-type description."""
        if pressure_hpa < 970:
            description = "storm"
        elif 970 <= pressure_hpa < 990:
            description = "rain"
        elif 990 <= pressure_hpa < 1010:
            description = "change"
        elif 1010 <= pressure_hpa < 1030:
            description = "fair"
        elif pressure_hpa >= 1030:
            description = "dry"
        else:
            description = ""
        return description


    def describe_humidity(self, corrected_humidity):
        """Convert relative humidity into good/bad description."""
        if 40 < corrected_humidity < 80:
            description = "good"
        else:
            description = "bad"
        return description


    def describe_light(self, lux):
        """Convert light level in lux to descriptive value."""
        if lux < 50:
            description = "dark"
        elif 50 <= lux < 100:
            description = "dim"
        elif 100 <= lux < 500:
            description = "light"
        elif lux >= 500:
            description = "bright"
        return description