import urequests
import utime
import uasyncio

class InfluxDataManager:
    def __init__(self, config, log_manager):
        self.config = config
        self.log_manager = log_manager
        self.base_url = f"http://{config.INFLUXDB_HOST}/api/v2"
        self.org = config.INFLUXDB_ORG
        self.bucket = config.INFLUXDB_BUCKET
        self.token = config.INFLUXDB_TOKEN
        self.lookup_interval_in_days = 30

    async def _query_influxdb(self, query):
        url = f"{self.base_url}/query?org={self.org}"
        headers = {
            "Authorization": f"Token {self.token}",
            "Content-Type": "application/vnd.flux",
            "Accept": "application/csv"
        }
        try:
            response = None
            request_sent = False
            while not request_sent:
                try:
                    response = urequests.post(url, headers=headers, data=query)
                    request_sent = True
                except OSError as e:
                    if e.errno != 11:  # EAGAIN error
                        raise
                await uasyncio.sleep(0)  # Yield control

            if response.status_code == 200:
                return response.text
            else:
                self.log_manager.log(f"InfluxDB query failed with status code {response.status_code}")
                self.log_manager.log(f"Response content: {response.text[:200]}...")  # Log first 200 characters
                return None
        except Exception as e:
            self.log_manager.log(f"Error in InfluxDB query: {e}")
            return None
        finally:
            if response:
                response.close()

    def _parse_csv_response(self, csv_data):
        lines = csv_data.strip().split('\n')
        if len(lines) < 2:
            self.log_manager.log(f"Unexpected CSV format: {csv_data}")
            return None
        headers = lines[0].split(',')
        values = lines[-1].split(',')
        return dict(zip(headers, values))

    def _safe_float_conversion(self, value):
        try:
            return float(value)
        except ValueError:
            self.log_manager.log(f"Error converting to float: {value}")
            return None

    async def get_water_tank_level(self):
        query = f'''
        from(bucket:"{self.bucket}")
          |> range(start: -{self.lookup_interval_in_days}d)
          |> filter(fn: (r) => r.entity_id == "water_tank_level")
          |> last()
        '''
        result = await self._query_influxdb(query)
        if result:
            try:
                parsed_result = self._parse_csv_response(result)
                if parsed_result and '_value' in parsed_result:
                    return self._safe_float_conversion(parsed_result['_value'])
            except Exception as e:
                self.log_manager.log(f"Error parsing water tank level: {e}")
                self.log_manager.log(f"Raw response: {result}")
        return None

    async def get_last_watered_time(self):
        query = f'''
        from(bucket:"{self.bucket}")
          |> range(start: -{self.lookup_interval_in_days}d)
          |> filter(fn: (r) => r["friendly_name"] == "M5 Unit Last Watered")
          |> last()
        '''
        result = await self._query_influxdb(query)
        if result:
            try:
                parsed_result = self._parse_csv_response(result)
                if parsed_result and '_value' in parsed_result:
                    return 0 if parsed_result['_value'] == "Never" else parsed_result['_value']
            except Exception as e:
                self.log_manager.log(f"Error parsing last watered time: {e}")
                self.log_manager.log(f"Raw response: {result}")
        return None

    async def query_task(self):
        try:
            self.log_manager.log("Starting InfluxDB query task")
            water_tank_level = await self.get_water_tank_level()
            if water_tank_level is not None:
                self.log_manager.log(f"Water tank level: {water_tank_level}")
            else:
                self.log_manager.log("Failed to get water tank level from InfluxDB")

            last_watered = await self.get_last_watered_time()
            if last_watered is not None:
                try:
                    last_watered_time = utime.localtime(int(last_watered))
                    self.log_manager.log(f"M5 Watering Unit last watered: {last_watered_time}")
                except ValueError:
                    self.log_manager.log(f"Error converting last watered time: {last_watered}")
            else:
                self.log_manager.log("Failed to get last watered time from InfluxDB")
            
            return water_tank_level, last_watered
        except Exception as e:
            self.log_manager.log(f"Error when querying InfluxDB: {e}")
            return None, None