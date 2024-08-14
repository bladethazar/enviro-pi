import uasyncio
from umqtt_simple import MQTTClient
import ujson
import utime

class MQTTManager:
    def __init__(self, config, log_manager):
        self.config = config
        self.log_manager = log_manager
        self.client = None
        self.is_connected = False
        self.last_publish_time = 0

    async def connect(self):
        try:
            self.client = MQTTClient(self.config.MQTT_CLIENT_NAME, self.config.MQTT_BROKER_ADDRESS, self.config.MQTT_BROKER_PORT)
            self.client.set_callback(self.on_message)
            self.client.connect()
            self.is_connected = True
            self.log_manager.log(f"MQTT client connected as {self.config.MQTT_CLIENT_NAME}")
            await self.subscribe_to_control_topics()
        except Exception as e:
            self.log_manager.log(f"Failed to connect to MQTT broker: {e}")
            self.is_connected = False

    async def reconnect(self):
        self.log_manager.log("Attempting to reconnect to MQTT broker")
        await self.connect()

    async def publish_data(self, data):
        if not self.is_connected:
            self.log_manager.log("MQTT not connected. Attempting to reconnect...")
            await self.reconnect()
        
        if not self.is_connected:
            self.log_manager.log("Failed to reconnect to MQTT. Cannot publish data.")
            return False

        try:
            for topic, subtopics in self.config.MQTT_TOPICS.items():
                if topic in data:
                    for subtopic in subtopics:
                        if subtopic in data[topic]:
                            full_topic = f"{self.config.MQTT_CLIENT_NAME}/{topic}/{subtopic}"
                            message = str(data[topic][subtopic])
                            self.log_manager.log(f"Publishing to {full_topic}: {message}")
                            result = self.client.publish(full_topic, message)
                            if result != 0:
                                self.log_manager.log(f"Failed to publish to {full_topic}. Result: {result}")
                                return False
            self.last_publish_time = utime.time()
            self.log_manager.log("All data published to MQTT broker")
            return True
        except Exception as e:
            self.log_manager.log(f"Failed to publish data: {e}")
            self.is_connected = False
            return False

    async def subscribe_to_control_topics(self):
        if self.is_connected:
            try:
                self.client.subscribe(b"picow/control/#")
                self.log_manager.log("Subscribed to control topics")
            except Exception as e:
                self.log_manager.log(f"Failed to subscribe to control topics: {e}")

    def on_message(self, topic, msg):
        self.log_manager.log(f"Received message on topic {topic}: {msg}")
        # Handle incoming messages here

    async def check_messages(self):
        if self.is_connected:
            try:
                self.client.check_msg()
            except Exception as e:
                self.log_manager.log(f"Error checking messages: {e}")
                await self.reconnect()

    async def run(self):
        while True:
            if not self.is_connected:
                await self.connect()
            await self.check_messages()
            await uasyncio.sleep(1)