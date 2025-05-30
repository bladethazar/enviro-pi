import asyncio
import uasyncio
import gc
import utime


class PicoEnviroPlusDisplayMgr:
    def __init__(self, config, enviro_plus, log_mgr, data_mgr, system_mgr):
        self.enviro_plus = enviro_plus
        self.log_mgr = log_mgr
        self.data_mgr = data_mgr
        self.system_mgr = system_mgr
        self.display = enviro_plus.display
        
        # Initialize display constants
        self.DISPLAY_WIDTH, self.DISPLAY_HEIGHT = self.display.get_bounds()
        self.setup_colors()
        
        self.display_backlight_on = True
        self.display_modes = ["Sensor", "Weather", "System", "Log"]
        self.current_mode_index = 0  # Start with Sensor mode
        self.enviro_plus.display_mode = self.display_modes[self.current_mode_index]
        
        # Log settings
        self.log_speed = 1
        self.log_scroll_position = 0
        self.line_height = 16
        self.button_label_height = 20  # Height of the button label area
        
        # Calculate available display height for logs
        self.log_display_height = self.DISPLAY_HEIGHT - 30 - self.button_label_height  # 30 for title
        self.lines_per_screen = self.log_display_height // self.line_height
        
        # Weather update cache
        self.last_weather_update_time = 0
        self.cached_weather_data = None
        
        # Button configuration
        self.button_config = {
            "Sensor": {
                "A": (lambda: self.cycle_display_mode(False), "Previous"),
                "B": (self.toggle_backlight, "Backlight"),
                "X": (lambda: self.cycle_display_mode(True), "Next"),
                "Y": (self.clear_system_memory, "Clear Memory")
            },
            "Weather": {
                "A": (lambda: self.cycle_display_mode(False), "Previous"),
                "B": (self.toggle_backlight, "Backlight"),
                "X": (lambda: self.cycle_display_mode(True), "Next"),
                "Y": (self.update_uv_index, "UV-Index")
            },
            "Log": {
                "A": (lambda: self.cycle_display_mode(False), "Previous"),
                "B": (self.toggle_backlight, "Backlight"),
                "X": (lambda: self.cycle_display_mode(True), "Next"),
                "Y": (self.clear_logs, "Clear logs")
            },
            "System": {
                "A": (lambda: self.cycle_display_mode(False), "Previous"),
                "B": (self.toggle_backlight, "Backlight"),
                "X": (lambda: self.cycle_display_mode(True), "Next"),
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

    def cycle_display_mode(self, direction: bool):
        if direction:
            self.current_mode_index = (self.current_mode_index + 1) % len(self.display_modes)
        else:
            self.current_mode_index = (self.current_mode_index - 1) % len(self.display_modes)
        
        self.enviro_plus.display_mode = self.display_modes[self.current_mode_index]
        self.log_mgr.log(f"Switched to {self.enviro_plus.display_mode} mode")
        return True  # Indicate that the mode has changed
       
    def read_all_sensors(self):
        self.log_mgr.log("Reading all sensors")
        self.log_mgr.log("Not implemented yet")
        # Implement sensor reading logic

    def update_uv_index(self):
        self.log_mgr.log("Updating UV Index")
        self.log_mgr.log("Not implemented yet")
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
        
    def format_weather_time(self, localtime_str):
        try:
            date_part, time_part = localtime_str.split(" ")
            _, month, day = map(int, date_part.split("-"))
            hour, minute = time_part.split(":")[:2]
            return f"Today, {hour}:{minute}"
        except Exception:
            return localtime_str

    def draw_weather_icon(self, condition, x=5, y=40):
        self.display.set_pen(self.WHITE)

        condition = condition.lower()
        # self.log_mgr.log(f"Condition: {condition}")

        if "sun" in condition:
            self.draw_sun_icon(x, y)
        elif "cloud" in condition and "partly" in condition:
            self.draw_partly_cloudy_icon(x, y)
        elif "cloud" in condition:
            self.draw_cloud_icon(x, y)
        elif "rain" in condition:
            self.draw_rain_icon(x, y)
        elif "snow" in condition:
            self.draw_snow_icon(x, y)
        elif "fog" in condition or "mist" in condition:
            self.draw_fog_icon(x, y)
        else:
            self.draw_unknown_icon(x, y)

    def draw_sun_icon(self, x, y):
        self.display.set_pen(self.YELLOW)
        self.display.circle(x + 20, y + 20, 15)
        self.display.line(x + 20, y, x + 20, y + 40)
        self.display.line(x, y + 20, x + 40, y + 20)

    def draw_cloud_icon(self, x, y):
        self.display.set_pen(self.GREY)
        self.display.circle(x + 15, y + 20, 12)
        self.display.circle(x + 30, y + 20, 14)
        self.display.rectangle(x + 10, y + 20, 30, 10)

    def draw_partly_cloudy_icon(self, x, y):
        self.draw_sun_icon(x, y)
        self.draw_cloud_icon(x + 10, y + 10)

    def draw_rain_icon(self, x, y):
        self.draw_cloud_icon(x, y)
        self.display.set_pen(self.BLUE)
        for dx in [15, 25, 35]:
            self.display.line(x + dx, y + 30, x + dx - 3, y + 38)

    def draw_snow_icon(self, x, y):
        self.draw_cloud_icon(x, y)
        self.display.set_pen(self.CYAN)
        for dx in [15, 25, 35]:
            self.display.line(x + dx, y + 30, x + dx, y + 38)
            self.display.line(x + dx - 3, y + 34, x + dx + 3, y + 34)

    def draw_fog_icon(self, x, y):
        self.draw_cloud_icon(x, y)
        self.display.set_pen(self.WHITE)
        for i in range(3):
            self.display.line(x + 5, y + 30 + (i * 6), x + 35, y + 30 + (i * 6))

    def draw_unknown_icon(self, x, y):
        self.display.set_pen(self.MAGENTA)
        self.display.text("?", x + 15, y + 10, scale=3)
        
    async def update_weather_display(self):

        now = utime.time()
        interval = self.data_mgr.config.WEATHER_UPDATE_INTERVAL_IN_MINUTES * 60

        if (
            self.enviro_plus.display_mode == "Weather" and
            (now - self.last_weather_update_time) >= interval
        ):
            self.log_mgr.log("Fetching weather data...")
            self.cached_weather_data = self.data_mgr.get_weather_data_from_api()
            self.last_weather_update_time = now

        weather = self.cached_weather_data

        if not weather:
            self.display.set_pen(self.RED)
            self.display.text("Weather unavailable.", 5, 40, scale=2)
            self.display.update()
            return

        self.display.set_pen(self.BLACK)
        self.display.clear()
        self.draw_display_mode_title("Weather")

        y = 35
        time_str = self.format_weather_time(weather["localtime"])

        # Display date & location
        self.display.set_pen(self.WHITE)
        self.display.text(f"{weather['location']} - {time_str}", 5, y, scale=2)
        y += 25

        # Show icon if it exists
        self.draw_weather_icon(weather['condition'], x=5, y=y)
        icon_x_offset = 75

        # Show temperature & condition beside the icon
        self.display.set_pen(self.GREEN)
        self.display.text(f"{weather['temp_c']}°C", icon_x_offset, y, scale=3)
        y += 30
        self.display.set_pen(self.WHITE)
        self.display.text(weather['condition'], icon_x_offset, y, scale=2)
        y += 25
        
        # --- HR Line ---
        self.display.set_pen(self.WHITE)
        self.display.line(0, y, self.DISPLAY_WIDTH, y, 1)
        y += 5
        
        # Other readings
        self.display.set_pen(self.WHITE)
        self.display.text(f"Feels like {weather['feelslike_c']}°C", 5, y, scale=2)
        y += 20
        self.display.text(f"Humidity: {weather['humidity']}%", 5, y, scale=2)
        y += 20
        self.display.text(f"Wind: {weather['wind_kph']} km/h {weather['wind_dir']}", 5, y, scale=2)
        y += 20
        self.display.text(f"Pressure: {weather['pressure_mb']} hPa", 5, y, scale=2)

        self.draw_button_labels()
        self.display.update()


        
    async def update_sensor_display(self, sensor_data):
        self.draw_display_mode_title("Sensors")

        left_x = 5
        center_x = self.DISPLAY_WIDTH // 2
        right_x = self.DISPLAY_WIDTH - 100
        y_offset = 30

        # --- Temperature row ---
        if sensor_data['temperature'] > 28:
            temp_color = self.RED
        elif sensor_data['temperature'] < 10:
            temp_color = self.CYAN
        else:
            temp_color = self.GREEN

        self.display.set_pen(self.GREY)
        self.display.rectangle(0, y_offset, self.DISPLAY_WIDTH, 45)

        self.display.set_pen(temp_color)
        self.display.text(f"{sensor_data['temperature']:.1f}°C", left_x, y_offset + 5, scale=4)

        self.display.set_pen(self.CYAN)
        self.display.text(f"Min: {self.enviro_plus.min_temperature:.1f}°C", center_x + 10, y_offset + 2, scale=2)

        self.display.set_pen(self.RED)
        self.display.text(f"Max: {self.enviro_plus.max_temperature:.1f}°C", center_x + 10, y_offset + 20, scale=2)

        y_offset += 50
        self.display.set_pen(self.WHITE)
        self.display.line(0, y_offset, self.DISPLAY_WIDTH, y_offset, 1)

        # --- Humidity row ---
        y_offset += 5
        self.display.set_pen(self.GREY)
        self.display.rectangle(0, y_offset, self.DISPLAY_WIDTH, 35)

        self.display.set_pen(self.WHITE)
        self.display.text(f"Humidity: {sensor_data['humidity']:.1f}%", left_x, y_offset + 5, scale=3)

        y_offset += 40
        self.display.set_pen(self.WHITE)
        self.display.line(0, y_offset, self.DISPLAY_WIDTH, y_offset, 1)

        # --- Other sensor readings ---
        info_scale = 2
        line_gap = 22

        y_offset += 5
        self.display.set_pen(self.WHITE)
        self.display.text(f"Light:", left_x, y_offset, scale=info_scale)
        self.display.text(f"{sensor_data['lux']:.0f} lx", right_x, y_offset, scale=info_scale)

        y_offset += line_gap
        self.display.text(f"Air Qual.:", left_x, y_offset, scale=info_scale)
        self.display.text(f"{sensor_data['gas_quality']}", right_x, y_offset, scale=info_scale)

        y_offset += line_gap
        self.display.text(f"Air Pres.:", left_x, y_offset, scale=info_scale)
        self.display.text(f"{sensor_data['pressure']:.0f} hPa", right_x, y_offset, scale=info_scale)

        y_offset += line_gap
        mic_val = sensor_data.get('mic', 'N/A')
        mic_str = f"{mic_val:.1f} dB" if isinstance(mic_val, (int, float)) else "N/A"
        self.display.text(f"Sound:", left_x, y_offset, scale=info_scale)
        self.display.text(mic_str, right_x, y_offset, scale=info_scale)

        self.draw_button_labels()
        self.display.update()



        

    # async def update_watering_display(self, watering_unit_data, dfr_moisture_sensor_data):
    #     self.draw_display_mode_title("Watering")
    #     # Water tank capacity bar graph
    #     bar_width = 20
    #     bar_height = 180
    #     fill_height = int((watering_unit_data['water_left'] / self.max_water_tank_capacity) * bar_height)
    #     bar_x = 5
    #     bar_y = 35
        
        
    #     self.display.set_pen(self.WHITE)
    #     self.display.rectangle(bar_x, bar_y, bar_width, bar_height)
    #     self.display.set_pen(self.BLUE)
    #     self.display.rectangle(bar_x, bar_y + (bar_height - fill_height), bar_width, fill_height)
        
    #     # Display watering data
    #     x_offset = bar_x + bar_width + 10
    #     y_offset = bar_y
    #     self.display.set_pen(self.WHITE)
        
    #     # Display moisture
    #     self.display.text(f"Moisture Level:", x_offset, y_offset, scale=2)
    #     y_offset += 25
        
    #     self.display.text(f"M5  | {watering_unit_data['moisture']:.1f}%", x_offset, y_offset, scale=2)
    #     y_offset += 20
    #     self.display.text(f"DFR | {dfr_moisture_sensor_data['moisture_percent']:.1f}%", x_offset, y_offset, scale=2)
    #     y_offset += 28
        
    #     self.display.line(25, y_offset - 10, self.DISPLAY_WIDTH, y_offset - 10, 1)
        
    #     self.display.set_pen(self.CYAN)
        
    #     self.display.text(f"M5 Last watered:", x_offset, y_offset, scale=2)
    #     y_offset += 20
        
    #     self.display.text(f"{watering_unit_data['last_watered']}", x_offset, y_offset, scale=2)
    #     y_offset += 30
        
    #     self.display.text(f"M5 Water left:", x_offset, y_offset, scale=2)
    #     y_offset += 20
        
    #     percentage = (watering_unit_data['water_left'] / self.max_water_tank_capacity) * 100
    #     self.display.text(f"{watering_unit_data['water_left']:.0f}ml ({percentage:.0f}%)", x_offset, y_offset, scale=2)
    #     y_offset += 30
        
        
    #     self.draw_button_labels()
    #     self.display.update()

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
        
    def format_uptime(self, uptime_str):
        try:
            parts = uptime_str.split()
            if len(parts) == 2:
                days = int(parts[0])
                h, m, s = map(int, parts[1].split(':'))
            else:
                days = 0
                h, m, s = map(int, parts[0].split(':'))

            formatted = f"{days}d {h}h {m}m {s}s" if days > 0 else f"{h}h {m}m {s}s"
            return formatted
        except Exception:
            return uptime_str



    async def update_system_display(self, system_data):
        self.draw_display_mode_title("System")

        left_x = 5
        right_x = self.DISPLAY_WIDTH // 2 + 10
        y_offset = 35
        label_scale = 2
        value_scale = 3
        line_gap = 22
        small_gap = 5

        # --- Uptime (Label + Large Value in Gray Box) ---
        uptime_str = self.format_uptime(system_data['uptime'])

        box_height = 50
        self.display.set_pen(self.GREY)
        self.display.rectangle(0, y_offset, self.DISPLAY_WIDTH, box_height)

        self.display.set_pen(self.WHITE)
        self.display.text("Uptime:", left_x, y_offset + 2, scale=label_scale)

        self.display.set_pen(self.GREEN)
        self.display.text(uptime_str, left_x, y_offset + 22, scale=value_scale)

        y_offset += box_height + small_gap
        self.display.set_pen(self.WHITE)
        self.display.line(0, y_offset, self.DISPLAY_WIDTH, y_offset, 1)

        # --- Other System Info ---
        y_offset += small_gap
        self.display.text("Voltage:", left_x, y_offset, scale=label_scale)
        self.display.text(f"{system_data['internal_voltage']:.2f} V", right_x, y_offset, scale=label_scale)

        y_offset += line_gap
        self.display.text("CPU Temp:", left_x, y_offset, scale=label_scale)
        self.display.text(f"{system_data['chip_temperature']:.1f}°C", right_x, y_offset, scale=label_scale)

        y_offset += line_gap
        self.display.text("CPU Freq:", left_x, y_offset, scale=label_scale)
        self.display.text(f"{system_data['cpu_frequency']:.2f} MHz", right_x, y_offset, scale=label_scale)

        y_offset += line_gap
        self.display.text("CPU Usage:", left_x, y_offset, scale=label_scale)
        self.display.text(f"{system_data['cpu_usage']:.1f}%", right_x, y_offset, scale=label_scale)

        y_offset += line_gap
        self.display.text("RAM Usage:", left_x, y_offset, scale=label_scale)
        self.display.text(f"{system_data['ram_usage']:.1f}%", right_x, y_offset, scale=label_scale)

        self.draw_button_labels()
        self.display.update()





    def cleanup_display(self):
        self.clear_display()
        gc.collect()