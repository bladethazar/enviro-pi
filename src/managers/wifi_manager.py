import network
import uasyncio
from machine import Pin

class WiFiManager:
    def __init__(self, config, log_manager):
        self.led = Pin("LED", Pin.OUT)
        self.ssid = config.WIFI_SSID
        self.wifi_password = config.WIFI_PASSWORD
        self.log_manager = log_manager
        self.wlan = network.WLAN(network.STA_IF)
        self.system_manager = None

    def set_system_manager(self, system_manager):
        self.system_manager = system_manager

    async def connect(self):
        if self.system_manager:
            self.system_manager.start_processing("wifi_connect")
        
        self.wlan.active(True)
        self.wlan.connect(self.ssid, self.wifi_password)

        max_wait = 10
        while max_wait > 0:
            if self.wlan.status() < 0 or self.wlan.status() >= 3:
                break
            self.log_manager.log("Waiting for WiFi connection...")
            self.led.toggle()
            await uasyncio.sleep(1)
            max_wait -= 1

        if self.wlan.status() != 3:
            self.led.value(0)  # Turn off LED on connection failure
            if self.system_manager:
                self.system_manager.add_error("wifi_connection")
                self.system_manager.stop_processing("wifi_connect")
            raise RuntimeError('WiFi connection failed.')
        else:
            self.log_manager.log("WiFi connection successful.")
            self.led.value(1)  # Turn on LED to indicate connection
            status = self.wlan.ifconfig()
            self.log_manager.log(f"Assigned IP: {status[0]}")
            if self.system_manager:
                self.system_manager.stop_processing("wifi_connect")
                self.system_manager.clear_error("wifi_connection")

    async def ensure_connection(self):
        if not self.wlan.isconnected():
            await self.connect()

    def is_connected(self):
        return self.wlan.isconnected()

    def get_ip(self):
        return self.wlan.ifconfig()[0] if self.wlan.isconnected() else None