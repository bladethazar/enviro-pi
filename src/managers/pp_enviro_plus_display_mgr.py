import time

class PicoEnviroPlusDisplayMgr:
    def __init__(self, enviro_plus, log_mgr, data_mgr) -> None:
        self.log_mgr = log_mgr
        self.data_mgr = data_mgr
        self.enviro_plus = enviro_plus
        self.enviro_plus_display = enviro_plus.display
        
        # Initialize the display constants
        self.DISPLAY_WIDTH, self.DISPLAY_HEIGHT = self.enviro_plus_display.get_bounds()
        self.WHITE = self.enviro_plus_display.create_pen(255, 255, 255)
        self.BLACK = self.enviro_plus_display.create_pen(0, 0, 0)
        self.RED = self.enviro_plus_display.create_pen(255, 0, 0)
        self.GREEN = self.enviro_plus_display.create_pen(0, 255, 0)
        self.CYAN = self.enviro_plus_display.create_pen(0, 255, 255)
        self.MAGENTA = self.enviro_plus_display.create_pen(200, 0, 200)
        self.YELLOW = self.enviro_plus_display.create_pen(200, 200, 0)
        self.BLUE = self.enviro_plus_display.create_pen(0, 0, 200)
        self.FFT_COLOUR = self.enviro_plus_display.create_pen(255, 0, 255)
        self.GREY = self.enviro_plus_display.create_pen(75, 75, 75)
        
        self.display_backlight_on = True  # Start with backlight on
        self.display_modes = ["Sensor", "Watering", "Log", "Equaliser"]  # Add all your display modes here
        self.current_mode_index = 0
        self.display_mode = self.display_modes[self.current_mode_index]
        
        # Log settings
        self.log_speed = 1  # Default log speed (lines per update)
        self.log_scroll_position = 0
        self.lines_per_screen = 15  # Adjust this based on your font size and display height
        self.line_height = 16 
        self.log_buffer = []
        
        # Initialize historical data tracking for moisture values
        self.min_moisture = float('inf')
        self.max_moisture = float('-inf')
        self.history_limit = 100  # Limit for the number of historical data points
        self.moisture_history = []
        
    def setup_display(self, config):
        self.enviro_plus_display.set_font("sans")
        self.enviro_plus_display.set_thickness(2)
        self.enviro_plus.led.set_rgb(255, 0, 0)
        self.enviro_plus_display.set_backlight(config.ENVIRO_PLUS_DISPLAY_BRIGHTNESS)
        self.enviro_plus_display.set_pen(self.RED)
        self.enviro_plus_display.text("waiting for sensors", 0, 0, self.DISPLAY_WIDTH, scale=3)
        self.enviro_plus_display.update()
        
    
    def update_sensor_display(self, corrected_temperature, corrected_humidity, pressure_hpa, lux, gas):
        # Clear the display and set the background
        self.enviro_plus_display.set_pen(self.BLACK)
        self.enviro_plus_display.clear()
        self.enviro_plus.adcfft.update()

        # Display the title
        title_scale = 2.5  # Scale for the title
        title = "Sensor Mode"
        title_width = self.enviro_plus_display.measure_text(title, scale=title_scale)
        self.enviro_plus_display.set_pen(self.WHITE)
        self.enviro_plus_display.text(title, (self.DISPLAY_WIDTH - title_width) // 2, 5, scale=title_scale)
        self.enviro_plus_display.line(0, 25, self.DISPLAY_WIDTH, 25, 1)  # Line below the title

        x_offset = 175
        y_offset = 30  # Start y_offset below the title and line

        # Draw the top box (temperature)
        self.enviro_plus_display.set_pen(self.GREY)
        self.enviro_plus_display.rectangle(0, y_offset, self.DISPLAY_WIDTH, 60)

        # Set the pen color based on the temperature
        if corrected_temperature > 28:
            self.enviro_plus_display.set_pen(self.RED)
        elif corrected_temperature < 10:
            self.enviro_plus_display.set_pen(self.CYAN)
        else:
            self.enviro_plus_display.set_pen(self.GREEN)

        # Display the temperature
        self.enviro_plus_display.text(f"{corrected_temperature:.1f}C", 5, y_offset + 5, scale=3)
        
        text_scale = 2

        # Display min and max temperatures
        self.enviro_plus_display.set_pen(self.CYAN)
        self.enviro_plus_display.text(f"min {self.enviro_plus.min_temperature:.1f}", x_offset - 20, y_offset + 5, scale=text_scale)
        self.enviro_plus_display.set_pen(self.RED)
        self.enviro_plus_display.text(f"max {self.enviro_plus.max_temperature:.1f}", x_offset - 20, y_offset + 30, scale=text_scale)

        # Adjust y_offset for the next section
        y_offset += 70

        # Draw the first column of sensor data
        self.enviro_plus_display.set_pen(self.WHITE)
        self.enviro_plus_display.text(f"Hum: {corrected_humidity:.0f}%", 5, y_offset, scale=text_scale)
        y_offset += 35
        self.enviro_plus_display.text(f"hPa: {pressure_hpa:.0f}", 5, y_offset, scale=text_scale)
        y_offset += 35
        self.enviro_plus_display.text(f"Lux: {lux}", 5, y_offset, scale=text_scale)
        y_offset += 35
        self.enviro_plus_display.text(f"Mic: {self.enviro_plus.adcfft}", 5, y_offset, scale=text_scale)

        # Reset y_offset for the second column
        y_offset = 100

        # Draw the second column of sensor descriptions
        self.enviro_plus_display.text(f" {self.data_mgr.describe_humidity(corrected_humidity)}", x_offset, y_offset, scale=text_scale)
        y_offset += 35
        self.enviro_plus_display.text(f" {self.data_mgr.describe_pressure(pressure_hpa)}", x_offset, y_offset, scale=text_scale)
        y_offset += 35
        self.enviro_plus_display.text(f" {self.data_mgr.describe_light(lux)}", x_offset, y_offset, scale=text_scale)
        y_offset += 35
        self.enviro_plus_display.text(f"???", x_offset, y_offset, scale=text_scale)

        # Draw the gas level bar
        if self.enviro_plus.min_gas != self.enviro_plus.max_gas:
            gas_normalized = (gas - self.enviro_plus.min_gas) / (self.enviro_plus.max_gas - self.enviro_plus.min_gas)
            gas_height = round(gas_normalized * self.DISPLAY_HEIGHT)

            # Set LED and pen color based on gas level
            if gas_normalized < self.enviro_plus.GAS_ALERT_TRESHOLD:
                self.enviro_plus.led.set_rgb(255, 0, 0)  # Red for alert
                self.enviro_plus_display.set_pen(self.RED)
            else:
                self.enviro_plus_display.set_pen(self.GREEN)

            # Draw the gas bar
            self.enviro_plus_display.rectangle(236, self.DISPLAY_HEIGHT - gas_height, 10, gas_height)
            self.enviro_plus_display.set_pen(self.WHITE)
            self.enviro_plus_display.text("Gas", 175, 225, scale=text_scale)

        # Update the display with all the changes
        self.enviro_plus_display.update()
        
    def update_watering_display(self, m5_watering_unit_data):
        # Clear the display and set the background
        self.enviro_plus_display.set_pen(self.BLACK)
        self.enviro_plus_display.clear()

        # Display the title
        title_scale = 2.5  # Scale for the title
        title = "Watering Mode"
        title_width = self.enviro_plus_display.measure_text(title, scale=title_scale)
        self.enviro_plus_display.set_pen(self.WHITE)
        self.enviro_plus_display.text(title, (self.DISPLAY_WIDTH - title_width) // 2, 5, scale=title_scale)
        self.enviro_plus_display.line(0, 25, self.DISPLAY_WIDTH, 25, 1)  # Line below the title

        x_offset = 175
        y_offset = 30  # Start y_offset below the title and line

        # Data from watering unit
        current_moisture = m5_watering_unit_data['moisture']
        water_left = m5_watering_unit_data['water_left']
        water_used = m5_watering_unit_data['water_used']
        watering_cycles = m5_watering_unit_data['watering_cycles']
        watering_cycles_configured = m5_watering_unit_data['watering_cycles_configured']

        # Update historical moisture values
        self.moisture_history.append(current_moisture)
        if len(self.moisture_history) > self.history_limit:
            self.moisture_history.pop(0)
        self.min_moisture = min(self.moisture_history)
        self.max_moisture = max(self.moisture_history)

        # Draw the top box (moisture)
        self.enviro_plus_display.set_pen(self.GREY)
        self.enviro_plus_display.rectangle(0, y_offset, self.DISPLAY_WIDTH, 70)

        # Add "Soil Moisture" label
        self.enviro_plus_display.set_pen(self.WHITE)
        self.enviro_plus_display.text("Soil Moisture", 5, y_offset + 5, scale=2)

        # Set the pen color based on the moisture level
        if current_moisture > 80:
            self.enviro_plus_display.set_pen(self.BLUE)
        elif current_moisture < 20:
            self.enviro_plus_display.set_pen(self.RED)
        else:
            self.enviro_plus_display.set_pen(self.GREEN)

        # Display the moisture
        self.enviro_plus_display.text(f"{current_moisture:.1f}%", 5, y_offset + 25, scale=3)

        text_scale = 2

        # Display min and max moisture
        self.enviro_plus_display.set_pen(self.RED)
        self.enviro_plus_display.text(f"min {self.min_moisture:.1f}", x_offset - 20, y_offset + 25, scale=text_scale)
        self.enviro_plus_display.set_pen(self.BLUE)
        self.enviro_plus_display.text(f"max {self.max_moisture:.1f}", x_offset - 20, y_offset + 50, scale=text_scale)

        # Adjust y_offset for the next section
        y_offset += 80

        # Draw the water capacity bar graph
        max_capacity = 1400
        bar_width = 20
        bar_height = 100
        fill_height = int((water_left / max_capacity) * bar_height)
        bar_x = 5
        bar_y = y_offset

        # Draw the bar outline
        self.enviro_plus_display.set_pen(self.WHITE)
        self.enviro_plus_display.rectangle(bar_x, bar_y, bar_width, bar_height)

        # Fill the bar
        self.enviro_plus_display.set_pen(self.BLUE)
        self.enviro_plus_display.rectangle(bar_x, bar_y + (bar_height - fill_height), bar_width, fill_height)

        # Display the water capacity percentage
        percentage = (water_left / max_capacity) * 100
        self.enviro_plus_display.set_pen(self.WHITE)
        self.enviro_plus_display.text(f"Water Left:", bar_x + 30, bar_y, scale=text_scale)
        self.enviro_plus_display.text(f"{water_left:.0f}ml ({percentage:.0f}%)", bar_x + 30, bar_y + 25, scale=2)

        # Adjust y_offset for the next section
        y_offset = bar_y + bar_height + 10

        # Display Water Used
        self.enviro_plus_display.text("Reset capacity >>>", 50, y_offset, scale=text_scale)
        # self.enviro_plus_display.text(f"{water_used:.0f} ml", 5, y_offset + 25, scale=2)
        # y_offset += 60

        # # Display Watering Status
        # watering_status_text = f"Watering: {'Yes' if m5_watering_unit_data['is_watering'] else 'No'}"
        # self.enviro_plus_display.text(watering_status_text, 5, y_offset, scale=text_scale)
        # y_offset += 30

        # # Display Watering Cycles
        # watering_cycles_text = f"Cycles: {watering_cycles} / {watering_cycles_configured}"
        # self.enviro_plus_display.text(watering_cycles_text, 5, y_offset, scale=text_scale)

        # Update the display with all the changes
        self.enviro_plus_display.update()
            
    def update_equalizer_display(self):
        
        def graphic_equaliser():
            m_arr = [0 for _ in range(16)]
            i = 0

            self.enviro_plus.adcfft.update()
            m = 0
            for x in range(5, 240):
                v = self.enviro_plus.adcfft.get_scaled(x, 144)
                m = max(m, v)
                v = min(239, v)
                v = 239 - v
                self.enviro_plus_display.line(x - 5, v, x - 5, 239)
            m_arr[i] = min(255, m)
            i += 1
            if i >= len(m_arr):
                i = 0
            ms = int(sum(m_arr) / len(m_arr))
            self.enviro_plus.led.set_rgb(0, ms, 0)
            
        self.enviro_plus_display.set_pen(self.BLACK)
        self.enviro_plus_display.clear()
        self.enviro_plus_display.set_pen(self.FFT_COLOUR)
        self.enviro_plus_display.text("mic", 10, 20, self.DISPLAY_WIDTH, scale=1.2)
        graphic_equaliser()
        self.enviro_plus_display.update()
        
    def update_log_display(self):
        self.enviro_plus_display.set_pen(self.BLACK)
        self.enviro_plus_display.clear()
        self.enviro_plus_display.set_pen(self.WHITE)

        # Set font and calculate lines per screen
        self.enviro_plus_display.set_font("bitmap6")
        scale = 1.5  # Increase text size to make it more readable
        self.line_height = int(16 * scale)  # Adjust this based on the new scale
        self.lines_per_screen = (self.DISPLAY_HEIGHT - 30) // self.line_height  # Leave some margin

        # Display title
        title_scale = 2.5  # Larger scale for the title
        title = "Log Mode"
        title_width = self.enviro_plus_display.measure_text(title, scale=title_scale)
        self.enviro_plus_display.text(title, (self.DISPLAY_WIDTH - title_width) // 2, 5, scale=title_scale)
        self.enviro_plus_display.line(0, 25, self.DISPLAY_WIDTH, 25, 1)

        # Get logs and calculate total lines
        log_lines = self.log_mgr.get_logs()
        total_lines = len(log_lines)

        # Calculate which lines to display with smooth scrolling
        self.log_scroll_position = (self.log_scroll_position + self.log_speed) % max(1, total_lines - self.lines_per_screen + 1)
        start_index = max(0, int(self.log_scroll_position))
        end_index = min(total_lines, start_index + self.lines_per_screen)

        # Clear the log display area
        self.enviro_plus_display.set_pen(self.BLACK)
        self.enviro_plus_display.rectangle(0, 30, self.DISPLAY_WIDTH, self.DISPLAY_HEIGHT - 30)
        # Display log lines from top to bottom with a delay
        y_offset = 30  # Start display from below the title
        
        # Initialize a set to keep track of seen lines
        # TODO: remove startup log after certain uptime
        seen_lines = set(self.log_buffer)

        for line in log_lines[start_index:end_index]:
            truncated_line = line[:30]  # Truncate long lines (adjusted for larger text)
            
            if truncated_line not in seen_lines:
                self.store_buffered_log_line(truncated_line)
                seen_lines.add(truncated_line)  # Add the new line to the set of seen lines
        
        for line in self.log_buffer:
            self.enviro_plus_display.set_pen(self.WHITE)
            self.enviro_plus_display.text(line, 5, y_offset, self.DISPLAY_WIDTH, scale=scale)
            y_offset += self.line_height
            self.enviro_plus_display.update()  # Update the display after each line
            time.sleep(1)  # Delay between lines to create a gradual scrolling effect
        
        # for line in log_lines[start_index:end_index]:
        #     truncated_line = line[:30]  # Truncate long lines (adjusted for larger text)
        #     self.store_buffered_log_line(truncated_line)
        #     self.display.set_pen(self.WHITE)
        #     self.display.text(truncated_line, 5, y_offset, self.DISPLAY_WIDTH - 10, scale=scale)
        #     y_offset += self.line_height
        #     self.display.update()  # Update the display after each line
        #     time.sleep(1)  # Delay between lines to create a gradual scrolling effect

        # Ensure the display is fully updated
        self.enviro_plus_display.update()

        # Debug print
        # print(f"Displayed lines {start_index} to {end_index} out of {total_lines}")
        # print(f"Scroll position: {self.log_scroll_position}")
        
    def set_log_speed(self, speed):
        """Set the logging speed (lines per update)"""
        self.log_speed = max(1, min(speed, self.lines_per_screen // 2))
        
    def store_buffered_log_line(self, message):
        self.log_buffer.append(message)
        self.log_buffer = self.log_buffer[-100:]  # Keep the last 100 logs
        self.log_mgr.log(message)