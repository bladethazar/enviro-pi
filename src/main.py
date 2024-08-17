import sys
import uasyncio
import machine
import gc
import micropython
import utime
from breakout_bme68x import STATUS_HEATER_STABLE

from config import PicoWConfig
from managers.wifi_manager import WiFiManager
from managers.mqtt_manager import MQTTManager
from managers.data_manager import DataManager
from managers.system_manager import SystemManager
from managers.log_manager import LogManager
from managers.pp_enviro_plus_display_mgr import PicoEnviroPlusDisplayMgr
from components.m5_watering_unit import M5WateringUnit
from components.pp_enviro_plus import PicoEnviroPlus

# Enable emergency exception buffer
micropython.alloc_emergency_exception_buf(100)

# Load custom configuration from json-file
PicoWConfig.load_from_file()

# Managers
log_mgr = LogManager(PicoWConfig)
system_mgr = SystemManager(PicoWConfig)
data_mgr = DataManager(PicoWConfig)
wifi_mgr = WiFiManager(PicoWConfig, log_mgr)
mqtt_mgr = MQTTManager(PicoWConfig, log_mgr)

# Initialize components
m5_watering_unit = M5WateringUnit(PicoWConfig, log_mgr)
enviro_plus = PicoEnviroPlus(PicoWConfig, log_mgr, m5_watering_unit.reset_water_tank_capacity, m5_watering_unit.trigger_watering)
enviro_plus.init_sensors()
enviro_plus_led = enviro_plus.get_led()

# Set up SystemManager with LED
system_mgr.set_led(enviro_plus_led)

# Init enviro+ display manager
enviro_plus_display_mgr = PicoEnviroPlusDisplayMgr(enviro_plus, log_mgr, data_mgr, m5_watering_unit, system_mgr)
enviro_plus_display_mgr.setup_display(PicoWConfig)

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

# Watchdog timer
wdt = machine.WDT(timeout=8000)  # 8 second timeout

async def read_sensors():
    sensor_data = enviro_plus.get_sensor_data()
    if sensor_data is None:
        return None
    
    try:
        temperature = sensor_data.get('temperature')
        pressure = sensor_data.get('pressure')
        humidity = sensor_data.get('humidity')
        gas = sensor_data.get('gas')
        lux = sensor_data.get('lux')
        
        if None in (temperature, pressure, humidity, gas, lux):
            return None
        
        corrected_temperature = data_mgr.correct_temperature_reading(temperature)
        corrected_humidity = data_mgr.correct_humidity_reading(humidity, temperature, corrected_temperature)
        pressure_hpa = data_mgr.adjust_to_sea_pressure(pressure, corrected_temperature, PicoWConfig.ALTITUDE)
        
        enviro_plus.set_temperature_edge_values(corrected_temperature)
        enviro_plus.set_gas_edge_values(gas)
        
        return {
            "temperature": corrected_temperature,
            "humidity": corrected_humidity,
            "pressure": pressure_hpa,
            "gas": gas,
            "lux": lux,
            "mic": sensor_data.get('mic'),
            "status": sensor_data.get('status', 0)
        }
    except Exception as e:
        log_mgr.log(f"Error processing sensor data: {e}")
        return None

async def handle_watering():
    global last_moisture_check
    current_time = utime.time()
    if current_time - last_moisture_check >= PicoWConfig.MOISTURE_CHECK_INTERVAL:
        last_moisture_check = current_time
        await m5_watering_unit.check_moisture_and_watering_status()
        m5_watering_unit.update_status()

