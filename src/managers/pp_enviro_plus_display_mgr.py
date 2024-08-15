import asyncio
import uasyncio
import gc
import utime


class PicoEnviroPlusDisplayMgr:
    def __init__(self, enviro_plus, log_mgr, data_mgr, m5_watering_unit, system_mgr):
        self.enviro_plus = enviro_plus
        self.log_mgr = log_mgr
        self.data_mgr = data_mgr
        self.m5_watering_unit = m5_watering_unit
        self.system_mgr = system_mgr
        self.display = enviro_plus.display
        
        # Initialize display constants
        self.DISPLAY_WIDTH, self.DISPLAY_HEIGHT = self.display.get_bounds()
        self.setup_colors()
        
        self.display_backlight_on = True
        self.display_modes = ["Sensor", "Watering", "Log", "System"]
        self.current_mode_index = 1  # Start with Watering mode
        self.enviro_plus.display_mode = self.display_modes[self.current_mode_index]
        
        # Log settings
        self.log_speed = 1
        self.log_scroll_position = 0
        self.line_height = 16
        self.button_label_height = 20  # Height of the button label area
        
        # Calculate available display height for logs
        self.log_display_height = self.DISPLAY_HEIGHT - 30 - self.button_label_height  # 30 for title
        self.lines_per_screen = self.log_display_height // self.line_height
        
        # Moisture history
        self.moisture_history = []
        self.history_limit = 100
        
        # Button configuration
        self.button_config = {
            "Sensor": {
                "A": (self.toggle_backlight, "Backlight"),
                "B": (self.read_all_sensors, "Update"),
                "X": (self.cycle_display_mode, "Next"),
                "Y": (self.update_uv_index, "UV-Index")
            },
            "Watering": {
                "A": (self.toggle_backlight, "Backlight"),
                "B": (self.reset_water_tank, "Reset tank"),
                "X": (self.cycle_display_mode, "Next"),
                "Y": (self.trigger_watering, "Water Now")
            },
            "Log": {
                "A": (self.toggle_backlight, "Backlight"),
                "B": (self.clear_logs, "Clear logs"),
                "X": (self.cycle_display_mode, "Next"),
                "Y": (self.clear_logs, "Clear logs")
            },
            "System": {
                "A": (self.toggle_backlight, "Backlight"),
                "B": (self.reset_wifi, "Reset WiFi"),
                "X": (self.cycle_display_mode, "Next"),
                "Y": (self.reset_mqtt, "Reset MQTT")
            }
        }

    def setup_colors(self):
        self.WHITE = self.display.create_pen(255, 255, 255)
        self.BLACK = self.display.create_pen(0, 0, 0)
        self.RED = self.display.create_pen(255, 0, 0)
        self.GREEN = self.display.create_pen(0, 255, 0)
        self.BLUE = self.display.create_pen(0, 0, 255)
        self.CYAN = self.display.create_pen(0, 255, 255)
        self.MAGENTA = self.display.create_pen(200, 0, 200)
        self.YELLOW = self.display.create_pen(200, 200, 0)
        self.GREY = self.display.create_pen(75, 75, 75)

    def setup_display(self, config):
        self.display.set_font("sans")
        self.display.set_thickness(2)
        self.enviro_plus.led.set_rgb(255, 0, 0)
        self.display.set_backlight(config.ENVIRO_PLUS_DISPLAY_BRIGHTNESS)
        self.clear_display()
        self.display.set_pen(self.RED)
        self.display.text("Initializing...", 0, 0, self.DISPLAY_WIDTH, scale=2)
        self.display.update()

    def clear_display(self):
        self.display.set_pen(self.BLACK)
        self.display.clear()
        
    def toggle_backlight(self):
        self.display_backlight_on = not self.display_backlight_on
        self.display.set_backlight(0.8 if self.display_backlight_on else 0)

    def cycle_display_mode(self):
        self.current_mode_index = (self.current_mode_index + 1) % len(self.display_modes)
        self.enviro_plus.display_mode = self.display_modes[self.current_mode_index]
        self.log_mgr.log(f"Switched to {self.enviro_plus.display_mode} mode")
        return True  # Indicate that the mode has changed

    def reset_water_tank(self):
        self.enviro_plus.reset_water_tank_capacity()
        self.log_mgr.log("Water tank capacity reset")

    async def trigger_watering(self):
        self.log_mgr.log("Manual watering triggered")
        await self.m5_watering_unit.trigger_watering()

    # async def handle_button_press(self, button):
    #     if self.enviro_plus.display_mode in self.button_config and button in self.button_config[self.enviro_plus.display_mode]:
    #         action, _ = self.button_config[self.enviro_plus.display_mode][button]
    #         if action == self.trigger_watering:
    #             await self.trigger_watering()
    #         elif action == self.cycle_display_mode:
    #             self.cycle_display_mode()
    #         else:
    #             action()

    def draw_button_labels(self):
        self.display.set_pen(self.WHITE)
        self.display.set_font("bitmap6")
        scale = 1

        # Draw top line
        self.display.line(0, 20, self.DISPLAY_WIDTH, self.button_label_height, 1)

        # Draw bottom line
        self.display.line(0, self.DISPLAY_HEIGHT - (self.button_label_height + 1), self.DISPLAY_WIDTH, self.DISPLAY_HEIGHT - (self.button_label_height + 1), 1)

        for button, (_, label) in self.button_config[self.enviro_plus.display_mode].items():
            if button == 'A' and label:
                self.display.text(label, 5, 5, scale=scale)
            elif button == 'X' and label:
                text_width = self.display.measure_text(label, scale=scale)
                self.display.text(label, self.DISPLAY_WIDTH - text_width - 5, 5, scale=scale)
            elif button == 'B' and label:
                self.display.text(label, 5, self.DISPLAY_HEIGHT - 15, scale=scale)
            elif button == 'Y' and label:
                text_width = self.display.measure_text(label, scale=scale)
                self.display.text(label, self.DISPLAY_WIDTH - text_width - 5, self.DISPLAY_HEIGHT - 15, scale=scale)
                
    def draw_display_mode_title(self, title):
        # Clear the display
        self.display.set_pen(self.BLACK)
        self.display.clear()

        # Display centered title
        title_scale = 2.5
        title_width = self.display.measure_text(title, scale=title_scale)
        title_x = (self.DISPLAY_WIDTH - title_width) // 2
        self.display.set_pen(self.WHITE)
        self.display.text(title, title_x, 5, scale=title_scale)

    # Placeholder methods for new button actions
    def read_all_sensors(self):
        self.log_mgr.log("Reading all sensors")
        # Implement sensor reading logic

    def update_uv_index(self):
        self.log_mgr.log("Updating UV Index")
        # Implement UV Index update logic

    def reset_wifi(self):
        self.log_mgr.log("Resetting WiFi")
        # Implement WiFi reset logic

    def reset_mqtt(self):
        self.log_mgr.log("Resetting MQTT")
        # Implement MQTT reset logic
        
    async def update_sensor_display(self, temperature, humidity, pressure, lux, gas, mic):
        self.draw_display_mode_title("Sensors")
        
        # Display sensor data
        y_offset = 35
        
        # Temperature display with min and max
        self.display.set_pen(self.GREY)
        self.display.rectangle(0, y_offset, self.DISPLAY_WIDTH, 60)
        
        if temperature > 28:
            self.display.set_pen(self.RED)
        elif temperature < 10:
            self.display.set_pen(self.CYAN)
        else:
            self.display.set_pen(self.GREEN)
        
        self.display.text(f"{temperature:.1f}C", 5, y_offset + 5, scale=3)
        
        self.display.set_pen(self.CYAN)
        self.display.text(f"min {self.enviro_plus.min_temperature:.1f}", 155, y_offset + 5, scale=2)
        self.display.set_pen(self.RED)
        self.display.text(f"max {self.enviro_plus.max_temperature:.1f}", 155, y_offset + 30, scale=2)
        
        y_offset += 70
        
        self.display.set_pen(self.WHITE)
        self.display.text(f"Humidity: {humidity:.0f}%", 5, y_offset, scale=2)
        y_offset += 25
        self.display.text(f"Pressure: {pressure:.0f}hPa", 5, y_offset, scale=2)
        y_offset += 25
        self.display.text(f"Light: {lux:.0f} lux", 5, y_offset, scale=2)
        y_offset += 25
        self.display.text(f"Gas: {gas:.0f}", 5, y_offset, scale=2)
        y_offset += 25
        self.display.text(f"Mic: {mic}", 5, y_offset, scale=2)
        
        self.draw_button_labels()
        self.display.update()

    async def update_watering_display(self, watering_unit_data):
        # Clear the display
        self.draw_display_mode_title("H²O")
        
        # Display watering data
        y_offset = 35
        self.display.text(f"Moisture: {watering_unit_data['moisture']:.1f}%", 5, y_offset, scale=2)
        y_offset += 30
        
        # Water tank capacity bar graph
        max_capacity = 1400
        bar_width = 20
        bar_height = 100
        fill_height = int((watering_unit_data['water_left'] / max_capacity) * bar_height)
        bar_x = 5
        bar_y = y_offset
        
        self.display.set_pen(self.WHITE)
        self.display.rectangle(bar_x, bar_y, bar_width, bar_height)
        self.display.set_pen(self.BLUE)
        self.display.rectangle(bar_x, bar_y + (bar_height - fill_height), bar_width, fill_height)
        
        self.display.set_pen(self.WHITE)
        self.display.text(f"Water left: {watering_unit_data['water_left']:.0f}ml", bar_x + 30, bar_y, scale=2)
        percentage = (watering_unit_data['water_left'] / max_capacity) * 100
        self.display.text(f"({percentage:.0f}%)", bar_x + 30, bar_y + 25, scale=2)
        
        y_offset += bar_height + 10
        self.display.text(f"Is watering: {'Yes' if watering_unit_data['is_watering'] else 'No'}", 5, y_offset, scale=2)
        y_offset += 30
        self.display.text(f"Cycles: {watering_unit_data['watering_cycles']}/{watering_unit_data['watering_cycles_configured']}", 5, y_offset, scale=2)
        
        self.draw_button_labels()
        self.display.update()

    async def update_log_display(self):
        self.clear_display()
        self.draw_display_mode_title("Logs")
        
        self.display.set_pen(self.WHITE)
        self.display.set_font("bitmap6")
        scale = 1.5

        logs = self.log_mgr.get_logs()
        total_logs = len(logs)
        
        start_index = max(0, total_logs - self.lines_per_screen)
        visible_logs = logs[start_index:]

        y_offset = 30  # Start below the title

        for log in visible_logs:
            self.display.text(log, 5, y_offset, self.DISPLAY_WIDTH - 10, scale=scale)
            y_offset += self.line_height
            
        self.draw_button_labels()
        self.display.update()

    async def continuous_log_update(self):
        try:
            while self.enviro_plus.display_mode == "Log":
                await self.update_log_display()
                await uasyncio.sleep(1)  # Update every second
        except uasyncio.CancelledError:
            # Perform any necessary cleanup
            await self.update_log_display()  # Final update before exiting
            raise  # Re-raise the CancelledError to properly handle task cancellation


    def clear_logs(self):
        self.log_mgr.clear_logs()
        self.log_mgr.log("Logs cleared")

    def toggle_log_speed(self):
        self.log_speed = 3 if self.log_speed == 1 else 1
        self.log_mgr.log(f"Log speed set to {self.log_speed}")

    async def scroll_logs(self):
        while self.enviro_plus.display_mode == "Log":
            total_logs = len(self.log_mgr.get_logs())
            self.log_scroll_position = (self.log_scroll_position + self.log_speed) % max(1, total_logs - self.lines_per_screen + 1)
            await self.update_log_display()
            await asyncio.sleep(0.5)  # Adjust for smooth scrolling

    async def update_system_display(self, system_data):
        self.draw_display_mode_title("System")
        
        # Display system data
        y_offset = 35
        self.display.text(f"CPU Temp: {system_data['chip_temperature']:.1f}C", 5, y_offset, scale=2)
        y_offset += 25
        self.display.text(f"CPU Freq: {system_data['cpu_frequency']/1000000:.0f}MHz", 5, y_offset, scale=2)
        y_offset += 25
        self.display.text(f"CPU Usage: {system_data['cpu_usage']:.1f}%", 5, y_offset, scale=2)
        y_offset += 25
        self.display.text(f"RAM Usage: {system_data['ram_usage']:.1f}%", 5, y_offset, scale=2)
        y_offset += 25
        self.display.text(f"Uptime: {system_data['uptime']}", 5, y_offset, scale=2)
        
        self.draw_button_labels()
        self.display.update()

    def update_moisture_history(self, current_moisture):
        self.moisture_history.append(current_moisture)
        if len(self.moisture_history) > self.history_limit:
            self.moisture_history.pop(0)

    def get_moisture_stats(self):
        if not self.moisture_history:
            return 0, 0, 0
        return min(self.moisture_history), max(self.moisture_history), sum(self.moisture_history) / len(self.moisture_history)

    def cleanup(self):
        self.clear_display()
        self.display.set_backlight(0)
        gc.collect()