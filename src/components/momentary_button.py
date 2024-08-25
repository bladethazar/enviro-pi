from machine import Pin
import utime

class MomentaryButton:
    def __init__(self, pin_number, debounce_ms=300):
        self.button = Pin(pin_number, Pin.IN, Pin.PULL_UP)
        self.last_press = 0
        self.debounce_ms = debounce_ms

    def is_pressed(self):
        current_time = utime.ticks_ms()
        if not self.button.value() and utime.ticks_diff(current_time, self.last_press) > self.debounce_ms:
            self.last_press = current_time
            return True
        return False