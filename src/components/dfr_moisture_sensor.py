from machine import ADC, Pin
import uasyncio
import _thread

class DFRobotMoistureSensor:
    def __init__(self, config, log_manager) -> None:
        self.sensor_pin = ADC(Pin(config.DFR_MOISTURE_SENSOR_PIN))
        self.log_mgr = log_manager
        
        # Configuration values
        self.SENSOR_DRY_VALUE = config.DFR_MOISTURE_SENSOR_DRY_VALUE
        self.SENSOR_WET_VALUE = config.DFR_MOISTURE_SENSOR_WET_VALUE
        self.THRESHOLD = config.MOISTURE_THRESHOLD
        
        self.moisture_raw = self.sensor_pin.read_u16()
        self.moisture_percent = self.calculate_moisture_lvl()
        
        self.lock = _thread.allocate_lock()
        self.log_mgr.log("DFRobotMoistureSensor initialized.")
        
    
    def calculate_moisture_lvl(self):
        try:
            
            self.moisture_raw = self.sensor_pin.read_u16()
            # Calculate moisture percentage
            moisture_range = self.SENSOR_DRY_VALUE - self.SENSOR_WET_VALUE
            if moisture_range == 0:
                self.log_mgr.log("Error: DFR Moisture sensor not properly calibrated")
                return None

            # Correct calculation: 100% when raw_value is at or below WET_VALUE, 0% when at or above DRY_VALUE
            if self.moisture_raw <= self.SENSOR_WET_VALUE:
                moisture_percent = 100.0
            elif self.moisture_raw >= self.SENSOR_DRY_VALUE:
                moisture_percent = 0.0
            else:
                moisture_percent = ((self.SENSOR_DRY_VALUE - self.moisture_raw) / moisture_range) * 100

            moisture_percent = max(0, min(100, moisture_percent))
            return moisture_percent
        except Exception as e:
            self.log_mgr.log(f"Error reading DFR moisture: {e}")
            return None
        
        
    async def read_moisture(self):
        with self.lock:
            self.moisture_percent = self.calculate_moisture_lvl()
            if self.moisture_percent is None:
                self.log_mgr.log("Failed to read DFR moisture.")
                if self.system_manager:
                    self.system_manager.add_error("DFR moisture_read")
                return
                
    def get_moisture_data(self):
        return {
            "moisture_percent": round(self.moisture_percent, 2) if self.moisture_percent is not None else None,
            "moisture_raw": self.moisture_raw
            }