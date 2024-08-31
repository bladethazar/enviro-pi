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
from components.af_ltr390 import AFLTR390 

# Enable emergency exception buffer
micropython.alloc_emergency_exception_buf(100)


# Managers
log_mgr = LogManager()
config_mgr = ConfigManager(log_mgr)
system_mgr = SystemManager(config_mgr, log_mgr, None)
data_mgr = DataManager(config_mgr, log_mgr, system_mgr)
system_mgr.data_mgr = data_mgr  
wifi_mgr = WiFiManager(config_mgr, log_mgr)
mqtt_mgr = MQTTManager(config_mgr, log_mgr)
influx_data_manager = InfluxDataManager(config_mgr, log_mgr)

# Initialize components
water_tank = WaterTank(config_mgr.WATER_TANK_FULL_CAPACITY, log_mgr)
m5_watering_unit = M5WateringUnit(config_mgr, system_mgr, log_mgr, water_tank)
af_ltr390 = AFLTR390()
enviro_plus = PicoEnviroPlus(config_mgr, log_mgr, data_mgr, af_ltr390, water_tank.reset_capacity, m5_watering_unit)
enviro_plus.init_sensors()
enviro_plus_led = enviro_plus.get_led()
external_watering_button = MomentaryButton(config_mgr.MOMENTARY_BUTTON_PIN)

# Set up SystemManager with LED
system_mgr.set_led(enviro_plus_led)

# Init enviro+ display manager
enviro_plus_display_mgr = PicoEnviroPlusDisplayMgr(config_mgr, enviro_plus, log_mgr, data_mgr, m5_watering_unit, system_mgr)
enviro_plus_display_mgr.setup_display(config_mgr)

# Set display manager in enviro_plus
enviro_plus.set_display_manager(enviro_plus_display_mgr)


# Set SystemManager to controll system status led
wifi_mgr.set_system_manager(system_mgr)
mqtt_mgr.set_system_manager(system_mgr)
m5_watering_unit.set_system_manager(system_mgr)
enviro_plus.set_system_manager(system_mgr)

# Global variables
current_status = "running"
last_mqtt_publish = 0
last_moisture_check = 0
external_watering_button_pressed = False




async def check_external_watering_button():
    global external_watering_button_pressed
    while True:
        if external_watering_button.is_pressed():
            external_watering_button_pressed = True
        await uasyncio.sleep_ms(100)

async def handle_external_watering_button():
    global external_watering_button_pressed
    if external_watering_button_pressed:
        log_mgr.log("External watering button pressed")
        await m5_watering_unit.trigger_watering()
        external_watering_button_pressed = False

async def read_enviro_plus_sensors():
    sensor_data = enviro_plus.get_sensor_data()
    if sensor_data is None:
        return None
    
    try:
        # Extract and process the new sensor data
        temperature = sensor_data.get('temperature')
        pressure = sensor_data.get('pressure')
        humidity = sensor_data.get('humidity')
        gas = sensor_data.get('gas')
        gas_quality = sensor_data.get('gas_quality')
        lux = sensor_data.get('lux')
        light_status = sensor_data["light_status"]
        mic = sensor_data.get('mic')
        env_status = sensor_data.get('env_status')
        env_issues = sensor_data.get('env_issues', [])
        af_uv = sensor_data.get('af_uv')
        af_uvi = sensor_data.get('af_uvi'),
        af_ambient_light = sensor_data.get('af_ambient_light'),
        af_lux = sensor_data.get('af_lux')
        
        
        if None in (temperature, pressure, humidity, gas, lux, mic):
            return None
        
        return {
            "temperature": temperature,
            "humidity": humidity,
            "pressure": pressure,
            "gas": gas,
            "gas_quality": gas_quality,
            "lux": lux,
            "light_status": light_status,
            "mic": mic,
            "status": sensor_data.get('status', 0),
            "env_status": env_status,
            "env_issues": ','.join(env_issues) if env_issues else '',
            "af_uv": af_uv,
            "af_uvi": af_uvi[0],
            "af_ambient_light": af_ambient_light[0],
            "af_lux": af_lux
        }
    except Exception as e:
        log_mgr.log(f"Error processing sensor data: {e}")
        return None

async def handle_watering():
    global last_moisture_check
    current_time = utime.time()
    if current_time - last_moisture_check >= config_mgr.MOISTURE_CHECK_INTERVAL:
        last_moisture_check = current_time
        await m5_watering_unit.check_moisture_and_watering_status()
        m5_watering_unit.update_status()

async def update_display(sensor_data):
    if sensor_data is None:
        return
    
    try:
        if enviro_plus.display_mode == "Sensor":
            await enviro_plus_display_mgr.update_sensor_display(sensor_data)
        elif enviro_plus.display_mode == "Watering":
            watering_unit_data = m5_watering_unit.get_current_data()
            if watering_unit_data:
                await enviro_plus_display_mgr.update_watering_display(watering_unit_data)
        elif enviro_plus.display_mode == "Log":
            await enviro_plus_display_mgr.update_log_display()
        elif enviro_plus.display_mode == "System":
            system_data = system_mgr.get_system_data()
            await enviro_plus_display_mgr.update_system_display(system_data['system'])
    except Exception as e:
        log_mgr.log(f"Error updating display: {e}")
        
def on_display_mode_change(new_mode):
    log_mgr.log(f"Display mode changed to: {new_mode}")
    uasyncio.create_task(update_display(None, force_update=True))

