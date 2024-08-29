from machine import I2C, Pin

class AFLTR390:
    def __init__(self, sda_pin=4, scl_pin=5, address=0x53):
        self.i2c = I2C(0, sda=Pin(sda_pin), scl=Pin(scl_pin))
        self.address = address
        self._write_register_byte(0x00, 0x02)  # Enable UVS
        self._write_register_byte(0x05, 0x01)  # Set gain to 3x

    def _write_register_byte(self, register, value):
        self.i2c.writeto(self.address, bytes([register, value]))

    def _read_register(self, register, length):
        self.i2c.writeto(self.address, bytes([register]))
        return self.i2c.readfrom(self.address, length)

    @property
    def uvs(self):
        return int.from_bytes(self._read_register(0x10, 3), 'little')

    @property
    def light(self):
        return int.from_bytes(self._read_register(0x0D, 3), 'little')

    @property
    def uvi(self):
        return self.uvs / 2300

    @property
    def lux(self):
        return self.light * 0.6

    def read_sensor(self):
        return {
            "uv": self.uvs,
            "ambient_light": self.light,
            "uvi": self.uvi,
            "lux": self.lux
        }