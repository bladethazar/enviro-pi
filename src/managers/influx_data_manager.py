import urequests
import uasyncio

class InfluxDataManager:
    def __init__(self, config, log_manager):
        self.config = config
        self.log_manager = log_manager
        self.enabled = bool(getattr(config, "INFLUXDB_ENABLED", False))
        self.available = False

        if not self.enabled:
            return

        host = getattr(config, "INFLUXDB_HOST", None)
        token = getattr(config, "INFLUXDB_TOKEN", None)
        org = getattr(config, "INFLUXDB_ORG", None)
        bucket = getattr(config, "INFLUXDB_BUCKET", None)
        port = getattr(config, "INFLUXDB_PORT", 8086)

        if not host or not token or not org or not bucket:
            self.log_manager.log("InfluxDB disabled: missing config values")
            self.enabled = False
            return

        self.base_url = f"http://{host}:{port}/api/v2"
        self.health_url = f"http://{host}:{port}/health"
        self.org = org
        self.bucket = bucket
        self.token = token

    async def check_availability(self):
        if not self.enabled:
            return False

        response = None
        try:
            response = urequests.get(self.health_url)
            if response.status_code == 200:
                self.available = True
                return True
            self.log_manager.log(f"InfluxDB health check failed with status code {response.status_code}")
        except Exception as e:
            self.log_manager.log(f"InfluxDB unavailable: {e}")
        finally:
            if response:
                response.close()
            await uasyncio.sleep(0)

        self.available = False
        self.enabled = False
        return False