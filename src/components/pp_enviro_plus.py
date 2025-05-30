import asyncio
import utime
import uasyncio
from machine import Pin, ADC
from picographics import PicoGraphics, DISPLAY_ENVIRO_PLUS
from pimoroni import RGBLED, Button
from breakout_bme68x import BreakoutBME68X
from pimoroni_i2c import PimoroniI2C
from breakout_ltr559 import BreakoutLTR559
from adcfft import ADCFFT
import gc

class PicoEnviroPlus:
    def __init__(self, config, log_manager, data_mgr):
        self.config = config
        self.log_manager = log_manager
        self.data_mgr = data_mgr
        self.system_manager = None
        self.display_manager = None

        # Initialize display
        self.display = PicoGraphics(display=DISPLAY_ENVIRO_PLUS, rotate=90)
        self.display_width, self.display_height = self.display.get_bounds()

        # Initialize LED and buttons
        self.led = RGBLED(6, 7, 10, invert=True)
        self.buttons = {
            'A': Button(12, invert=True),
            'B': Button(13, invert=True),
            'X': Button(14, invert=True),
            'Y': Button(15, invert=True)
        }

        # Display settings
        self.display_backlight_on = True
        self.display_modes = ["Sensor", "Weather", "Log", "System"]
        self.current_mode_index = 1  # Start with Sensor mode
        self.display_mode = self.display_modes[self.current_mode_index]

        # Sensor data
        self.last_sensor_read = 0
        self.sensor_data = {}

        # Temperature edge values
        self.min_temperature = float('inf')
        self.max_temperature = float('-inf')

        # Gas edge values
        self.min_gas = float('inf')
        self.max_gas = float('-inf')

        # Initialize sensors
        self.init_sensors()

        self.log_manager.log("PicoEnviroPlus initialized.")

    def set_system_manager(self, system_manager):
        self.system_manager = system_manager

    def init_sensors(self):
        try:
            i2c = PimoroniI2C(sda=4, scl=5)
            self.bme = BreakoutBME68X(i2c, address=0x77)
            self.ltr559 = BreakoutLTR559(i2c)
            self.adcfft = ADCFFT()
            self.mic = ADC(Pin(self.config.ENVIRO_PLUS_MICROPHONE_PIN))
            self.log_manager.log("PicoEnviroPlus sensors initialized.")
        except Exception as e:
            self.log_manager.log(f"Error initializing PicoEnviroPlus sensors: {e}")

    def read_sensors(self):
        try:
            bme_data = self.bme.read()
            ltr559_data = self.ltr559.get_reading()
            mic_reading = self.mic.read_u16()

            temperature = bme_data[0]
            pressure = bme_data[1]
            humidity = bme_data[2]
            gas = bme_data[3]
            enviro_plus_lux = ltr559_data[BreakoutLTR559.LUX] if ltr559_data else 0
            
            corrected_temperature = self.data_mgr.correct_temperature_reading(temperature)
            self.set_temperature_edge_values(corrected_temperature)
            corrected_humidity = self.data_mgr.correct_humidity_reading(humidity, temperature, corrected_temperature)
            adjusted_pressure = self.data_mgr.adjust_to_sea_pressure(pressure, corrected_temperature, self.config.ALTITUDE)
            adjusted_enviro_plus_lux = self.data_mgr.adjust_lux_for_growhouse(enviro_plus_lux)
            
            gas_quality = self.data_mgr.interpret_gas_reading(gas)
            mic_db = self.data_mgr.interpret_mic_reading(mic_reading)

            # env_status, issues, light_status = self.data_mgr.describe_growhouse_environment(
            #     corrected_temperature, corrected_humidity, adjusted_enviro_plus_lux)
            self.sensor_data = {
                "temperature": corrected_temperature,
                "humidity": corrected_humidity,
                "pressure": adjusted_pressure,
                "gas": gas,
                "gas_quality": gas_quality,
                "lux": adjusted_enviro_plus_lux,
                # "light_status": light_status,
                "mic": mic_db,
                "status": bme_data[4]
                # "env_status": env_status,
                # "env_issues": issues
            }
            self.last_sensor_read = utime.ticks_ms()
            return self.sensor_data
        except Exception as e:
            self.log_manager.log(f"Error reading PicoEnviroPlus sensors: {e}")
            if self.system_manager:
                self.system_manager.add_error("sensor_read")
            return None

    def get_sensor_data(self):
        if utime.ticks_diff(utime.ticks_ms(), self.last_sensor_read) > 1000:
            return self.read_sensors()
        return self.sensor_data
    
    def set_display_manager(self, display_mgr):
        self.display_manager = display_mgr

    def set_display_mode(self, mode):
        if mode in self.display_modes:
            self.display_mode = mode
            self.current_mode_index = self.display_modes.index(mode)
            self.log_manager.log(f"Display mode set to {mode}")
        else:
            self.log_manager.log(f"Invalid display mode: {mode}")

    def cycle_display_mode(self):
        self.current_mode_index = (self.current_mode_index + 1) % len(self.display_modes)
        self.display_mode = self.display_modes[self.current_mode_index]
        self.log_manager.log(f"Switched to {self.display_mode} mode")

    def toggle_backlight(self):
        self.display_backlight_on = not self.display_backlight_on
        self.display.set_backlight(self.config.ENVIRO_PLUS_DISPLAY_BRIGHTNESS if self.display_backlight_on else 0)
        self.log_manager.log(f"Display backlight {'on' if self.display_backlight_on else 'off'}")
        

    async def handle_button_press(self, button):
        if self.display_manager is None:
            self.log_manager.log("Display manager not set")
            return

        current_mode = self.display_mode
        if current_mode not in self.display_manager.button_config:
            self.log_manager.log(f"Invalid display mode: {current_mode}")
            return

        button_actions = self.display_manager.button_config.get(current_mode, {})
        action_tuple = button_actions.get(button)

        if action_tuple is None:
            self.log_manager.log(f"No action defined for button {button} in mode {current_mode}")
            return

        action = action_tuple[0]  # The first element of the tuple is the action

        try:
            if action == self.display_manager.initiate_system_restart:
                await self.initiate_system_restart()
            elif callable(action):
                result = action()
                if hasattr(result, '__await__'):
                    await result
        except Exception as e:
            self.log_manager.log(f"Error executing button action: {e}")

    def check_buttons(self):
        for button, obj in self.buttons.items():
            if obj.read():
                uasyncio.create_task(self.handle_button_press(button))
                utime.sleep_ms(200)  # Debounce


    def set_led(self, r, g, b):
        self.led.set_rgb(r, g, b)

    def get_led(self):
        return self.led

    def set_temperature_edge_values(self, temperature):
        self.min_temperature = min(self.min_temperature, temperature)
        self.max_temperature = max(self.max_temperature, temperature)

    def set_gas_edge_values(self, gas):
        self.min_gas = min(self.min_gas, gas)
        self.max_gas = max(self.max_gas, gas)

    def cleanup(self):
        self.display.set_backlight(0)
        self.set_led(0, 0, 0)
        gc.collect()

    async def run(self):
        while True:
            self.check_buttons()
            await uasyncio.sleep_ms(100)