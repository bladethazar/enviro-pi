import json

class ConfigManager:
    def __init__(self, log_mgr):
        self.log_manager = log_mgr
        self._config = {}
        self.load_from_file()
        
    

    def load_from_file(self, filename='../config.json'):
        try:
            with open(filename, 'r') as f:
                self._config = json.load(f)
            self.log_manager.log("Configuration loaded successfully")
        except Exception as e:
            self.log_manager.log(f"Error loading configuration: {e}")

    def save_to_file(self, filename='config.json'):
        try:
            with open(filename, 'w') as f:
                json.dump(self._config, f)
            self.log_manager.log("Configuration saved successfully")
        except Exception as e:
            self.log_manager.log(f"Error saving configuration: {e}")

    def update_config(self, key, value):
        if key in self._config:
            self._config[key] = value
            self.save_to_file()
            return True
        return False

    def get(self, key, default=None):
        return self._config.get(key, default)

    def __getattr__(self, name):
        return self.get(name)