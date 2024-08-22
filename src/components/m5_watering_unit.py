import utime
import uasyncio
from machine import Pin, ADC
import _thread
import gc

class M5WateringUnit:
    def __init__(self, config, log_manager, water_tank):
        self.log_manager = log_manager
        self.system_manager = None
        self.config = config
        self.water_tank = water_tank
        self.auto_watering = False
        
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
        
        # State variables
        self.current_moisture = self.read_moisture()
        self.water_used = 0
        self.watering_cycles = 0
        self.is_watering = False
        self.watered_time = 0
        self.watering_pause_start_time = 0
        self.watering_cycle_pause_flag = False
        self.last_watering_check_time = 0
        self.last_watered = 0
        self.watering_block_timer = 0 
        
        self.lock = _thread.allocate_lock()
        
        self.log_manager.log("Initialized M5WateringUnit successfully!")

    def set_system_manager(self, system_manager):
        self.system_manager = system_manager
        
    def toggle_auto_watering(self):
        self.auto_watering = not self.auto_watering
        status = "enabled" if self.auto_watering else "disabled"
        self.log_manager.log(f"Auto watering {status}")
        return self.auto_watering

    def read_moisture(self):
        try:
            raw_value = self.moisture_sensor.read_u16()
            
            # Calculate moisture percentage
            moisture_range = self.MOISTURE_SENSOR_DRY_VALUE - self.MOISTURE_SENSOR_WET_VALUE
            if moisture_range == 0:
                self.log_manager.log("Error: Moisture sensor not properly calibrated")
                return None

            # Correct calculation: 100% when raw_value is at or below WET_VALUE, 0% when at or above DRY_VALUE
            if raw_value <= self.MOISTURE_SENSOR_WET_VALUE:
                moisture_percent = 100.0
            elif raw_value >= self.MOISTURE_SENSOR_DRY_VALUE:
                moisture_percent = 0.0
            else:
                moisture_percent = ((self.MOISTURE_SENSOR_DRY_VALUE - raw_value) / moisture_range) * 100

            moisture_percent = max(0, min(100, moisture_percent))
            return moisture_percent
        except Exception as e:
            self.log_manager.log(f"Error reading moisture: {e}")
            return None

    async def control_pump(self, duration):
        current_time = utime.time()
        if current_time < self.watering_block_timer:
            self.log_manager.log(f"Watering blocked. Please wait {self.watering_block_timer - current_time} seconds.")
            return

        try:
            if self.system_manager:
                self.system_manager.start_processing("watering")
            self.is_watering = True
            self.water_pump.on()
            await uasyncio.sleep(duration)
            self.water_pump.off()
            self.watered_time += duration
            water_used = (duration / 60) * self.WATER_PUMP_FLOW_RATE
            self.water_tank.reduce_capacity(water_used)
            self.water_used += water_used
            self.last_watered = utime.time()
            self.watering_block_timer = self.last_watered + duration  # Set the block timer
            self.log_manager.log(f"Watered for {duration}s, used {water_used:.2f}ml")
            if self.system_manager:
                self.system_manager.stop_processing("watering")
        except Exception as e:
            self.log_manager.log(f"Error controlling pump: {e}")
            if self.system_manager:
                self.system_manager.add_error("watering")
            self.water_pump.off()  # Ensure pump is off in case of error
        finally:
            self.is_watering = False

    
    def reset_water_used(self):
        self.water_used = 0
        self.log_manager.log("Watering Unit 1 - water_used value reset")
        
    def get_time_since_last_watered(self):
        if self.last_watered == 0:
            return "Never"
        
        time_diff = utime.time() - self.last_watered
        if time_diff < 60:
            return f"{time_diff} sec ago"
        elif time_diff < 3600:
            return f"{time_diff // 60} min ago"
        elif time_diff < 86400:
            return f"{time_diff // 3600} hr ago"
        else:
            return f"{time_diff // 86400} days ago"

    def get_current_data(self):
        with self.lock:
            return {
                "moisture": round(self.current_moisture, 2) if self.current_moisture is not None else None,
                "water_used": round(self.water_used, 2),
                "water_left": round(self.water_tank.get_capacity(), 2),
                "last_watered": self.get_time_since_last_watered(),
                "watering_cycles": self.watering_cycles,
                "watering_cycles_configured": self.WATERING_MAX_CYCLES,
                "auto_watering": self.auto_watering
            }

    async def check_moisture_and_watering_status(self):
        self.log_manager.log("Starting moisture and watering status check")
        with self.lock:
            self.current_moisture = self.read_moisture()
            if self.current_moisture is None:
                self.log_manager.log("Failed to read moisture. Skipping watering check.")
                if self.system_manager:
                    self.system_manager.add_error("moisture_read")
                return

            self.log_manager.log(f"Soil moisture level: {self.current_moisture:.2f}%")

            if self.current_moisture < self.MOISTURE_THRESHOLD:
                self.log_manager.log(f"Moisture below threshold ({self.MOISTURE_THRESHOLD}%)")
                if self.auto_watering:
                    if (self.watering_cycles < self.WATERING_MAX_CYCLES and 
                        self.water_tank.get_capacity() > 0 and 
                        not self.watering_cycle_pause_flag):
                        self.log_manager.log("Starting watering")
                        await self.trigger_watering()
                    else:
                        self.log_manager.log("Cannot start watering")
                        await self.handle_watering_limits()
                else:
                    self.log_manager.log("Automated watering deactivated")
            else:
                self.log_manager.log("Soil moisture is okay.")
                self.watering_cycles = 0
            self.log_manager.log("Moisture and watering status check completed")

    async def trigger_watering(self):
        if not self.is_watering:
            self.log_manager.log(f"Manual watering triggered for {self.WATERING_DURATION} seconds.")
            await self.control_pump(self.WATERING_DURATION)
        else:
            self.log_manager.log("Watering already in progress. Please wait.")

    async def handle_watering_limits(self):
        if self.watering_cycles >= self.WATERING_MAX_CYCLES:
            self.log_manager.log(f"Max watering cycles [{self.watering_cycles}/{self.WATERING_MAX_CYCLES}] reached. Pausing watering...")
            self.watering_cycles = 0
            self.watering_cycle_pause_flag = True
            self.watering_pause_start_time = utime.ticks_ms()
        elif self.water_tank.get_capacity() <= 0:
            self.log_manager.log("Water tank empty. Pausing automated watering. Refill water tank!")

    def update_status(self):
        if self.watering_cycle_pause_flag:
            if utime.ticks_diff(utime.ticks_ms(), self.watering_pause_start_time) >= self.WATERING_PAUSE_DURATION * 1000:
                self.watering_cycle_pause_flag = False
                self.log_manager.log("Watering cycle pause finished.")

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