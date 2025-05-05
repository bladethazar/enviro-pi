class WaterTank:
    def __init__(self, capacity, log_mgr) -> None:
        self.log_manager = log_mgr
        self.WATER_TANK_FULL_CAPACITY = capacity
        self.water_tank_capacity = capacity
        
    def reduce_capacity(self, water_used):
        self.water_tank_capacity = max(0, self.water_tank_capacity - water_used)

    def reset_capacity(self):
        self.log_manager.log("Reset Water tank capacity")
        self.water_tank_capacity = self.WATER_TANK_FULL_CAPACITY
        
    def get_capacity(self):
        return self.water_tank_capacity
    
    def set_capacity(self, capacity):
        self.water_tank_capacity = capacity
        self.log_manager.log(f"Set water_tank_capacity to: {capacity}")
    