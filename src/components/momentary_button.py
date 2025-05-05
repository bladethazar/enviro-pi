import utime
from machine import Pin

class MomentaryButton:
    def __init__(self, pin_number, sample_size=5, threshold=4, debounce_ms=50):
        self.button = Pin(pin_number, Pin.IN, Pin.PULL_UP)
        self.sample_size = sample_size
        self.threshold = threshold
        self.debounce_ms = debounce_ms
        self.last_press_time = 0
        self.samples = [1] * sample_size  # Initialize with pulled-up state

    def is_pressed(self):
        current_time = utime.ticks_ms()
        if utime.ticks_diff(current_time, self.last_press_time) < self.debounce_ms:
            return False

        # Shift samples and add new reading
        self.samples = self.samples[1:] + [self.button.value()]
        
        # Check if enough low samples to consider a press
        if sum(self.samples) <= self.sample_size - self.threshold:
            self.last_press_time = current_time
            return True
        
        return False