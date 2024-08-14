import utime
import uasyncio
from machine import Pin, ADC
import _thread
import gc

class M5WateringUnit:
    def __init__(self, config, log_manager):
        self.log_manager = log_manager
        self.config = config
        
        # Initialize pins
        self.moisture_sensor = ADC(config.MOISTURE_SENSOR_PIN_NR)
        self.water_pump = Pin(config.WATER_PUMP_PIN_NR, Pin.OUT)
        
        # Configuration values
        self.MOISTURE_SENSOR_DRY_VALUE = config.MOISTURE_SENSOR_DRY_VALUE
        self.MOISTURE_SENSOR_WET_VALUE = config.MOISTURE_SENSOR_WET_VALUE
        self.MOISTURE_THRESHOLD = config.MOISTURE_THRESHOLD
        self.WATER_PUMP_FLOW_RATE = config.WATER_PUMP_FLOW_RATE
        self.WATERING_DURATION = config.WATERING_DURATION
        self.WATERING_MAX_CYCLES = config.WATERING_MAX_CYCLES
        self.WATERING_PAUSE_DURATION = config.WATERING_PAUSE_DURATION
        self.WATER_TANK_CAPACITY = config.WATER_TANK_FULL_CAPACITY
        
        # State variables
        self.current_moisture = self.read_moisture()
        self.water_used = 0
        self.watering_cycles = 0
        self.is_watering = False
        self.watered_time = 0
        self.watering_pause_start_time = 0
        self.watering_cycle_pause_flag = False
        self.last_watering_check_time = 0
        
        self.lock = _thread.allocate_lock()
        
        self.log_manager.log("Initialized M5WateringUnit successfully!")

    def read_moisture(self):
        try:
            raw_value = self.moisture_sensor.read_u16()
            moisture_percent = ((self.MOISTURE_SENSOR_DRY_VALUE - raw_value) / 
                                (self.MOISTURE_SENSOR_DRY_VALUE - self.MOISTURE_SENSOR_WET_VALUE)) * 100
            return max(0, min(100, moisture_percent))
        except Exception as e:
            self.log_manager.log(f"Error reading moisture: {e}")
            return None

    async def control_pump(self, duration):
        try:
            self.water_pump.on()
            await uasyncio.sleep(duration)
            self.water_pump.off()
            self.watered_time += duration
            water_used = (duration / 60) * self.WATER_PUMP_FLOW_RATE
            self.water_used += water_used
            self.log_manager.log(f"Watered for {duration}s, used {water_used:.2f}ml")
        except Exception as e:
            self.log_manager.log(f"Error controlling pump: {e}")
            self.water_pump.off()  # Ensure pump is off in case of error
        finally:
            self.is_watering = False

    def get_water_tank_capacity_left(self):
        return max(0, self.WATER_TANK_CAPACITY - self.water_used)

    def reset_water_tank_capacity(self):
        self.WATER_TANK_CAPACITY = self.config.WATER_TANK_FULL_CAPACITY
        self.water_used = 0
        self.log_manager.log("Water tank capacity reset")

    def get_current_data(self):
        with self.lock:
            return {
                "moisture": round(self.current_moisture, 2) if self.current_moisture is not None else None,
                "water_used": round(self.water_used, 2),
                "water_left": round(self.get_water_tank_capacity_left(), 2),
                "is_watering": self.is_watering,
                "watering_cycles": self.watering_cycles,
                "watering_cycles_configured": self.WATERING_MAX_CYCLES
            }

    async def check_moisture_and_watering_status(self):
        self.log_manager.log("Starting moisture and watering status check")
        with self.lock:
            self.log_manager.log("Acquired lock")
            self.current_moisture = self.read_moisture()
            self.log_manager.log(f"Current moisture read: {self.current_moisture}")
            if self.current_moisture is None:
                self.log_manager.log("Failed to read moisture. Skipping watering check.")
                return

            self.log_manager.log(f"Soil moisture level: {self.current_moisture:.2f}%")

            if self.current_moisture < self.MOISTURE_THRESHOLD:
                self.log_manager.log("Moisture below threshold")
                if (self.watering_cycles < self.WATERING_MAX_CYCLES and 
                    self.get_water_tank_capacity_left() > 0 and 
                    not self.watering_cycle_pause_flag):
                    self.log_manager.log("Starting watering")
                    await self.trigger_watering()
                else:
                    self.log_manager.log("Cannot start watering")
                    await self.handle_watering_limits()
            else:
                self.log_manager.log("Soil moisture is okay.")
                self.watering_cycles = 0
            self.log_manager.log("Moisture and watering status check completed")

    async def trigger_watering(self):
        self.log_manager.log(f"Start watering for {self.WATERING_DURATION} seconds...")
        self.is_watering = True
        self.watering_cycles += 1
        await self.control_pump(self.WATERING_DURATION)

    async def handle_watering_limits(self):
        if self.watering_cycles >= self.WATERING_MAX_CYCLES:
            self.log_manager.log(f"Max watering cycles [{self.watering_cycles}/{self.WATERING_MAX_CYCLES}] reached. Pausing watering...")
            self.watering_cycles = 0
            self.watering_cycle_pause_flag = True
            self.watering_pause_start_time = utime.ticks_ms()
        elif self.get_water_tank_capacity_left() <= 0:
            self.log_manager.log("Water tank empty. Pausing automated watering. Refill water tank!")

    def update_status(self):
        if self.watering_cycle_pause_flag:
            if utime.ticks_diff(utime.ticks_ms(), self.watering_pause_start_time) >= self.WATERING_PAUSE_DURATION * 1000:
                self.watering_cycle_pause_flag = False
                self.log_manager.log("Watering cycle pause finished.")

    async def manual_water(self, duration=None):
        if duration is None:
            duration = self.WATERING_DURATION
        
        self.log_manager.log(f"Manual watering triggered for {duration} seconds.")
        await self.control_pump(duration)
        self.log_manager.log("Manual watering completed.")

    async def run(self):
        while True:
            current_time = utime.time()
            if current_time - self.last_watering_check_time >= self.config.WATERING_CHECK_INTERVAL:
                self.last_watering_check_time = current_time
                await self.check_moisture_and_watering_status()
                self.update_status()
            await uasyncio.sleep(1)

    def cleanup(self):
        self.water_pump.off()
        gc.collect()