import time
from machine import Pin, ADC
from picographics import PicoGraphics, DISPLAY_ENVIRO_PLUS
from pimoroni import RGBLED, Button
from breakout_bme68x import BreakoutBME68X
from pimoroni_i2c import PimoroniI2C
from breakout_ltr559 import BreakoutLTR559
from adcfft import ADCFFT


class PicoEnviroPlus:

    def __init__(self, config, log_manager) -> None:
        self.log_manager = log_manager
        
        # Set configuration
        self.TEMPERATURE_OFFSET = config.TEMPERATURE_OFFSET
        self.ENVIRO_PLUS_DISPLAY_BRIGHTNESS = config.ENVIRO_PLUS_DISPLAY_BRIGHTNESS
        self.ALTITUDE = config.ALTITUDE
        self.GAS_ALERT_TRESHOLD = config.GAS_ALERT_TRESHOLD
        self.MICROPHONE_PIN = config.MICROPHONE_PIN
        
        # Initialize the display
        self.display = PicoGraphics(display=DISPLAY_ENVIRO_PLUS, rotate=90)
        self.display_backlight_on = True  # Start with backlight on
        self.display_modes = ["Sensor", "Watering", "Log", "Equaliser"]  # Add all your display modes here
        self.current_mode_index = 0
        self.display_mode = self.display_modes[self.current_mode_index]
        
        # Initialize the LED
        self.led = RGBLED(6, 7, 10, invert=True)

        # Initialize the buttons
        self.button_a = Button(12, invert=True)
        self.button_b = Button(13, invert=True)
        self.button_x = Button(14, invert=True)
        self.button_y = Button(15, invert=True)
        self.button_actions = {
            self.button_a: self.toggle_backlight,
            self.button_b: None,  # TODO: Add wifi reset functionality
            self.button_x: self.cycle_display_mode,
            self.button_y: None   # TODO: Add reset water-tank capacity
        }
        
        # Initialize edge values for temperature and gas (overwritten later)
        self.min_temperature = 100.0
        self.max_temperature = 0.0
        self.min_gas = 100000.0
        self.max_gas = 0.0
        
    def cycle_display_mode(self):
        self.current_mode_index = (self.current_mode_index + 1) % len(self.display_modes)
        self.display_mode = self.display_modes[self.current_mode_index]
        if not self.display_backlight_on:
            self.toggle_backlight()  # Turn on backlight when changing mode
        print(f"Switched to {self.display_mode} mode")
        
    def set_display_mode(self, mode):
        self.display_mode = mode
        if not self.display_backlight_on:
            self.toggle_backlight()  # Turn on backlight when changing mode

    def init_sensors(self):
        # Initializa the Pico W's I2C
        PINS_BREAKOUT_GARDEN = {"sda": 4, "scl": 5}
        self.i2c = PimoroniI2C(**PINS_BREAKOUT_GARDEN)

        # Initializa BME688 and LTR559 sensors
        self.bme = BreakoutBME68X(self.i2c, address=0x77)
        self.ltr = BreakoutLTR559(self.i2c)

        # Initializa ADCFFT library to read mic with fast fourier transform
        self.adcfft = ADCFFT()

        # Initializa analog channel for microphone
        self.mic = ADC(Pin(self.MICROPHONE_PIN))
        
    def read_bme688_sensor_data(self):
        # Discard initial readings efficiently using a loop before data acquisition
        for _ in range(2):  # Loop twice to discard two readings
            self.bme.read()  # Read and discard sensor data
            time.sleep(0.5)  # Maintain delay between readings
        return self.bme.read()
        
    def read_all_sensors(self):
        try:
            temperature, pressure, humidity, gas, status, _, _ = self.read_bme688_sensor_data()
            ltr_reading = self.get_ltr_reading()
            lux = ltr_reading[BreakoutLTR559.LUX] if ltr_reading else None
            mic_reading = self.mic.read_u16()
            
            return {
                "temperature": temperature,
                "pressure": pressure,
                "humidity": humidity,
                "gas": gas,
                "status": status,
                "lux": lux,
                "mic": mic_reading
            }
        except Exception as e:
            print(f"Error reading sensors: {e}")
            return None
        
    def toggle_backlight(self):
        if self.display_backlight_on:
            self.display.set_backlight(0)
            self.display_backlight_on = False
        else:
            self.display.set_backlight(self.ENVIRO_PLUS_DISPLAY_BRIGHTNESS)
            self.display_backlight_on = True

    def handle_button_input(self):
        for button, action in self.button_actions.items():
            if button.is_pressed and action is not None:
                print(f"Button pressed: {button}")
                action()
                self.display.update()  # Immediately update display after button press
                # Wait for button release with a timeout
                start_time = time.time()
                while button.is_pressed:
                    time.sleep(0.01)
                    if time.time() - start_time > 1:  # 1 second timeout
                        print("Button press timeout")
                        break
                time.sleep(0.1)
                return
    
    def set_temperature_edge_values(self, corrected_temperature):
        if corrected_temperature >= self.max_temperature:
            self.max_temperature = corrected_temperature
        if corrected_temperature <= self.min_temperature:
            self.min_temperature = corrected_temperature
            
    def set_gas_edge_values(self, gas):
        if gas > self.max_gas:
            self.max_gas = gas
        if gas < self.min_gas:
            self.min_gas = gas
            
        temperature, pressure, humidity, gas, status, _, _ = self.bme.read()
        return temperature, pressure, humidity, gas, status, _, _ 
            
    def get_led(self):
        return self.led
    
    def get_ltr_reading(self):
        return self.ltr.get_reading()
    