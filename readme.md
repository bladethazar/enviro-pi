# Pico W Plant Watering and Environmental Monitoring System

## Project Overview

This project uses a Raspberry Pi Pico W to create an automated plant watering system with environmental monitoring capabilities. It combines an M5 Watering Unit for moisture sensing and watering control with a Pimoroni Enviro+ pHAT for environmental data collection.

### Key Features

- Automated plant watering based on soil moisture levels
- Environmental monitoring (temperature, humidity, pressure, light, gas)
- MQTT integration for remote monitoring and control
- Display interface for real-time data visualization
- Configurable settings for easy customization

## Hardware Requirements

- Raspberry Pi Pico W
- M5-Stack Watering Unit
- Pimoroni Pico Enviro+ pHAT

## Software Requirements

- MicroPython firmware for Raspberry Pi Pico W
- Required MicroPython libraries (included in the project)

## Setup Instructions

1. Flash MicroPython firmware to your Raspberry Pi Pico W.
2. Clone this repository to your local machine.
3. Copy `config.json.template` to `config.json` and update with your specific settings:

   ``` shell
   cp config.json.template config.json
   ```

4. Edit `config.json` with your Wi-Fi credentials, MQTT broker details, and other settings.
5. Upload all project files to your Pico W.

## Configuration

The system is configured using the `config.json` file. Here are the key configuration sections:

### Wi-Fi Settings

- `WIFI_SSID`: Your Wi-Fi network name
- `WIFI_PASSWORD`: Your Wi-Fi password
- `WIFI_COUNTRY`: Your country code (e.g., "US", "UK", "DE")

### MQTT Settings

MQTT implementation is configured to use anonymous client connection to the MQTT broker.

- `MQTT_CLIENT_NAME`: Unique name for this device on MQTT
- `MQTT_BROKER_ADDRESS`: IP address of your MQTT broker
- `MQTT_BROKER_PORT`: Port number for MQTT (usually 1883)
- `MQTT_UPDATE_INTERVAL`: How often to send data to MQTT (in seconds)

### Watering Unit Settings

- `WATER_PUMP_PIN_NR`: GPIO pin number for the water pump
- `MOISTURE_SENSOR_PIN_NR`: ADC pin number for the moisture sensor
- `MOISTURE_THRESHOLD`: Moisture level to trigger watering (percentage)
- `WATERING_DURATION`: How long to run the pump each cycle (seconds)
- `WATER_TANK_FULL_CAPACITY`: Total capacity of the water tank (ml)

### Enviro+ Settings

- `TEMPERATURE_OFFSET`: Adjustment for temperature readings
- `ENVIRO_PLUS_DISPLAY_BRIGHTNESS`: Screen brightness (0.0 to 1.0)
- `ALTITUDE`: Your altitude for pressure adjustments (meters)

## Usage

Once configured and powered on, the system will:

1. Connect to Wi-Fi
2. Start monitoring soil moisture and environmental conditions
3. Water the plant when soil moisture falls below the threshold
4. Send data to the MQTT broker at regular intervals
5. Display current readings on the Enviro+ screen

You can interact with the system using the buttons on the Enviro+ pHAT:

- Button A: Toggle display backlight
- Button B: Cycle through display modes
- Button X: Trigger manual watering
- Button Y: Reset water tank capacity

## Troubleshooting

- If the system fails to connect to Wi-Fi, check your `config.json` settings.
- For MQTT connection issues, verify your broker address and port.
- If the water pump doesn't activate, check the wiring and GPIO pin configuration.

## Contributing

Contributions to this project are welcome! Please fork the repository and submit a pull request with your improvements.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Thanks to Pimoroni for the Enviro+ pHAT and libraries
- Thanks to the MicroPython community for their excellent work
