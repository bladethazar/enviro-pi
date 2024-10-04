import sys
import uasyncio
import machine
import gc
import micropython
import utime
from breakout_bme68x import STATUS_HEATER_STABLE

from managers.config_manager import ConfigManager
from managers.wifi_manager import WiFiManager
from managers.mqtt_manager import MQTTManager
from managers.data_manager import DataManager
from managers.system_manager import SystemManager
from managers.log_manager import LogManager
from managers.pp_enviro_plus_display_mgr import PicoEnviroPlusDisplayMgr
from managers.influx_data_manager import InfluxDataManager
from components.m5_watering_unit import M5WateringUnit
from components.pp_enviro_plus import PicoEnviroPlus
from components.water_tank import WaterTank
from components.momentary_button import MomentaryButton 
from components.dfr_moisture_sensor import DFRobotMoistureSensor

class PicoWGrowmat:
    def __init__(self):
        micropython.alloc_emergency_exception_buf(100)
        
        self.log_mgr = LogManager()
        self.config_mgr = ConfigManager(self.log_mgr)
        self.system_mgr = SystemManager(self.config_mgr, self.log_mgr, None)
        self.data_mgr = DataManager(self.config_mgr, self.log_mgr, self.system_mgr)
        self.system_mgr.data_mgr = self.data_mgr
        self.wifi_mgr = WiFiManager(self.config_mgr, self.log_mgr)
        self.mqtt_mgr = MQTTManager(self.config_mgr, self.log_mgr)
        self.influx_data_manager = InfluxDataManager(self.config_mgr, self.log_mgr)

        self.water_tank = WaterTank(self.config_mgr.WATER_TANK_FULL_CAPACITY, self.log_mgr)
        self.m5_watering_unit = M5WateringUnit(self.config_mgr, self.system_mgr, self.log_mgr, self.data_mgr, self.water_tank)
        self.dfr_moisture_sensor = DFRobotMoistureSensor(self.config_mgr, self.log_mgr, self.data_mgr)
        self.enviro_plus = PicoEnviroPlus(self.config_mgr, self.log_mgr, self.data_mgr, self.water_tank.reset_capacity, self.m5_watering_unit)
        self.enviro_plus_led = self.enviro_plus.get_led()
        self.external_watering_button = MomentaryButton(self.config_mgr.MOMENTARY_BUTTON_PIN, sample_size=10, threshold=8)

        self.system_mgr.set_led(self.enviro_plus_led)
        self.enviro_plus_display_mgr = PicoEnviroPlusDisplayMgr(self.config_mgr, self.enviro_plus, self.log_mgr, self.data_mgr, self.m5_watering_unit, self.system_mgr)
        self.enviro_plus.set_display_manager(self.enviro_plus_display_mgr)

        self._setup_managers()
        self._initialize_state()

    def _setup_managers(self):
        self.wifi_mgr.set_system_manager(self.system_mgr)
        self.mqtt_mgr.set_system_manager(self.system_mgr)
        self.m5_watering_unit.set_system_manager(self.system_mgr)
        self.enviro_plus.set_system_manager(self.system_mgr)

    def _initialize_state(self):
        self.current_status = "running"
        self.last_mqtt_publish = 0
        self.last_moisture_check = 0
        self.external_watering_button_pressed = False

    async def run(self):
        await self.startup()
        await self.main_loop()

    async def startup(self):
        self.log_mgr.enable_buffering()
        self.log_mgr.log("Starting PicoW-Growmat startup sequence...")
        self.enviro_plus.set_display_mode("Log")

        await self._initialize_connections()
        await self._setup_components()
        await self._start_tasks()

        self.enviro_plus.set_display_mode(self.config_mgr.DEFAULT_DISPLAY_MODE)
        self.log_mgr.log("Startup sequence completed")

    async def _initialize_connections(self):
        self.log_mgr.log("Initializing connections...")
        try:
            await uasyncio.wait_for(self.wifi_mgr.connect(), 30)
        except uasyncio.TimeoutError:
            self.log_mgr.log("WiFi connection timed out")

        if self.system_mgr.sync_time():
            self.log_mgr.log("Time synchronized successfully")
        else:
            self.log_mgr.log("Failed to synchronize time")

    async def _setup_components(self):
        self.enviro_plus.on_display_mode_change = self.on_display_mode_change
        self.mqtt_mgr.set_m5_watering_unit(self.m5_watering_unit)
        self.mqtt_mgr.set_dfr_moisture_sensor(self.dfr_moisture_sensor)
        self.enviro_plus_display_mgr.setup_display(self.config_mgr)

    async def _start_tasks(self):
        uasyncio.create_task(self.mqtt_mgr.run())
        uasyncio.create_task(self.system_mgr.run())
        uasyncio.create_task(self.enviro_plus.run())
        uasyncio.create_task(self.check_external_watering_button())

        try:
            water_tank_level, last_watered = await uasyncio.wait_for(self.influx_data_manager.query_task(), 10)
            if water_tank_level is not None:
                self.water_tank.set_capacity(water_tank_level)
            if last_watered is not None:
                self.m5_watering_unit.set_last_watered_time(last_watered)
        except uasyncio.TimeoutError:
            self.log_mgr.log("InfluxDB query timed out")

    async def main_loop(self):
        while True:
            try:
                gc.collect()
                self.system_mgr.update_system_data()
                
                await self.handle_external_watering_button()
                await self.process_sensor_data()
                
                self.enviro_plus.check_buttons()
                await uasyncio.sleep(1)

            except Exception as e:
                self.log_mgr.log(f"Error in main loop: {e}")
                self.system_mgr.print_system_data()
                await uasyncio.sleep(5)

    async def process_sensor_data(self):
        # Enviro Plus Sensor
        enviro_plus_sensor_data = await self.read_enviro_plus_sensors()
        # DFR Moisture Sensor
        await self.dfr_moisture_sensor.read_moisture()
        dfr_moisture_sensor_data = self.dfr_moisture_sensor.get_moisture_data()
        # M5 Watering Unit
        await self.m5_watering_unit.read_moisture()
        m5_watering_unit_data = self.m5_watering_unit.get_current_data()
        
        if enviro_plus_sensor_data is None or dfr_moisture_sensor_data is None or m5_watering_unit_data is None:
            self.log_mgr.log("No Enviro Plus sensor data available")
        elif dfr_moisture_sensor_data is None:
            self.log_mgr.log("No DFR Moisture sensor data available")
        elif m5_watering_unit_data is None:
            self.log_mgr.log("No M5 Watering data available")

        await self.update_display(enviro_plus_sensor_data, dfr_moisture_sensor_data, m5_watering_unit_data)
        
        if enviro_plus_sensor_data.get('status', 0) & STATUS_HEATER_STABLE:
            await self.handle_mqtt_publishing(enviro_plus_sensor_data, dfr_moisture_sensor_data, m5_watering_unit_data)
        else:
            self.log_mgr.log("Gas sensor heater not stable, skipping MQTT publishing")

    async def check_external_watering_button(self):
        while True:
            if self.external_watering_button.is_pressed():
                self.external_watering_button_pressed = True
            await uasyncio.sleep_ms(100)

    async def handle_external_watering_button(self):
        if self.external_watering_button_pressed:
            self.log_mgr.log("External watering button pressed")
            await self.m5_watering_unit.trigger_watering()
            self.external_watering_button_pressed = False

    async def read_enviro_plus_sensors(self):
        return self.enviro_plus.get_sensor_data()

    async def update_display(self, sensor_data, dfr_moisture_sensor_data, m5_watering_unit_data):
        if sensor_data is None:
            return
        
        try:
            display_mode = self.enviro_plus.display_mode
            if display_mode == "Sensor":
                await self.enviro_plus_display_mgr.update_sensor_display(sensor_data)
            elif display_mode == "Watering":
                if m5_watering_unit_data and dfr_moisture_sensor_data:
                    await self.enviro_plus_display_mgr.update_watering_display(m5_watering_unit_data, dfr_moisture_sensor_data)
            elif display_mode == "Log":
                await self.enviro_plus_display_mgr.update_log_display()
            elif display_mode == "System":
                system_data = self.system_mgr.get_system_data()
                await self.enviro_plus_display_mgr.update_system_display(system_data['system'])
        except Exception as e:
            self.log_mgr.log(f"Error updating display: {e}")

    async def handle_mqtt_publishing(self, enviro_plus_sensor_data, dfr_moisture_sensor_data, m5_watering_unit_data):
        current_time = utime.time()
        if current_time - self.last_mqtt_publish >= self.config_mgr.MQTT_UPDATE_INTERVAL:
            if not self.mqtt_mgr.is_connected:
                self.log_mgr.log("MQTT not connected, attempting to connect...")
                await self.mqtt_mgr.connect()
            
            if self.mqtt_mgr.is_connected:
                try:
                    prepared_mqtt_data = self.data_mgr.prepare_mqtt_sensor_data_for_publishing(
                        m5_watering_unit_data,
                        dfr_moisture_sensor_data,
                        enviro_plus_sensor_data,
                        self.system_mgr.get_system_data(),
                        self.system_mgr.get_current_config_data()
                    )
                    publish_result = await self.mqtt_mgr.publish_data(prepared_mqtt_data)
                    if publish_result:
                        self.last_mqtt_publish = current_time
                except Exception as e:
                    self.log_mgr.log(f"MQTT publishing error: {e}")
            else:
                self.log_mgr.log("MQTT connection failed, skipping publish")

    def on_display_mode_change(self, new_mode):
        self.log_mgr.log(f"Display mode changed to: {new_mode}")
        uasyncio.create_task(self.update_display(None))