import _thread
from machine import Pin, ADC
import utime
from config import PicoWConfig

class M5WateringUnit:
    last_watering_check_time = 0
    def __init__(self, log_manager):
        self.log_manager = log_manager
        self.MOISTURE_SENSOR_PIN_NR = ADC(PicoWConfig.MOISTURE_SENSOR_PIN_NR)
        self.MOISTURE_SENSOR_DRY_VALUE = PicoWConfig.MOISTURE_SENSOR_DRY_VALUE
        self.MOISTURE_SENSOR_WET_VALUE = PicoWConfig.MOISTURE_SENSOR_WET_VALUE
        self.MOISTURE_THRESHOLD = PicoWConfig.MOISTURE_THRESHOLD
        
        self.WATER_PUMP_PIN_NR = Pin(PicoWConfig.WATER_PUMP_PIN_NR, Pin.OUT)
        self.WATER_PUMP_FLOW_RATE = PicoWConfig.WATER_PUMP_FLOW_RATE
        self.WATERING_DURATION = PicoWConfig.WATERING_DURATION
        self.WATERING_MAX_CYCLES = PicoWConfig.WATERING_MAX_CYCLES
        self.WATERING_PAUSE_DURATION = PicoWConfig.WATERING_PAUSE_DURATION
        self.WATER_TANK_CAPACITY = PicoWConfig.WATER_TANK_FULL_CAPACITY
        
        self.current_moisture = self.read_moisture()
        
        self.water_used = 0
        self.watering_cycles = 0
        self.is_watering = False
        self.watered_time = 0
        self.watering_pause_start_time = 0
        self.watering_cycle_pause_flag = False
        
        self.lock = _thread.allocate_lock()
        self.log_manager.log("Initialized M5WateringUnit successful!")
        print("M5WateringUnit | Initialization successful!")
        

    def read_moisture(self):
        raw_value = self.MOISTURE_SENSOR_PIN_NR.read_u16()

        # Error handling for division by zero
        if self.MOISTURE_SENSOR_DRY_VALUE == self.MOISTURE_SENSOR_WET_VALUE:
            return None  # Or handle the error differently

        # Convert to floating-point for accurate calculation
        raw_value = float(raw_value)
        dry_value = float(self.MOISTURE_SENSOR_DRY_VALUE)
        wet_value = float(self.MOISTURE_SENSOR_WET_VALUE)

        # Calculate moisture percentage with potential calibration factor
        calibration_factor = (dry_value - wet_value) / (self.MOISTURE_SENSOR_DRY_VALUE - self.MOISTURE_SENSOR_WET_VALUE)
        moisture_percent = ((dry_value - raw_value) / (dry_value - wet_value)) * 100 * calibration_factor

        return max(0, min(100, moisture_percent))

    def control_pump(self, duration):
        self.WATER_PUMP_PIN_NR.on()
        utime.sleep(duration)
        self.WATER_PUMP_PIN_NR.off()
        self.watered_time += duration

    def get_water_tank_capacity_left(self):
        return max(0, self.WATER_TANK_CAPACITY - self.water_used)
    
    def reset_water_tank_capacity(self):
        self.WATER_TANK_CAPACITY = PicoWConfig.WATER_TANK_FULL_CAPACITY
        self.water_used = 0
        print("Waten tank capacity resetted!")

    def get_current_data(self):
        with self.lock:
            return {
                "moisture": round(self.current_moisture, 2),
                "water_used": round(self.water_used, 2),
                "water_left": round(self.get_water_tank_capacity_left(), 2),
                "is_watering": self.is_watering,
                "watering_cycles": self.watering_cycles,
                "watering_cycles_configured": self.WATERING_MAX_CYCLES
            }

    def check_moisture_and_watering_status(self):
        # print("M5WateringUnit | Starting soil moisture checks and watering ...")
        with self.lock:
            self.current_moisture = self.read_moisture()
            self.log_manager.log(f"Soil moisture level: {self.current_moisture:.2f}%")
            print(f"M5WateringUnit | Soil moisture level: {self.current_moisture:.2f}%")

            if self.current_moisture < self.MOISTURE_THRESHOLD:
                if self.watering_cycles < self.WATERING_MAX_CYCLES and self.get_water_tank_capacity_left() > 0 and not self.watering_cycle_pause_flag:
                    # Start watering
                    self.log_manager.log(f"Start watering for {self.WATERING_DURATION} seconds ...")
                    print(f"M5WateringUnit | Start watering for {self.WATERING_DURATION} seconds ...")
                    self.is_watering = True
                    self.watering_cycles += 1
                    self.control_pump(self.WATERING_DURATION)
                    self.log_manager.log(f"Finshed watering.")
                    print("M5WateringUnit | Finshed watering.")
                    
                    # Calculate water used after watering
                    water_used = (self.watered_time / 60) * self.WATER_PUMP_FLOW_RATE
                    self.watered_time = 0  # Reset watered time
                    self.water_used += water_used
                else:
                    # Handle max watering cycles or empty tank
                    if self.watering_cycles >= self.WATERING_MAX_CYCLES:
                        self.log_manager.log(f"Max watering cycles [{self.watering_cycles}/{self.WATERING_MAX_CYCLES}] reached. Pausing watering ...")
                        print(f"M5WateringUnit | Max watering cycles [{self.watering_cycles}/{self.WATERING_MAX_CYCLES}] reached. Pausing watering ...")
                        self.watering_cycles = 0
                        self.watering_cycle_pause_flag = True
                        self.watering_pause_start_time = utime.ticks_ms()
                    elif self.get_water_tank_capacity_left() <= 0:
                        self.current_moisture = self.read_moisture()
                        self.log_manager.log(f"Water tank empty. Pausing automated watering. Refill water-tank!")
                        print("M5WateringUnit | Water tank empty. Pausing automated watering. Refill water-tank!")
            else:
                self.log_manager.log(f"Soil moisture is okay.")
                print("M5WateringUnit | Soil moisture is okay.")
                self.watering_cycles = 0
            # print("M5WateringUnit | Soil moisture checks and watering finished.")

    def update_status(self):
        if self.watering_cycle_pause_flag:
            if (utime.ticks_ms() - self.watering_pause_start_time) / 1000 >= self.WATERING_PAUSE_DURATION:
                self.watering_cycle_pause_flag = False
                self.log_manager.log("Watering cycle pause finished.")
                print("M5WateringUnit | Watering cycle pause finished.")