import gc


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
        self.display_modes = ["Overview", "VPD", "Air", "Light", "Sound", "System", "Log"]
        self.current_mode_index = 0
        self.enviro_plus.display_mode = self.display_modes[self.current_mode_index]

        # Layout constants (landscape)
        self.header_height = 20
        self.footer_height = 16
        
        # Log settings
        self.log_speed = 1
        self.log_scroll_position = 0
        self.line_height = 12
        self.button_label_height = 20  # Deprecated, kept for compatibility

        # Calculate available display height for logs
        self.log_display_height = self.DISPLAY_HEIGHT - self.header_height - self.footer_height - 4
        self.lines_per_screen = self.log_display_height // self.line_height
        
        # Button configuration
        self.button_config = {
            "Overview": {
                "A": (lambda: self.cycle_display_mode(False), "Prev"),
                "B": (self.toggle_backlight, "Light"),
                "X": (lambda: self.cycle_display_mode(True), "Next"),
                "Y": (self.reset_sensor_extremes, "Reset")
            },
            "Air": {
                "A": (lambda: self.cycle_display_mode(False), "Prev"),
                "B": (self.toggle_backlight, "Light"),
                "X": (lambda: self.cycle_display_mode(True), "Next"),
                "Y": (self.reset_sensor_extremes, "Reset")
            },
            "VPD": {
                "A": (lambda: self.cycle_display_mode(False), "Prev"),
                "B": (self.toggle_backlight, "Light"),
                "X": (lambda: self.cycle_display_mode(True), "Next"),
                "Y": (self.reset_sensor_extremes, "Reset")
            },
            "Light": {
                "A": (lambda: self.cycle_display_mode(False), "Prev"),
                "B": (self.toggle_backlight, "Light"),
                "X": (lambda: self.cycle_display_mode(True), "Next"),
                "Y": (self.reset_sensor_extremes, "Reset")
            },
            "Sound": {
                "A": (lambda: self.cycle_display_mode(False), "Prev"),
                "B": (self.toggle_backlight, "Light"),
                "X": (lambda: self.cycle_display_mode(True), "Next"),
                "Y": (self.reset_sensor_extremes, "Reset")
            },
            "Log": {
                "A": (lambda: self.cycle_display_mode(False), "Prev"),
                "B": (self.toggle_backlight, "Light"),
                "X": (lambda: self.cycle_display_mode(True), "Next"),
                "Y": (self.clear_logs, "Clear")
            },
            "System": {
                "A": (lambda: self.cycle_display_mode(False), "Prev"),
                "B": (self.toggle_backlight, "Light"),
                "X": (lambda: self.cycle_display_mode(True), "Next"),
                "Y": (self.initiate_system_restart, "Reboot")
            }
        }


    def setup_colors(self):
        self.WHITE = self.display.create_pen(240, 240, 240)
        self.BLACK = self.display.create_pen(0, 0, 0)
        self.RED = self.display.create_pen(180, 80, 80)
        self.GREEN = self.display.create_pen(90, 140, 120)
        self.BLUE = self.display.create_pen(80, 100, 150)
        self.CYAN = self.display.create_pen(80, 130, 140)
        self.MAGENTA = self.display.create_pen(150, 90, 150)
        self.YELLOW = self.display.create_pen(160, 130, 80)
        self.GREY = self.display.create_pen(70, 70, 70)
        self.MODE_ACCENTS = {
            "Overview": self.CYAN,
            "VPD": self.MAGENTA,
            "Air": self.GREEN,
            "Light": self.YELLOW,
            "Sound": self.BLUE,
            "System": self.WHITE,
            "Log": self.GREY
        }

    def setup_display(self, config):
        self.display.set_font("sans")
        self.display.set_thickness(2)
        self.enviro_plus.led.set_rgb(255, 0, 0)
        brightness = getattr(config, "ENVIRO_PLUS_DISPLAY_BRIGHTNESS", 0.8)
        self.display.set_backlight(brightness)
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
        brightness = getattr(self.data_mgr.config, "ENVIRO_PLUS_DISPLAY_BRIGHTNESS", 0.8)
        self.display.set_backlight(brightness if self.display_backlight_on else 0)

    def cycle_display_mode(self, direction: bool):
        if direction:
            self.current_mode_index = (self.current_mode_index + 1) % len(self.display_modes)
        else:
            self.current_mode_index = (self.current_mode_index - 1) % len(self.display_modes)
        
        self.enviro_plus.display_mode = self.display_modes[self.current_mode_index]
        self.log_mgr.log(f"Switched to {self.enviro_plus.display_mode} mode")
        return True  # Indicate that the mode has changed
       
    def reset_sensor_extremes(self):
        self.enviro_plus.min_temperature = float('inf')
        self.enviro_plus.max_temperature = float('-inf')
        self.enviro_plus.min_gas = float('inf')
        self.enviro_plus.max_gas = float('-inf')
        self.log_mgr.log("Sensor extremes reset")

    def clear_system_memory(self):
        self.log_mgr.log("Clearing system memory")
        self.cleanup_display()
        self.display.set_pen(self.YELLOW)
        self.display.text("Clearing memory...", 5, self.DISPLAY_HEIGHT // 2, scale=2)
        self.display.update()
        self.system_mgr.clear_memory()
        utime.sleep(2)  # Allow time for the message to be displayed
        self.update_system_display(self.system_mgr.get_system_data()['system']) 

    def initiate_system_restart(self):
        self.log_mgr.log("System restart initiated")
        self.clear_display()
        self.display.set_pen(self.RED)
        self.display.text("Restarting system...", 5, self.DISPLAY_HEIGHT // 2, scale=2)
        self.display.update()
        utime.sleep(2)  # Allow time for the message to be displayed
        self.system_mgr.restart_system()  # Call the system manager's restart method

    def draw_header(self, title):
        self.display.set_pen(self.BLACK)
        self.display.clear()
        self.display.set_font("sans")
        current_mode = self.enviro_plus.display_mode
        accent = self.MODE_ACCENTS.get(current_mode, self.WHITE)

        modes = self.display_modes
        strip_height = 3
        segment_width = self.DISPLAY_WIDTH // len(modes)
        for idx, mode in enumerate(modes):
            x = idx * segment_width
            width = segment_width if idx < len(modes) - 1 else self.DISPLAY_WIDTH - x
            pen = accent if mode == current_mode else self.GREY
            self.display.set_pen(pen)
            self.display.rectangle(x, 0, width, strip_height)

        self.display.set_pen(accent)
        self.display.text(title, 5, 4, scale=2)
        self.display.line(0, self.header_height, self.DISPLAY_WIDTH, self.header_height, 1)

    def draw_display_mode_title(self, title):
        self.draw_header(title)

    def draw_button_labels(self):
        self.display.set_pen(self.WHITE)
        self.display.set_font("bitmap6")
        mode_labels = self.button_config.get(self.enviro_plus.display_mode, {})
        label_a = mode_labels.get("A", ("", ""))[1]
        label_b = mode_labels.get("B", ("", ""))[1]
        label_x = mode_labels.get("X", ("", ""))[1]
        label_y = mode_labels.get("Y", ("", ""))[1]

        footer_y = self.DISPLAY_HEIGHT - self.footer_height
        self.display.line(0, footer_y, self.DISPLAY_WIDTH, footer_y, 1)
        label_text = f"A:{label_a}  B:{label_b}  X:{label_x}  Y:{label_y}"
        self.display.text(label_text, 2, footer_y + 2, self.DISPLAY_WIDTH - 4, scale=1)
        


        
    async def update_overview_display(self, sensor_data):
        self.draw_display_mode_title("Overview")
        self.display.set_pen(self.WHITE)
        self.display.set_font("bitmap6")

        scale = 2
        line_height = 14
        y_offset = self.header_height + 4

        mic_val = sensor_data.get('mic', None)
        mic_str = f"{mic_val:.1f} dB" if isinstance(mic_val, (int, float)) else "N/A"

        rows = [
            ("Temp", f"{sensor_data['temperature']:.1f}°C"),
            ("RH", f"{sensor_data['humidity']:.1f}% {sensor_data.get('humidity_status', '')}"),
            ("Press", f"{sensor_data['pressure']:.0f} hPa"),
            ("Light", f"{sensor_data['lux']:.0f} lx {sensor_data.get('light_status', '')}"),
            ("Air", f"{sensor_data['gas_quality']}"),
            ("Sound", f"{mic_str} {sensor_data.get('sound_status', '')}")
        ]

        for label, value in rows:
            self.display.text(label, 5, y_offset, scale=scale)
            value_text = value.strip() if value else "N/A"
            value_width = self.display.measure_text(value_text, scale=scale)
            self.display.text(value_text, self.DISPLAY_WIDTH - value_width - 5, y_offset, scale=scale)
            y_offset += line_height

        self.draw_button_labels()
        self.display.update()

    async def update_air_display(self, sensor_data):
        self.draw_display_mode_title("Air")
        self.display.set_font("bitmap6")

        left_x = 5
        right_x = self.DISPLAY_WIDTH - 5
        y_offset = self.header_height + 4
        scale = 2
        line_height = 14

        temp = sensor_data.get("temperature")
        humidity = sensor_data.get("humidity")
        dew_point = sensor_data.get("dew_point")
        pressure = sensor_data.get("pressure")
        gas_quality = sensor_data.get("gas_quality")
        heater_stable = sensor_data.get("heater_stable", True)

        self.display.set_pen(self.WHITE)
        self.display.text("Temp", left_x, y_offset, scale=scale)
        temp_text = f"{temp:.1f}°C" if isinstance(temp, (int, float)) else "N/A"
        temp_width = self.display.measure_text(temp_text, scale=scale)
        self.display.text(temp_text, right_x - temp_width, y_offset, scale=scale)
        y_offset += line_height

        min_temp = self.enviro_plus.min_temperature
        max_temp = self.enviro_plus.max_temperature
        min_text = f"Min {min_temp:.1f}°C" if min_temp != float('inf') else "Min N/A"
        max_text = f"Max {max_temp:.1f}°C" if max_temp != float('-inf') else "Max N/A"
        self.display.set_pen(self.GREY)
        self.display.text(min_text, left_x, y_offset, scale=1)
        max_width = self.display.measure_text(max_text, scale=1)
        self.display.text(max_text, right_x - max_width, y_offset, scale=1)
        y_offset += line_height

        self.display.set_pen(self.WHITE)
        self.display.text("RH", left_x, y_offset, scale=scale)
        humidity_text = f"{humidity:.1f}% {sensor_data.get('humidity_status', '')}" if isinstance(humidity, (int, float)) else "N/A"
        humidity_width = self.display.measure_text(humidity_text, scale=scale)
        self.display.text(humidity_text, right_x - humidity_width, y_offset, scale=scale)
        y_offset += line_height

        self.display.text("Dew Pt", left_x, y_offset, scale=scale)
        dew_text = f"{dew_point:.1f}°C" if isinstance(dew_point, (int, float)) else "N/A"
        dew_width = self.display.measure_text(dew_text, scale=scale)
        self.display.text(dew_text, right_x - dew_width, y_offset, scale=scale)
        y_offset += line_height

        self.display.text("Press", left_x, y_offset, scale=scale)
        pressure_text = f"{pressure:.0f} hPa" if isinstance(pressure, (int, float)) else "N/A"
        pressure_width = self.display.measure_text(pressure_text, scale=scale)
        self.display.text(pressure_text, right_x - pressure_width, y_offset, scale=scale)
        y_offset += line_height

        gas_label = "Gas" if heater_stable else "Gas (warm)"
        self.display.text(gas_label, left_x, y_offset, scale=scale)
        gas_text = f"{gas_quality}" if gas_quality else "N/A"
        gas_width = self.display.measure_text(gas_text, scale=scale)
        self.display.text(gas_text, right_x - gas_width, y_offset, scale=scale)

        self.draw_button_labels()
        self.display.update()

    async def update_vpd_display(self, sensor_data):
        self.draw_display_mode_title("VPD")
        self.display.set_font("bitmap6")
        self.display.set_pen(self.WHITE)

        left_x = 5
        right_x = self.DISPLAY_WIDTH - 5
        y_offset = self.header_height + 4
        scale = 2
        line_height = 16

        vpd = sensor_data.get("vpd")
        vpd_status = sensor_data.get("vpd_status", "N/A")
        temp = sensor_data.get("temperature")
        humidity = sensor_data.get("humidity")
        dew_point = sensor_data.get("dew_point")

        self.display.text("VPD", left_x, y_offset, scale=scale)
        vpd_text = f"{vpd:.2f} kPa" if isinstance(vpd, (int, float)) else "N/A"
        vpd_width = self.display.measure_text(vpd_text, scale=scale)
        self.display.text(vpd_text, right_x - vpd_width, y_offset, scale=scale)
        y_offset += line_height

        self.display.text("Status", left_x, y_offset, scale=scale)
        status_width = self.display.measure_text(vpd_status, scale=scale)
        self.display.text(vpd_status, right_x - status_width, y_offset, scale=scale)
        y_offset += line_height

        self.display.text("Temp", left_x, y_offset, scale=scale)
        temp_text = f"{temp:.1f}°C" if isinstance(temp, (int, float)) else "N/A"
        temp_width = self.display.measure_text(temp_text, scale=scale)
        self.display.text(temp_text, right_x - temp_width, y_offset, scale=scale)
        y_offset += line_height

        self.display.text("RH", left_x, y_offset, scale=scale)
        humidity_text = f"{humidity:.1f}%" if isinstance(humidity, (int, float)) else "N/A"
        humidity_width = self.display.measure_text(humidity_text, scale=scale)
        self.display.text(humidity_text, right_x - humidity_width, y_offset, scale=scale)
        y_offset += line_height

        self.display.text("Dew Pt", left_x, y_offset, scale=scale)
        dew_text = f"{dew_point:.1f}°C" if isinstance(dew_point, (int, float)) else "N/A"
        dew_width = self.display.measure_text(dew_text, scale=scale)
        self.display.text(dew_text, right_x - dew_width, y_offset, scale=scale)

        self.draw_button_labels()
        self.display.update()

    async def update_light_display(self, sensor_data):
        self.draw_display_mode_title("Light")
        self.display.set_font("bitmap6")
        self.display.set_pen(self.WHITE)

        left_x = 5
        right_x = self.DISPLAY_WIDTH - 5
        y_offset = self.header_height + 4
        scale = 2
        line_height = 16

        lux = sensor_data.get("lux")
        light_status = sensor_data.get("light_status", "N/A")

        self.display.text("Lux", left_x, y_offset, scale=scale)
        lux_text = f"{lux:.0f} lx" if isinstance(lux, (int, float)) else "N/A"
        lux_width = self.display.measure_text(lux_text, scale=scale)
        self.display.text(lux_text, right_x - lux_width, y_offset, scale=scale)
        y_offset += line_height

        self.display.text("Status", left_x, y_offset, scale=scale)
        status_width = self.display.measure_text(light_status, scale=scale)
        self.display.text(light_status, right_x - status_width, y_offset, scale=scale)
        y_offset += line_height

        self.display.text("Temp", left_x, y_offset, scale=scale)
        temp = sensor_data.get("temperature")
        temp_text = f"{temp:.1f}°C" if isinstance(temp, (int, float)) else "N/A"
        temp_width = self.display.measure_text(temp_text, scale=scale)
        self.display.text(temp_text, right_x - temp_width, y_offset, scale=scale)
        y_offset += line_height

        self.display.text("RH", left_x, y_offset, scale=scale)
        humidity = sensor_data.get("humidity")
        humidity_text = f"{humidity:.1f}%" if isinstance(humidity, (int, float)) else "N/A"
        humidity_width = self.display.measure_text(humidity_text, scale=scale)
        self.display.text(humidity_text, right_x - humidity_width, y_offset, scale=scale)

        self.draw_button_labels()
        self.display.update()

    async def update_sound_display(self, sensor_data):
        self.draw_display_mode_title("Sound")
        self.display.set_font("bitmap6")
        self.display.set_pen(self.WHITE)

        left_x = 5
        right_x = self.DISPLAY_WIDTH - 5
        y_offset = self.header_height + 4
        scale = 2
        line_height = 16

        mic_val = sensor_data.get('mic', None)
        mic_str = f"{mic_val:.1f} dB" if isinstance(mic_val, (int, float)) else "N/A"
        sound_status = sensor_data.get("sound_status", "N/A")

        self.display.text("Level", left_x, y_offset, scale=scale)
        mic_width = self.display.measure_text(mic_str, scale=scale)
        self.display.text(mic_str, right_x - mic_width, y_offset, scale=scale)
        y_offset += line_height

        self.display.text("Status", left_x, y_offset, scale=scale)
        status_width = self.display.measure_text(sound_status, scale=scale)
        self.display.text(sound_status, right_x - status_width, y_offset, scale=scale)
        y_offset += line_height

        self.display.text("Temp", left_x, y_offset, scale=scale)
        temp = sensor_data.get("temperature")
        temp_text = f"{temp:.1f}°C" if isinstance(temp, (int, float)) else "N/A"
        temp_width = self.display.measure_text(temp_text, scale=scale)
        self.display.text(temp_text, right_x - temp_width, y_offset, scale=scale)

        self.draw_button_labels()
        self.display.update()

    async def update_log_display(self):
        self.draw_display_mode_title("Logs")

        self.display.set_pen(self.WHITE)
        self.display.set_font("bitmap6")
        scale = 1

        logs = self.log_mgr.get_logs()
        total_logs = len(logs)
        
        start_index = max(0, total_logs - self.lines_per_screen)
        visible_logs = logs[start_index:]

        y_offset = self.header_height + 4  # Start below the title

        for log in visible_logs:
            self.display.text(log, 5, y_offset, self.DISPLAY_WIDTH - 10, scale=scale)
            y_offset += self.line_height
            
        self.draw_button_labels()
        self.display.update()

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
        self.display.set_font("bitmap6")

        scale = 2
        line_height = 14
        y_offset = self.header_height + 4

        uptime_str = self.format_uptime(system_data['uptime'])
        self.display.set_pen(self.WHITE)
        self.display.text("Uptime", 5, y_offset, scale=scale)
        uptime_width = self.display.measure_text(uptime_str, scale=scale)
        self.display.text(uptime_str, self.DISPLAY_WIDTH - uptime_width - 5, y_offset, scale=scale)
        y_offset += line_height + 2

        self.display.line(0, y_offset, self.DISPLAY_WIDTH, y_offset, 1)
        y_offset += 4

        col_width = (self.DISPLAY_WIDTH // 2) - 8
        col1_x = 5
        col2_x = self.DISPLAY_WIDTH // 2 + 3

        def draw_row(x, y, label, value):
            self.display.text(label, x, y, scale=scale)
            value_width = self.display.measure_text(value, scale=scale)
            self.display.text(value, x + col_width - value_width, y, scale=scale)

        draw_row(col1_x, y_offset, "Volt", f"{system_data['internal_voltage']:.2f}V")
        draw_row(col2_x, y_offset, "CPU", f"{system_data['chip_temperature']:.1f}°C")
        y_offset += line_height

        draw_row(col1_x, y_offset, "Freq", f"{system_data['cpu_frequency']:.2f}M")
        draw_row(col2_x, y_offset, "CPU%", f"{system_data['cpu_usage']:.1f}%")
        y_offset += line_height

        draw_row(col1_x, y_offset, "RAM%", f"{system_data['ram_usage']:.1f}%")

        self.draw_button_labels()
        self.display.update()





    def cleanup_display(self):
        self.clear_display()
        gc.collect()