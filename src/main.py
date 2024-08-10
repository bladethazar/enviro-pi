import _thread
import os
import sys
import time
import uasyncio
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

# Managers
log_mgr = LogManager(PicoWConfig)
system_mgr = SystemManager(PicoWConfig)
data_mgr = DataManager()

# Wifi and MQTT connections
wifi_manager = WiFiManager(PicoWConfig, log_mgr)
mqtt_manager = MQTTManager(PicoWConfig, log_mgr)


# Initialize components
m5_watering_unit = M5WateringUnit(log_mgr)
enviro_plus = PicoEnviroPlus(PicoWConfig, log_mgr, m5_watering_unit.reset_water_tank_capacity)
enviro_plus.init_sensors()
enviro_plus_led = enviro_plus.get_led()

# Init enviro+ display manager
enviro_plus_display_mgr = PicoEnviroPlusDisplayMgr(enviro_plus, log_mgr, data_mgr)
enviro_plus_display_mgr.setup_display(PicoWConfig)


# Connect to WiFi and MQTT
wifi_manager.connect()
mqtt_manager.connect()

# Global variables
mqtt_time = 0
mqtt_success = False

async def read_sensors():
    sensor_data = enviro_plus.read_all_sensors()
    temperature, pressure, humidity, gas, status, lux = (
        sensor_data['temperature'],
        sensor_data['pressure'],
        sensor_data['humidity'],
        sensor_data['gas'],
        sensor_data['status'],
        sensor_data['lux']
    )
    
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
        "mic": sensor_data['mic'],
        "status": status
    }
    
async def handle_watering():
    current_time = time.time()
    if current_time - m5_watering_unit.last_watering_check_time >= PicoWConfig.WATERING_CHECK_INTERVAL:
        m5_watering_unit.last_watering_check_time = current_time
        m5_watering_unit.check_moisture_and_watering_status()
        m5_watering_unit.update_status()

async def update_display(sensor_data):
    enviro_plus.handle_button_input()
    if enviro_plus.display_mode == "Sensor":
        enviro_plus_display_mgr.update_sensor_display(
            sensor_data['temperature'],
            sensor_data['humidity'],
            sensor_data['pressure'],
            sensor_data['lux'],
            sensor_data['gas']
        )
    elif enviro_plus.display_mode == "Watering":
        watering_unit_data = m5_watering_unit.get_current_data()
        enviro_plus_display_mgr.update_watering_display(watering_unit_data)
    elif enviro_plus.display_mode == "Log":
        log_mgr.enable_buffering()
        enviro_plus_display_mgr.update_log_display()
    elif enviro_plus.display_mode == "Equaliser":
        enviro_plus_display_mgr.update_equalizer_display()

async def handle_mqtt_publishing(sensor_data):
    global mqtt_time, mqtt_success
    current_time = time.ticks_ms()
    if (current_time - mqtt_time) / 1000 >= PicoWConfig.MQTT_UPDATE_INTERVAL:
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
            
            if mqtt_manager.publish_data(prepared_mqtt_data):
                log_mgr.log(f"Finished publishing topics to MQTT-Broker successfully.")
                print("PicoW Growmat  | Finished publishing topics to MQTT-Broker successfully.")
                mqtt_time = time.ticks_ms()
                enviro_plus_led.set_rgb(0, 50, 0)
                mqtt_success = True
            else:
                log_mgr.log(f"Error publishing to MQTT-Broker.")
                print("PicoW Growmat  | Error publishing to MQTT-Broker.")
                enviro_plus_led.set_rgb(255, 0, 0)
                mqtt_success = False
        except Exception as e:
            print(f"Exception: {e}")
            enviro_plus_led.set_rgb(255, 0, 0)
            mqtt_success = False

async def startup_sequence():
    enviro_plus.set_display_mode("Log")
    log_mgr.enable_buffering()
    await uasyncio.sleep(0.1)
    enviro_plus_display_mgr.set_log_speed(1)
    enviro_plus_display_mgr.update_log_display()
    await uasyncio.sleep(1)
    
    log_mgr.log("Startup complete.")
    enviro_plus_display_mgr.update_log_display()
    await uasyncio.sleep(2)  # Display the final message for 2 seconds
    
    log_mgr.disable_buffering()
    enviro_plus.set_display_mode("Sensor")

async def main_loop():
    while True:
        system_mgr.update_system_data()
        if enviro_plus.display_mode == "Log":
            if not log_mgr.buffering_enabled:
                log_mgr.enable_buffering()
            enviro_plus_display_mgr.update_log_display()
            await uasyncio.sleep(0.5) # Adjust to make scrolling smoother
        else:
            if log_mgr.buffering_enabled:
                log_mgr.disable_buffering()
                
        sensor_data = await read_sensors()
        if sensor_data is None:
            log_mgr.log(f"Failed to read sensor data. Retrying in 5 seconds ...")
            print("PicoW Growmat  | Failed to read sensor data. Retrying in 5 seconds...")
            await uasyncio.sleep(5)
            continue
        
        await handle_watering()
        
        await update_display(sensor_data)
        
        if sensor_data['status'] & STATUS_HEATER_STABLE:
            await handle_mqtt_publishing(sensor_data)
        

        await uasyncio.sleep(0.1)

async def main():
    log_mgr.log(f"Components initialized successfully. Starting main loop ...")
    await startup_sequence()
    await main_loop()

# Run the main coroutine
uasyncio.run(main())