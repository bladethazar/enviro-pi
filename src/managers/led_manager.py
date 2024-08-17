import utime
from machine import Timer

class LEDManager:
    def __init__(self, led):
        self.led = led
        self.current_status = "RUNNING"
        self.timer = Timer()
        self.pulse_direction = 1
        self.pulse_value = 0
        self.update_led(self.current_status)

    def update_led(self, status):
        self.current_status = status
        self.timer.deinit()  # Stop any existing timer
        
        if status == "RUNNING":
            self.timer.init(period=50, mode=Timer.PERIODIC, callback=self._pulse_green)
        elif status == "PROCESSING":
            self.timer.init(period=50, mode=Timer.PERIODIC, callback=self._pulse_blue)
        elif status == "ERROR":
            self.timer.init(period=500, mode=Timer.PERIODIC, callback=self._blink_red)

    def _pulse_green(self, _):
        self.pulse_value += self.pulse_direction * 5
        if self.pulse_value >= 128 or self.pulse_value <= 0:
            self.pulse_direction *= -1
        self.led.set_rgb(0, self.pulse_value, 0)

    def _pulse_blue(self, _):
        self.pulse_value += self.pulse_direction * 5
        if self.pulse_value >= 192 or self.pulse_value <= 0:
            self.pulse_direction *= -1
        self.led.set_rgb(0, 0, self.pulse_value)

    def _blink_red(self, _):
        if self.pulse_value == 0:
            self.pulse_value = 255
        else:
            self.pulse_value = 0
        self.led.set_rgb(self.pulse_value, 0, 0)