async def handle_mqtt_publishing(sensor_data):
    global last_mqtt_publish
    current_time = utime.time()
    
    if current_time - last_mqtt_publish >= config_mgr.MQTT_UPDATE_INTERVAL:
        if not mqtt_mgr.is_connected:
            log_mgr.log("MQTT not connected, attempting to connect...")
            await mqtt_mgr.connect()
        
        if mqtt_mgr.is_connected:
            try:
                enviro_plus_data = {
                    "temperature": round(sensor_data['temperature'], 2),
                    "humidity": round(sensor_data['humidity'], 2),
                    "pressure": round(sensor_data['pressure'], 2),
                    "gas": sensor_data['gas'],
                    "gas_quality": sensor_data['gas_quality'],
                    "lux": sensor_data['lux'],
                    "light_status": sensor_data['light_status'],
                    "mic": sensor_data['mic'],
                    "env_status": sensor_data['env_status'],
                    "env_issues": sensor_data['env_issues'],
                    "af_uv": sensor_data['af_uv'],
                    "af_uvi": sensor_data['af_uvi'],
                    "af_ambient_light": sensor_data['af_ambient_light'],
                    "af_lux": sensor_data['af_lux']
                }
                prepared_mqtt_data = data_mgr.prepare_mqtt_sensor_data_for_publishing(
                    m5_watering_unit.get_current_data(),
                    enviro_plus_data,
                    system_mgr.get_system_data()
                )
                publish_result = await mqtt_mgr.publish_data(prepared_mqtt_data)
                if publish_result:
                    last_mqtt_publish = current_time
            except Exception as e:
                log_mgr.log(f"MQTT publishing error: {e}")
        else:
            log_mgr.log("MQTT connection failed, skipping publish")
            
async def startup():
    display_task = None
    try:
        log_mgr.enable_buffering()
        log_mgr.log("Starting PicoW-Growmat startup sequence...")
        enviro_plus.set_display_mode("Log")  # Set Log Mode for startup

        # Initialize WiFi
        log_mgr.log("Initializing connections...")
        wifi_task = uasyncio.create_task(wifi_mgr.connect())
        
        
        # Start continuous log update
        display_task = uasyncio.create_task(enviro_plus_display_mgr.continuous_log_update())
        
        # Wait for WiFi task to complete with a timeout
        try:
            await uasyncio.wait_for(wifi_task, 30)  # 30 seconds timeout
        except uasyncio.TimeoutError:
            log_mgr.log("WiFi connection timed out")
            
        # Synchronize time
        if system_mgr.sync_time():
            log_mgr.log("Time synchronized successfully")
        else:
            log_mgr.log("Failed to synchronize time")
            
            
        enviro_plus.on_display_mode_change = on_display_mode_change
        mqtt_mgr.set_m5_watering_unit(m5_watering_unit)
        
        uasyncio.create_task(mqtt_mgr.run())
        
        uasyncio.create_task(system_mgr.run())
        influxdb_task = uasyncio.create_task(influx_data_manager.query_task())
        uasyncio.create_task(enviro_plus.run())
        uasyncio.create_task(check_external_watering_button())
        
        # Wait for InfluxDB query to complete
        try:
            water_tank_level, last_watered = await uasyncio.wait_for(influxdb_task, 10)  # 10 seconds timeout for InfluxDB query
            if water_tank_level is not None:
                water_tank.set_capacity(water_tank_level)
            if last_watered is not None:
                m5_watering_unit.set_last_watered_time(last_watered)
        except uasyncio.TimeoutError:
            log_mgr.log("InfluxDB query timed out")
            
        
        # Allow some time for final logs to be displayed
        await uasyncio.sleep(2)
        
        enviro_plus.set_display_mode(config_mgr.DEFAULT_DISPLAY_MODE)
    except RuntimeError as e:
        log_mgr.log(f"WiFi connection error: {e}")
    except Exception as e:
        log_mgr.log(f"Error in startup sequence: {e}")
        sys.print_exception(e)
    finally:
        # Ensure display task is always cancelled
        if display_task:
            display_task.cancel()
            try:
                await display_task
            except uasyncio.CancelledError:
                pass
        log_mgr.log("Startup sequence completed")

async def main_loop():
    await startup()
    while True:
        try:
            gc.collect()
            system_mgr.update_system_data()
            
            await handle_external_watering_button()

            enviro_plus_sensor_data = await read_enviro_plus_sensors()
            if enviro_plus_sensor_data is None:
                log_mgr.log("No sensor data available, skipping this iteration")
                await uasyncio.sleep(5)
                continue

            await handle_watering()
            
            enviro_plus.check_buttons()

            await update_display(enviro_plus_sensor_data)
            
            if enviro_plus_sensor_data.get('status', 0) & STATUS_HEATER_STABLE:
                await handle_mqtt_publishing(enviro_plus_sensor_data)
            else:
                log_mgr.log(" Gas sensor heater not stable, skipping MQTT publishing")

            await uasyncio.sleep(1)

        except Exception as e:
            log_mgr.log(f"Error in main loop: {e}")
            system_mgr.print_system_data()
            await uasyncio.sleep(5)

async def main():
    main_loop_task = uasyncio.create_task(main_loop())
    await main_loop_task

# Run the main coroutine
uasyncio.run(main())