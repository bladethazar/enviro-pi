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
    def __init__(self, config, log_manager, reset_water_tank_capacity):
        self.config = config
        self.log_manager = log_manager
        self.reset_water_tank_capacity = reset_water_tank_capacity

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
        self.display_modes = ["Sensor", "Watering", "Log", "System"]
        self.current_mode_index = 1  # Start with Watering mode
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

        self.log_manager.log("PicoEnviroPlus initialized successfully")

    def init_sensors(self):
        try:
            i2c = PimoroniI2C(sda=4, scl=5)
            self.bme = BreakoutBME68X(i2c, address=0x77)
            self.ltr = BreakoutLTR559(i2c)
            self.adcfft = ADCFFT()
            self.mic = ADC(Pin(self.config.MICROPHONE_PIN))
            self.log_manager.log("Sensors initialized successfully")
        except Exception as e:
            self.log_manager.log(f"Error initializing sensors: {e}")

    def read_sensors(self):
        try:
            bme_data = self.bme.read()
            ltr_data = self.ltr.get_reading()
            mic_reading = self.mic.read_u16()

            self.sensor_data = {
                "temperature": bme_data[0] - self.config.TEMPERATURE_OFFSET,
                "pressure": bme_data[1],
                "humidity": bme_data[2],
                "gas": bme_data[3],
                "lux": ltr_data[BreakoutLTR559.LUX] if ltr_data else None,
                "mic": mic_reading,
                "status": bme_data[4]
            }
            self.last_sensor_read = utime.ticks_ms()
            return self.sensor_data
        except Exception as e:
            self.log_manager.log(f"Error reading sensors: {e}")
            return None

    def get_sensor_data(self):
        if utime.ticks_diff(utime.ticks_ms(), self.last_sensor_read) > 1000:
            return self.read_sensors()
        return self.sensor_data

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

    def handle_button_press(self, button):
        if button == 'A':
            self.toggle_backlight()
        elif button == 'B':
            if self.display_mode == "Watering":
                self.reset_water_tank_capacity()
            else:
                self.cycle_display_mode()
        elif button == 'X':
            self.cycle_display_mode()
        elif button == 'Y':
            if self.display_mode == "Watering":
                # Trigger manual watering
                pass  # Implement this functionality
            else:
                self.cycle_display_mode()

    def check_buttons(self):
        for button, obj in self.buttons.items():
            if obj.read():
                self.handle_button_press(button)
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