async def update_display(sensor_data):
    if sensor_data is None:
        return
    
    try:
        if enviro_plus.display_mode == "Sensor":
            if all(key in sensor_data for key in ['temperature', 'humidity', 'pressure', 'lux', 'gas']):
                await enviro_plus_display_mgr.update_sensor_display(
                    sensor_data['temperature'],
                    sensor_data['humidity'],
                    sensor_data['pressure'],
                    sensor_data['lux'],
                    sensor_data['gas'],
                    sensor_data['mic']
                )
        elif enviro_plus.display_mode == "Watering":
            watering_unit_data = m5_watering_unit.get_current_data()
            if watering_unit_data:
                await enviro_plus_display_mgr.update_watering_display(watering_unit_data)
        elif enviro_plus.display_mode == "Log":
            await enviro_plus_display_mgr.update_log_display()
        elif enviro_plus.display_mode == "System":
            system_data = system_mgr.get_system_data()
            await enviro_plus_display_mgr.update_system_display(system_data[0]['system'])
    except Exception as e:
        log_mgr.log(f"Error updating display: {e}")

async def handle_mqtt_publishing(sensor_data):
    global last_mqtt_publish
    current_time = utime.time()
    
    if current_time - last_mqtt_publish >= PicoWConfig.MQTT_UPDATE_INTERVAL:
        if not mqtt_mgr.is_connected:
            log_mgr.log("MQTT not connected, attempting to connect...")
            await mqtt_mgr.connect()
        
        if mqtt_mgr.is_connected:
            try:
                enviro_plus_data = {
                    "temperature": sensor_data['temperature'],
                    "humidity": sensor_data['humidity'],
                    "pressure": sensor_data['pressure'],
                    "gas": sensor_data['gas'],
                    "lux": sensor_data['lux'],
                    "mic": sensor_data['mic']
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


async def startup_sequence():
    display_task = None
    try:
        log_mgr.enable_buffering()
        log_mgr.log("Starting startup sequence...")
        enviro_plus.set_display_mode("Log")  # Set Log Mode for startup

        # Initialize WiFi
        log_mgr.log("Initializing connections...")
        wifi_task = uasyncio.create_task(wifi_mgr.connect())
        
        # Start continuous log update
        display_task = uasyncio.create_task(enviro_plus_display_mgr.continuous_log_update())
        
        # Wait for WiFi task to complete with a timeout
        try:
            await uasyncio.wait_for(wifi_task, 30)  # 30 seconds timeout
            wdt.feed()  # Feed the watchdog after WiFi connection attempt
        except uasyncio.TimeoutError:
            log_mgr.log("WiFi connection timed out")
        
        # Allow some time for final logs to be displayed
        await uasyncio.sleep(2)
        
        log_mgr.log("Startup sequence finished")
        enviro_plus.set_display_mode("Watering")  # Set Watering Mode as default after startup
    except RuntimeError as e:
        log_mgr.log(f"WiFi connection error: {e}")
    except Exception as e:
        log_mgr.log(f"Error in startup sequence: {e}")
        print(f"Error in startup sequence: {e}")
        sys.print_exception(e)
    finally:
        # Ensure display task is always cancelled
        if display_task:
            display_task.cancel()
            try:
                await display_task
            except uasyncio.CancelledError:
                pass
        log_mgr.log("Startup sequence cleanup completed")
        wdt.feed()  # Final watchdog feed before exiting startup sequence

async def main_loop():
    log_mgr.log("Starting main loop...")
    await startup_sequence()
    uasyncio.create_task(enviro_plus.run())
    uasyncio.create_task(system_mgr.run())  # Start the SystemManager task
    while True:
        try:
            gc.collect()
            system_mgr.update_system_data()

            sensor_data = await read_sensors()
            if sensor_data is None:
                log_mgr.log("No sensor data available, skipping this iteration")
                await uasyncio.sleep(5)
                continue

            await handle_watering()
            enviro_plus.check_buttons()
            
            if enviro_plus.display_mode == "Log":
                await enviro_plus_display_mgr.update_log_display()
            else:
                await update_display(sensor_data)
            
            if sensor_data.get('status', 0) & STATUS_HEATER_STABLE:
                await handle_mqtt_publishing(sensor_data)
            else:
                log_mgr.log("Sensor heater not stable, skipping MQTT publishing")

            wdt.feed()
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