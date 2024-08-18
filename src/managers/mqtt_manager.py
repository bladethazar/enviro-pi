import uasyncio
from umqtt_simple import MQTTClient
import utime

class MQTTManager:
    def __init__(self, config, log_mgr):
        self.config = config
        self.log_mgr = log_mgr
        self.client = None
        self.is_connected = False
        self.last_publish_time = 0
        self.system_manager = None
        
    def set_system_manager(self, system_manager):
        self.system_manager = system_manager

    async def publish_data(self, data):
        if not self.is_connected:
            self.log_mgr.log("MQTT not connected. Attempting to connect...")
            await self.reconnect()
        
        if not self.is_connected:
            self.log_mgr.log("MQTT connection failed. Cannot publish data.")
            return False

        try:
            for topic, subtopics in self.config.MQTT_TOPICS.items():
                if topic in data:
                    for subtopic in subtopics:
                        if subtopic in data[topic]:
                            full_topic = f"{self.config.MQTT_CLIENT_NAME}/{topic}/{subtopic}"
                            message = str(data[topic][subtopic])
                            try:
                                result = self.client.publish(full_topic.encode(), message.encode())
                            except Exception as e:
                                if self.system_manager:
                                    self.system_manager.add_error("mqtt_publish")
                                self.log_mgr.log(f"Exception while publishing to {full_topic}: {e}")
                        else:
                            self.log_mgr.log(f"Subtopic {subtopic} not found in data for topic {topic}")
                else:
                    self.log_mgr.log(f"Topic {topic} not found in data")
            
            self.last_publish_time = utime.time()
            self.log_mgr.log("MQTT data published successful")
            return True
        except Exception as e:
            self.log_mgr.log(f"Exception in publish_data: {e}")
            if self.system_manager:
                self.system_manager.add_error("mqtt_publish")
            self.is_connected = False
            return False

    async def reconnect(self):
        self.log_mgr.log("Attempting to reconnect to MQTT broker")
        try:
            self.client.disconnect()
        except:
            pass
        await self.connect()

    async def connect(self):
        if self.system_manager:
            self.system_manager.start_processing("mqtt_connect")
        self.log_mgr.log("MQTT connecting ...")
        try:
            self.client = MQTTClient(self.config.MQTT_CLIENT_NAME, self.config.MQTT_BROKER_ADDRESS, self.config.MQTT_BROKER_PORT)
            self.client.set_callback(self.on_message)
            self.client.connect()
            self.is_connected = True
            self.log_mgr.log(f"MQTT client connected as: {self.config.MQTT_CLIENT_NAME}")
            await self.subscribe_to_control_topics()
            if self.system_manager:
                self.system_manager.stop_processing("mqtt_connect")
        except Exception as e:
            self.log_mgr.log(f"Failed to connect to MQTT broker: {e}")
            self.is_connected = False
            if self.system_manager:
                self.system_manager.add_error("mqtt_connection")
                self.system_manager.stop_processing("mqtt_connect")


    async def subscribe_to_control_topics(self):
        if self.is_connected:
            try:
                self.client.subscribe(b"picow/control/#")
                self.log_mgr.log("MQTT control topics subscribed")
            except Exception as e:
                self.log_mgr.log(f"Failed to subscribe to control topics: {e}")

    def on_message(self, topic, msg):
        self.log_mgr.log(f"MQTT message received on topic {topic}: {msg}")
        # Handle incoming messages here

    async def check_messages(self):
        if self.is_connected:
            try:
                self.client.check_msg()
            except Exception as e:
                self.log_mgr.log(f"Error checking messages: {e}")
                await self.reconnect()

    async def run(self):
        while True:
            if not self.is_connected:
                await self.connect()
            await self.check_messages()
            await uasyncio.sleep(1)