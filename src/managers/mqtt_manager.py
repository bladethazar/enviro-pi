from umqtt_simple import MQTTClient
import ujson
import utime

class MQTTManager:
    def __init__(self, config, log_manager):
        self.client_name = config.MQTT_CLIENT_NAME
        self.broker = config.MQTT_BROKER_ADDRESS
        self.port = config.MQTT_BROKER_PORT
        self.update_interval = config.MQTT_UPDATE_INTERVAL
        self.topics = config.MQTT_TOPICS
        self.client = None
        self.last_publish_time = 0
        self.is_connected = False
        self.publishing_success = False
        self.log_manager = log_manager

    def connect(self):
        if not self.is_connected:
            try:
                self.client = MQTTClient(self.client_name, self.broker, self.port)
                self.client.set_callback(self.on_message)
                self.client.connect()
                self.is_connected = True
                self.log_manager.log(f"MQTT client connected as {self.client_name}")
                print(f"MQTTManager    | MQTT Client connected as {self.client_name}")
                self.subscribe_to_control_topics()
            except Exception as e:
                print(f"MQTTManager    | Failed to connect to MQTT broker: {e}")
                self.is_connected = False

    def disconnect(self):
        if self.is_connected:
            try:
                self.client.disconnect()
                self.is_connected = False
                self.log_manager.log(f"MQTT client disconnected")
                print("MQTTManager    | Disconnected from MQTT broker")
            except Exception as e:
                self.log_manager.log(f"MQTT disconnection error: {e}")
                print(f"MQTTManager    | Error disconnecting from MQTT broker: {e}")

    def reconnect(self):
        self.disconnect()
        self.connect()

    def check_connection(self):
        if not self.is_connected:
            self.connect()
        else:
            try:
                self.client.ping()
            except:
                self.log_manager.log(f"MQTT connection lost. Reconnecting...")
                print("MQTTManager    | MQTT connection lost. Reconnecting...")
                self.reconnect()

    def publish(self, topic, message):
        self.check_connection()
        if self.is_connected:
            try:
                self.client.publish(topic, message)
                return True
            except Exception as e:
                self.log_manager.log(f"Failed to publish message: {e}")
                print(f"MQTTManager    | Failed to publish message: {e}")
                self.reconnect()
                return False
    
    def set_publishing_success_status(self, status):
        self.publishing_success = status
        
    def get_publishing_success_status(self):
        return self.publishing_success

    def publish_data(self, data):
        current_time = utime.time()
        if current_time - self.last_publish_time >= self.update_interval:
            all_published = True
            for topic, subtopics in self.topics.items():
                if topic in data:
                    for subtopic in subtopics:
                        if subtopic in data[topic]:
                            full_topic = f"{self.client_name}/{topic}/{subtopic}"
                            message = str(data[topic][subtopic])
                            if not self.publish(full_topic, message):
                                all_published = False
                        else:
                            self.log_manager.log(f"Subtopic {subtopic} not found for {topic}")
                            print(f"MQTTManager    | Subtopic {subtopic} not found for {topic}")
                else:
                    self.log_manager.log(f"Topic {topic} not found")
                    print(f"MQTTManager    | Topic {topic} not found in data")
            
            self.set_publishing_success_status(all_published)
            self.last_publish_time = current_time
            return all_published
        return False

    def subscribe_to_control_topics(self):
        if self.is_connected:
            try:
                self.client.subscribe(b"picow/control/#")
                self.log_manager.log(f"Subscribed to control topics")
                print("MQTTManager    | Subscribed to control topics")
            except Exception as e:
                self.log_manager.log(f"Failed to subscribe to control topics: {e}")
                print(f"MQTTManager    | Failed to subscribe to control topics: {e}")

    def on_message(self, topic, msg):
        self.log_manager.log(f"Received message on topic {topic}: {msg}")
        print(f"MQTTManager    | Received message on topic {topic}: {msg}")
        if topic == b"picow/control/pump":
            self.handle_pump_control(msg)
        # Add more control handlers as needed

    def handle_pump_control(self, msg):
        try:
            command = ujson.loads(msg)
            if "action" in command:
                if command["action"] == "start":
                    print("MQTTManager    | Starting pump")
                    # Add your pump control code here
                elif command["action"] == "stop":
                    print("MQTTManager    | Stopping pump")
                    # Add your pump control code here
        except ValueError:
            print("MQTTManager    | Invalid JSON command received")

    def check_messages(self):
        if self.is_connected:
            try:
                self.client.check_msg()
            except Exception as e:
                self.log_manager.log(f"Error checking messages: {e}")
                print(f"MQTTManager    | Error checking messages: {e}")
                self.reconnect()