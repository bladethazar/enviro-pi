from machine import Pin, SPI
import _thread
import time

MOSI = 11
SCK = 10    
RCLK = 9

KILOBIT   = 0xFE
HUNDREDS  = 0xFD
TENS      = 0xFB
UNITS     = 0xF7
Dot       = 0x80

# Default hex codes for characters 0-9, A-F, adjustable by user
SEG8Code = {
    '0': 0x3F,
    '1': 0x06,
    '2': 0x5B,
    '3': 0x4F,
    '4': 0x66,
    '5': 0x6D,
    '6': 0x7D,
    '7': 0x07,
    '8': 0x7F,
    '9': 0x6F,
    'A': 0x77,
    'b': 0x7C,
    'C': 0x39,
    'd': 0x5E,
    'E': 0x79,
    'F': 0x71
}

class LED_8SEG():
    def __init__(self, custom_chars=None):
        self.rclk = Pin(RCLK, Pin.OUT)
        self.rclk(1)
        self.spi = SPI(1, 10000_000, polarity=0, phase=0, sck=Pin(SCK), mosi=Pin(MOSI), miso=None)
        self.SEG8 = SEG8Code
        if custom_chars:
            self.SEG8.update(custom_chars)  # Allow custom character definitions
        self.running = False
        self.lock = _thread.allocate_lock()

    def write_cmd(self, Num, Seg):    
        self.rclk(1)
        self.spi.write(bytearray([Num]))
        self.spi.write(bytearray([Seg]))
        self.rclk(0)
        time.sleep(0.005)  # Slight delay to ensure visibility across segments
        self.rclk(1)

    def clear_display(self):
        """Clear the display by turning off all segments."""
        self.write_cmd(UNITS, 0x00)
        self.write_cmd(TENS, 0x00)
        self.write_cmd(HUNDREDS, 0x00)
        self.write_cmd(KILOBIT, 0x00)

    def run_animation(self, animation, duration=5):
        """Run an animation on the display."""
        self.running = True
        start_time = time.time()
        while self.running and (time.time() - start_time < duration):
            with self.lock:
                try:
                    patterns = next(animation)
                    self.display_pattern(patterns)
                except StopIteration:
                    break
        self.clear_display()

    def start_animation(self, animation, duration=5):
        """Start the animation in a separate thread."""
        _thread.start_new_thread(self.run_animation, (animation, duration))

    def stop(self):
        """Stop the current animation."""
        self.running = False

    def display_pattern(self, patterns):
        """Display a specific pattern on all digits with proper delays."""
        self.write_cmd(UNITS, patterns[0])
        time.sleep(0.05)  # Increased delay for better visibility
        self.write_cmd(TENS, patterns[1])
        time.sleep(0.05)
        self.write_cmd(HUNDREDS, patterns[2])
        time.sleep(0.05)
        self.write_cmd(KILOBIT, patterns[3])
        time.sleep(0.05)

    def blink(self, duration=5):
        """Simple blink animation."""
        def blink_gen():
            while True:
                yield [0xFF, 0xFF, 0xFF, 0xFF]  # All segments on
                time.sleep(0.5)
                yield [0x00, 0x00, 0x00, 0x00]  # All segments off
                time.sleep(0.5)

        self.start_animation(blink_gen(), duration)

    def rotate(self, duration=5):
        """Improved rotating animation across all segments."""
        def rotate_gen():
            patterns = [
                [0x01, 0x00, 0x00, 0x00],
                [0x02, 0x00, 0x00, 0x00],
                [0x04, 0x00, 0x00, 0x00],
                [0x08, 0x00, 0x00, 0x00],
                [0x10, 0x00, 0x00, 0x00],
                [0x20, 0x00, 0x00, 0x00],
                [0x40, 0x00, 0x00, 0x00],
                [0x80, 0x00, 0x00, 0x00],
                [0x00, 0x01, 0x00, 0x00],
                [0x00, 0x02, 0x00, 0x00],
                [0x00, 0x04, 0x00, 0x00],
                [0x00, 0x08, 0x00, 0x00],
                [0x00, 0x10, 0x00, 0x00],
                [0x00, 0x20, 0x00, 0x00],
                [0x00, 0x40, 0x00, 0x00],
                [0x00, 0x80, 0x00, 0x00],
                [0x00, 0x00, 0x01, 0x00],
                [0x00, 0x00, 0x02, 0x00],
                [0x00, 0x00, 0x04, 0x00],
                [0x00, 0x00, 0x08, 0x00],
                [0x00, 0x00, 0x10, 0x00],
                [0x00, 0x00, 0x20, 0x00],
                [0x00, 0x00, 0x40, 0x00],
                [0x00, 0x00, 0x80, 0x00],
                [0x00, 0x00, 0x00, 0x01],
                [0x00, 0x00, 0x00, 0x02],
                [0x00, 0x00, 0x00, 0x04],
                [0x00, 0x00, 0x00, 0x08],
                [0x00, 0x00, 0x00, 0x10],
                [0x00, 0x00, 0x00, 0x20],
                [0x00, 0x00, 0x00, 0x40],
                [0x00, 0x00, 0x00, 0x80],
            ]
            while True:
                for pattern in patterns:
                    yield pattern
                    time.sleep(0.5)  # Slower rotation for visibility

        self.start_animation(rotate_gen(), duration)

    def progress_bar(self, duration=5):
        """Simple progress bar animation."""
        def progress_gen():
            pattern = [0x00, 0x00, 0x00, 0x00]
            while True:
                for i in range(4):
                    pattern[i] = (pattern[i] << 1) | 0x01
                    if pattern[i] == 0xFF:
                        pattern[i] = 0x00
                yield pattern
                time.sleep(0.5)

        self.start_animation(progress_gen(), duration)

if __name__ == '__main__':
    # Custom character example (optional)
    custom_chars = {
        'H': 0x76,  # Custom 'H' character
        'I': 0x30,  # Custom 'I' character
    }

    # Test setup for the LED_8SEG class
    LED = LED_8SEG(custom_chars)

    print("Testing Blink Animation")
    LED.blink(duration=10)
    time.sleep(10)

    print("Testing Rotate Animation")
    LED.rotate(duration=10)
    time.sleep(10)

    print("Testing Progress Bar Animation")
    LED.progress_bar(duration=10)
    time.sleep(10)

    print("Stopping the Display")
    LED.stop()

    print("Testing completed.")
