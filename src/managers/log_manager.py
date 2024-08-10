import gc

class LogManager:
    def __init__(self, config):
        self.buffer_size = config.LOG_MANAGER_BUFFER_SIZE
        self.buffer = bytearray(self.buffer_size)
        self.write_index = 0
        self.read_index = 0
        self.buffering_enabled = True

    def log(self, message):
        if self.buffering_enabled:
            message_bytes = (message + "\n").encode('utf-8')
            data_len = len(message_bytes)
            # Check for buffer overflow
            if (self.write_index + data_len) >= self.buffer_size:
                # Handle buffer overflow (e.g., discard oldest data)
                self.read_index = (self.read_index + (self.write_index + data_len - self.buffer_size)) % self.buffer_size
                self.write_index = 0
            # Append data to buffer
            end_index = min(self.write_index + data_len, self.buffer_size)
            self.buffer[self.write_index:end_index] = message_bytes[:end_index-self.write_index]
            self.write_index = end_index % self.buffer_size

    def get_logs(self):
        if self.write_index >= self.read_index:
            logs = self.buffer[self.read_index:self.write_index].decode('utf-8', 'ignore')
        else:
            logs = self.buffer[self.read_index:].decode('utf-8', 'ignore') + self.buffer[:self.write_index].decode('utf-8', 'ignore')

        self.read_index = (self.read_index + len(logs.encode('utf-8'))) % self.buffer_size
        gc.collect()  # Force garbage collection to reclaim memory
        return logs.strip().split('\n')

    def enable_buffering(self):
        self.buffering_enabled = True
        print("Log buffering enabled ...")

    def disable_buffering(self):
        self.buffering_enabled = False
        print("Log buffering disabled ...")