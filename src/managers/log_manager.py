import utime

class LogManager:
    def __init__(self):
        self.buffer_size = 15
        self.buffer = []
        self.buffering_enabled = True

    def log(self, message):
        timestamp = utime.localtime()
        formatted_time = "{:02d}:{:02d}:{:02d}".format(timestamp[3], timestamp[4], timestamp[5])
        log_entry = f"{formatted_time} | {message}"
        
        if self.buffering_enabled:
            if len(self.buffer) >= self.buffer_size:
                self.buffer.pop(0)
            self.buffer.append(log_entry)
        
        print(log_entry)  # Always print to console for immediate feedback

    def get_logs(self):
        return self.buffer

    def enable_buffering(self):
        self.buffering_enabled = True

    def disable_buffering(self):
        self.buffering_enabled = False

    def clear_logs(self):
        self.buffer.clear()