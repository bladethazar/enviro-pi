import asyncio
import uasyncio
import gc
import utime


class PicoEnviroPlusDisplayMgr:
    def __init__(self, config, enviro_plus, log_mgr, data_mgr, m5_watering_unit, system_mgr):
        self.enviro_plus = enviro_plus
        self.log_mgr = log_mgr
        self.data_mgr = data_mgr
        self.m5_watering_unit = m5_watering_unit
        self.system_mgr = system_mgr
        self.display = enviro_plus.display
        self.max_water_tank_capacity = config.WATER_TANK_FULL_CAPACITY
        
        # Initialize display constants
        self.DISPLAY_WIDTH, self.DISPLAY_HEIGHT = self.display.get_bounds()
        self.setup_colors()
        
        self.display_backlight_on = True
        self.display_modes = ["Watering", "Sensor", "System", "Log"]
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
                "A": (self.toggle_auto_watering, "Auto: On/Off"),
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
                "B": (self.clear_system_memory, "Clear Memory"),
                "X": (self.cycle_display_mode, "Next"),
                "Y": (self.initiate_system_restart, "Restart")
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

    # Button functions
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
        self.enviro_plus.reset_water_used_unit_1()
    
    def toggle_auto_watering(self):
        new_status = self.m5_watering_unit.toggle_auto_watering()
        self.log_mgr.log(f"Auto watering {'enabled' if new_status else 'disabled'}")

    async def trigger_watering(self):
        self.log_mgr.log("Manual watering triggered")
        await self.m5_watering_unit.trigger_watering()

    def read_all_sensors(self):
        self.log_mgr.log("Reading all sensors")
        # Implement sensor reading logic

    def update_uv_index(self):
        self.log_mgr.log("Updating UV Index")
        # Implement UV Index update logic

    def clear_system_memory(self):
        self.log_mgr.log("Clearing system memory")
        self.cleanup_display()
        self.display.set_pen(self.YELLOW)
        self.display.text("Clearing memory...", 5, self.DISPLAY_HEIGHT // 2, scale=2)
        self.display.update()
        self.system_mgr.clear_memory()
        utime.sleep(2)  # Allow time for the message to be displayed
        self.update_system_display(self.system_mgr.get_system_data()[0]['system']) 

    def initiate_system_restart(self):
        self.log_mgr.log("System restart initiated")
        self.clear_display()
        self.display.set_pen(self.RED)
        self.display.text("Restarting system...", 5, self.DISPLAY_HEIGHT // 2, scale=2)
        self.display.update()
        utime.sleep(2)  # Allow time for the message to be displayed
        self.system_mgr.restart_system()  # Call the system manager's restart method

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
        
    async def update_sensor_display(self, sensor_data):
        self.draw_display_mode_title("Sensors")
        
        y_offset = 30
        left_column = 5
        right_column = 125
        
        # Environment status indicator
        status_color = self.GREEN if sensor_data['env_status'] == "Optimal" else self.YELLOW
        self.display.set_pen(status_color)
        self.display.circle(left_column + 5, y_offset + 10, 10)
        self.display.text(sensor_data['env_status'], left_column + 25, y_offset, scale=2)
        # Display issues if any
        if sensor_data['env_issues']:
            y_offset += 20
            self.display.set_pen(self.YELLOW)
            self.display.text(f"Issues: {sensor_data['env_issues']}", left_column + 25, y_offset, scale=1.5)

        # Draw line at a consistent position
        y_offset = 55  # Set a fixed y_offset for the line
        self.display.set_pen(self.WHITE)
        self.display.line(0, y_offset, self.DISPLAY_WIDTH, y_offset, 1)
        
        # Temperature display with min and max
        y_offset += 1
        if sensor_data['temperature'] > 28:
            temp_color = self.RED
        elif sensor_data['temperature'] < 10:
            temp_color = self.CYAN
        else:
            temp_color = self.GREEN
            
        self.display.set_pen(self.WHITE)

        
        self.display.set_pen(self.GREY)
        self.display.rectangle(0, y_offset, self.DISPLAY_WIDTH, 30)
        self.display.set_pen(temp_color)
        self.display.text(f"{sensor_data['temperature']:.1f}°C", left_column, y_offset + 5, scale=3)
        self.display.set_pen(self.CYAN)
        self.display.text(f"Min: {self.enviro_plus.min_temperature:.1f}°C", right_column, y_offset, scale=2)
        self.display.set_pen(self.RED)
        self.display.text(f"Max: {self.enviro_plus.max_temperature:.1f}°C", right_column, y_offset + 15, scale=2)
        

        # Other sensor data
        y_offset += 35
        self.display.set_pen(self.WHITE)
        self.display.text(f"Humidity: {sensor_data['humidity']:.1f}%", left_column, y_offset, scale=2)
        
        y_offset += 20
        self.display.text(f"Pressure: {sensor_data['pressure']:.0f} hPa", left_column, y_offset, scale=2)
        
        y_offset += 20
        light_status = sensor_data.get('light_status', 'N/A')
        self.display.text(f"Light: {sensor_data['lux']:.0f} lux", left_column, y_offset, scale=2)
        self.display.text(f"({light_status})", right_column, y_offset, scale=2)
        
        y_offset += 20
        self.display.text(f"Air Quality: {sensor_data['gas_quality']}", left_column, y_offset, scale=2)
        
        y_offset += 20
        bar_x = left_column
        bar_y = y_offset
        bar_width = self.DISPLAY_WIDTH - 2 * left_column
        bar_height = 15
        self.draw_sound_level_bar(sensor_data['mic'], bar_x, bar_y, bar_width, bar_height)

        self.draw_button_labels()
        self.display.update()
        
    def draw_sound_level_bar(self, mic_value, x, y, width, height):
        # Normalize the mic value to a 0-1 range
        # mic_value is now in dB scale from 30 to 120
        normalized = (mic_value - 30) / 90

        # Calculate the fill width
        fill_width = int(normalized * width)

        # Draw the label
        self.display.set_pen(self.WHITE)
        self.display.text("Sound-bar:", x, y - 15, scale=1.5)

        # Draw the empty bar
        self.display.rectangle(x, y, width, height)

        # Fill the bar based on the sound level
        if normalized > 0.66:
            self.display.set_pen(self.RED)
        elif normalized > 0.33:
            self.display.set_pen(self.YELLOW)
        else:
            self.display.set_pen(self.GREEN)
        self.display.rectangle(x, y, fill_width, height)

        # Add tick marks and labels
        self.draw_tick_marks(x, y, width, height)

        # Add dB value at the end of the bar
        self.display.set_pen(self.WHITE)
        db_text = f"{mic_value:.1f}dB"
        text_width = self.display.measure_text(db_text, scale=1.5)
        self.display.text(db_text, x + width - text_width, y + height + 2, scale=1.5)

    def draw_tick_marks(self, x, y, width, height):
        self.display.set_pen(self.WHITE)
        tick_positions = [0, 0.33, 0.66, 1]
        for pos in tick_positions:
            tick_x = x + int(pos * width)
            self.display.line(tick_x, y + height, tick_x, y + height + 5)
            if pos > 0:
                db_value = 30 + pos * 90
                self.display.text(f"{db_value:.0f}", tick_x - 10, y + height + 7, scale=1)

    async def update_watering_display(self, watering_unit_data):
        self.draw_display_mode_title("H²O")
        
        # Water tank capacity bar graph
        bar_width = 20
        bar_height = 180
        fill_height = int((watering_unit_data['water_left'] / self.max_water_tank_capacity) * bar_height)
        bar_x = 5
        bar_y = 35
        
        # Update moisture history
        self.update_moisture_history(watering_unit_data['moisture'])
        min_moisture, max_moisture, _ = self.get_moisture_stats()
        
        self.display.set_pen(self.WHITE)
        self.display.rectangle(bar_x, bar_y, bar_width, bar_height)
        self.display.set_pen(self.BLUE)
        self.display.rectangle(bar_x, bar_y + (bar_height - fill_height), bar_width, fill_height)
        
        # Display watering data
        x_offset = bar_x + bar_width + 10
        y_offset = bar_y
        self.display.set_pen(self.WHITE)
        
        self.display.text(f"Moisture: {watering_unit_data['moisture']:.1f}%", x_offset, y_offset, scale=2)
        y_offset += 20
        
        # Display min and max moisture
        self.display.text(f"Min: {min_moisture:.1f}% | Max: {max_moisture:.1f}%", x_offset, y_offset, scale=1.5)
        y_offset += 25
        
        self.display.line(25, y_offset - 10, self.DISPLAY_WIDTH, y_offset - 10, 1)
        
        self.display.set_pen(self.CYAN)
        auto_status = "ON" if watering_unit_data['auto_watering'] else "OFF"
        self.display.text(f"Auto watering: {auto_status}", x_offset, y_offset, scale=2)
        y_offset += 25
        
        self.display.text(f"Last watered:", x_offset, y_offset, scale=2)
        y_offset += 20
        
        self.display.text(f"-> {watering_unit_data['last_watered']}", x_offset, y_offset, scale=2)
        y_offset += 25
        
        self.display.text(f"Water left:", x_offset, y_offset, scale=2)
        y_offset += 20
        
        percentage = (watering_unit_data['water_left'] / self.max_water_tank_capacity) * 100
        self.display.text(f"-> {watering_unit_data['water_left']:.0f}ml ({percentage:.0f}%)", x_offset, y_offset, scale=2)
        y_offset += 25
        
        self.display.text(f"Cycles: {watering_unit_data['watering_cycles']}/{watering_unit_data['watering_cycles_configured']}", x_offset, y_offset, scale=2)
        
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

    async def update_system_display(self, system_data):
        self.draw_display_mode_title("System")
        
        # Display system data
        y_offset = 35
        self.display.text(f"Uptime: {system_data['uptime']}", 5, y_offset, scale=2)
        y_offset += 25
        self.display.line(0, y_offset - 6, self.DISPLAY_WIDTH, y_offset - 6, 2)
        y_offset += 25
        self.display.text(f"CPU Temp: {system_data['chip_temperature']:.1f}C", 5, y_offset, scale=2)
        y_offset += 25
        self.display.text(f"CPU Freq: {system_data['cpu_frequency']:.2f}MHz", 5, y_offset, scale=2)
        y_offset += 25
        self.display.text(f"CPU Usage: {system_data['cpu_usage']:.1f}%", 5, y_offset, scale=2)
        y_offset += 25
        self.display.text(f"RAM Usage: {system_data['ram_usage']:.1f}%", 5, y_offset, scale=2)
        
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

    def cleanup_display(self):
        self.clear_display()
        gc.collect()