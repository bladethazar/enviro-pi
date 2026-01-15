import asyncio
import utime
import uasyncio
from machine import Pin, ADC
from picographics import PicoGraphics, DISPLAY_ENVIRO_PLUS
from pimoroni import RGBLED, Button
from breakout_bme68x import BreakoutBME68X, STATUS_HEATER_STABLE
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

        # Initialize display (default rotation)
        self.display = PicoGraphics(display=DISPLAY_ENVIRO_PLUS, rotate=0)
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
        self.display_modes = ["Overview", "VPD", "Air", "Light", "Sound", "System", "Log"]
        self.current_mode_index = 0
        self.display_mode = self.display_modes[self.current_mode_index]

        # Sensor data
        self.last_sensor_read = 0
        self.sensor_data = {}

        # Sensor sampling config (fallbacks for missing config keys)
        self.sensor_read_samples = getattr(self.config, "SENSOR_READ_SAMPLES", 3)
        self.sensor_read_delay_ms = getattr(self.config, "SENSOR_READ_DELAY_MS", 50)
        self.mic_read_samples = getattr(self.config, "MIC_READ_SAMPLES", 5)
        self.mic_read_delay_ms = getattr(self.config, "MIC_READ_DELAY_MS", 10)

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
            mic_pin = getattr(self.config, "ENVIRO_PLUS_MICROPHONE_PIN", 26)
            self.mic = ADC(Pin(mic_pin))
            self.log_manager.log("PicoEnviroPlus sensors initialized.")
        except Exception as e:
            self.log_manager.log(f"Error initializing PicoEnviroPlus sensors: {e}")

    def _is_valid_number(self, value):
        try:
            return value is not None and value == value and value != float("inf") and value != float("-inf")
        except Exception:
            return False

    def _median(self, values, default=None):
        if not values:
            return default
        ordered = sorted(values)
        return ordered[len(ordered) // 2]

    def _collect_samples(self, read_fn, sample_count, delay_ms):
        samples = []
        for _ in range(sample_count):
            try:
                samples.append(read_fn())
            except Exception:
                pass
            if delay_ms:
                utime.sleep_ms(delay_ms)
        return samples

    def read_sensors(self):
        try:
            bme_samples = self._collect_samples(self.bme.read, self.sensor_read_samples, self.sensor_read_delay_ms)
            bme_samples = [s for s in bme_samples if isinstance(s, (list, tuple)) and len(s) >= 5]
            if not bme_samples:
                raise Exception("No BME68X samples available")

            temperature_samples = [s[0] for s in bme_samples if self._is_valid_number(s[0])]
            pressure_samples = [s[1] for s in bme_samples if self._is_valid_number(s[1])]
            humidity_samples = [s[2] for s in bme_samples if self._is_valid_number(s[2])]
            gas_samples = [s[3] for s in bme_samples if self._is_valid_number(s[3])]
            status = bme_samples[-1][4]

            temperature = self._median(temperature_samples)
            pressure = self._median(pressure_samples)
            humidity = self._median(humidity_samples)
            gas = self._median(gas_samples)

            if temperature is None or pressure is None or humidity is None:
                raise Exception("Invalid BME68X readings")

            ltr_samples = self._collect_samples(self.ltr559.get_reading, self.sensor_read_samples, self.sensor_read_delay_ms)
            lux_samples = []
            for sample in ltr_samples:
                if sample:
                    try:
                        lux_samples.append(sample[BreakoutLTR559.LUX])
                    except Exception:
                        pass
            enviro_plus_lux = self._median(lux_samples, default=0)

            mic_samples = self._collect_samples(self.mic.read_u16, self.mic_read_samples, self.mic_read_delay_ms)
            mic_reading = self._median([s for s in mic_samples if self._is_valid_number(s)], default=0)
            
            corrected_temperature = self.data_mgr.correct_temperature_reading(temperature)
            corrected_temperature = self.data_mgr.filter_spike("temperature", corrected_temperature)
            self.set_temperature_edge_values(corrected_temperature)
            corrected_humidity = self.data_mgr.correct_humidity_reading(humidity, temperature, corrected_temperature)
            corrected_humidity = self.data_mgr.filter_spike("humidity", corrected_humidity)
            altitude = getattr(self.config, "ALTITUDE", 0)
            adjusted_pressure = self.data_mgr.adjust_to_sea_pressure(pressure, corrected_temperature, altitude)
            adjusted_pressure = self.data_mgr.filter_spike("pressure", adjusted_pressure)
            adjusted_enviro_plus_lux = self.data_mgr.adjust_lux_for_growhouse(enviro_plus_lux)
            adjusted_enviro_plus_lux = self.data_mgr.filter_spike("lux", adjusted_enviro_plus_lux)

            heater_stable = bool(status & STATUS_HEATER_STABLE)
            if gas is None:
                gas = None
                gas_quality = "Unavailable"
            else:
                gas = self.data_mgr.filter_spike("gas", gas)
                self.set_gas_edge_values(gas)
                gas_quality = self.data_mgr.interpret_gas_reading(gas) if heater_stable else "Warming"
            mic_db = self.data_mgr.interpret_mic_reading(mic_reading)
            light_status = self.data_mgr.describe_light(adjusted_enviro_plus_lux)
            humidity_status = self.data_mgr.describe_humidity(corrected_humidity)
            dew_point = self.data_mgr.calculate_dew_point(corrected_temperature, corrected_humidity)
            sound_status = self.data_mgr.describe_sound(mic_db)
            vpd = self.data_mgr.calculate_vpd(corrected_temperature, corrected_humidity)
            vpd_status = self.data_mgr.describe_vpd(vpd)

            # env_status, issues, light_status = self.data_mgr.describe_growhouse_environment(
            #     corrected_temperature, corrected_humidity, adjusted_enviro_plus_lux)
            self.sensor_data = {
                "temperature": corrected_temperature,
                "humidity": corrected_humidity,
                "humidity_status": humidity_status,
                "dew_point": dew_point,
                "vpd": vpd,
                "vpd_status": vpd_status,
                "pressure": adjusted_pressure,
                "gas": gas,
                "gas_quality": gas_quality,
                "heater_stable": heater_stable,
                "lux": adjusted_enviro_plus_lux,
                "light_status": light_status,
                "mic": mic_db,
                "sound_status": sound_status,
                "status": status
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