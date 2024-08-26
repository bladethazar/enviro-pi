from machine import ADC, Pin
import _thread

class DFRobotMoistureSensor:
    def __init__(self, config, log_manager) -> None:
        self.sensor_pin = ADC(Pin(config.DFR_MOISTURE_SENSOR_PIN))
        self.log_mgr = log_manager
        
        # Configuration values
        self.SENSOR_DRY_VALUE = config.DFR_MOISTURE_SENSOR_DRY_VALUE
        self.SENSOR_WET_VALUE = config.DFR_MOISTURE_SENSOR_WET_VALUE
        self.THRESHOLD = config.DFR_MOISTURE_THRESHOLD
        
        self.current_moisture = self.read_moisture()
        
        self.lock = _thread.allocate_lock()
        self.log_mgr.log("DFRobotMoistureSensor initialized.")
        
    
    def read_moisture(self):
        try:
            raw_value = self.sensor_pin.read_u16()
            
            # Calculate moisture percentage
            moisture_range = self.SENSOR_DRY_VALUE - self.SENSOR_WET_VALUE
            if moisture_range == 0:
                self.log_mgr.log("Error: DFR Moisture sensor not properly calibrated")
                return None

            # Correct calculation: 100% when raw_value is at or below WET_VALUE, 0% when at or above DRY_VALUE
            if raw_value <= self.SENSOR_WET_VALUE:
                moisture_percent = 100.0
            elif raw_value >= self.SENSOR_DRY_VALUE:
                moisture_percent = 0.0
            else:
                moisture_percent = ((self.SENSOR_DRY_VALUE - raw_value) / moisture_range) * 100

            moisture_percent = max(0, min(100, moisture_percent))
            return moisture_percent
        except Exception as e:
            self.log_mgr.log(f"Error reading DFR moisture: {e}")
            return None
        
        
    async def check_moisture(self):
        with self.lock:
            self.current_moisture = self.read_moisture()
            if self.current_moisture is None:
                self.log_mgr.log("Failed to read DFR moisture.")
                if self.system_manager:
                    self.system_manager.add_error("DFR moisture_read")
                return

            self.log_mgr.log(f"DFR Soil moisture level: {self.current_moisture:.2f}%")

            if self.current_moisture < self.THRESHOLD:
                self.log_mgr.log(f"DFR moisture below threshold ({self.THRESHOLD}%)")
                
    def get_moisture_data(self):
        return {
            "moisture": round(self.current_moisture, 2) if self.current_moisture is not None else None
            }