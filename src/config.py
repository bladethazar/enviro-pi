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
