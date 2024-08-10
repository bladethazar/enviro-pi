import network
import time
from machine import Pin, Timer
 

class WiFiManager:
    def __init__(self, config, log_manager) -> None:
        self.led = Pin("LED", Pin.OUT)
        self.tim = Timer()
        self.ssid = config.WIFI_SSID
        self.wifi_password = config.WIFI_PASSWORD
        self.log_manager = log_manager

    @classmethod        
    def tick(timer):
        global led
        led.toggle()

    def connect(self):
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        wlan.connect(self.ssid, self.wifi_password)

        max_wait = 10
        while max_wait > 0:
            if wlan.status() < 0 or wlan.status() >= 3:
                break
            self.log_manager.log(f"Waiting for WiFi connection...")
            print("WiFiManager    | Waiting for WiFi connection...")
            self.tim.init(freq=2.5, mode=Timer.PERIODIC, callback=self.tick)
            time.sleep(1)
            max_wait -= 1

        if wlan.status() != 3:
            self.led.value(0)  # Turn off LED on connection failure
            self.tim.deinit()  # Stop blinking
            raise RuntimeError('WiFiManager    | WiFi connection failed.')
        else:
            self.log_manager.log(f"WiFi connection successful.")
            print('WiFiManager    | WiFi connection successful.')
            self.led.value(1)  # Turn on LED to indicate connection
            self.tim.deinit()  # Stop blinking
            status = wlan.ifconfig()
            self.log_manager.log(f"Assigned IP: {status[0]}")
            print('WiFiManager    | Assigned IP:', status[0])


# For standalone testing
# if __name__ == "__main__":
#     config = {
#         "WIFI_SSID": "<YOUR_NETWORK_SSID>",
#         "WIFI_PASSWORD": "<YOUR_SECRET_PASSWORD>"
#     }
#     wifi_manager = WiFiManager(config)
#     wifi_manager.connect()