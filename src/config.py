import json


class PicoWConfig:
  
    @classmethod
    def load_from_file(cls, filename='config.json'):
        """Load configuration from a JSON file."""
        try:
            with open(filename, 'r') as f:
                config_dict = json.load(f)
                for key, value in config_dict.items():
                    setattr(cls, key, value)
        except Exception as e:
            print(f"Error loading configuration: {e}")

    @classmethod
    def get_mqtt_config(cls):
        """Return a dictionary of MQTT-specific configuration."""
        return {
            'broker_address': cls.MQTT_BROKER_ADDRESS,
            'broker_port': cls.MQTT_BROKER_PORT,
            'client_name': cls.MQTT_CLIENT_NAME,
            'publish_interval': cls.MQTT_UPDATE_INTERVAL,
            'reconnect_interval': cls.MQTT_UPDATE_INTERVAL,
        }