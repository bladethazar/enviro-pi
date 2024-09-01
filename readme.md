# PicoW-Growmat: Advanced Plant Monitoring and Watering System

## Project Overview

PicoW-Growmat is a sophisticated plant monitoring and automated watering system designed for use in real growhouse environments. Built on the Raspberry Pi Pico W platform and utilizing MicroPython, this system integrates various sensors and components to provide comprehensive plant care, environmental monitoring, and intelligent watering control.

### Key Features

- Automated plant watering based on real-time soil moisture levels
- Environmental monitoring (temperature, humidity, pressure, light, UV, gas, sound)
- MQTT integration for remote monitoring and control
- Configurable settings via MQTT for easy customization of configuration values and settings
- InfluxDB integration for long-term data storage and analysis
- Interactive display interface with multiple information modes
- Manual control options with both on-board and external buttons
- Robust error handling and system health monitoring

## Hardware Components

- Raspberry Pi Pico W
- M5-Stack Watering Unit
- Pimoroni Pico Enviro+ pHAT
- LTR-390 UV and Ambient Light Sensor
- External momentary button for manual control

## Software Requirements

- MicroPython firmware for Raspberry Pi Pico W (picow-v1.23.0-1-pimoroni-micropython.uf2)
- Custom PicoW-Growmat software (included in this repository)

## Setup Instructions

1. Flash the Raspberry Pi Pico W with the specified MicroPython firmware.
2. Clone this repository to your local machine.
3. Copy `config.json.template` to `config.json` and update with your specific settings:

   ``` powershell
   cp config.json.template config.json
   ```

4. Edit `config.json` with your Wi-Fi credentials, MQTT broker details, InfluxDB settings, and other configuration options.
5. Upload all project files to your Pico W.

## Configuration

The `config.json` file is the central configuration point for PicoW-Growmat. Key configuration sections include:

- Network settings (Wi-Fi, MQTT, InfluxDB)
- Watering control parameters
- Environmental thresholds
- Display and LED settings
- System update intervals

Refer to `config.json.template` for a complete list of configurable options.

## Usage

Once powered on and configured, PicoW-Growmat will:

1. Establish network connections (Wi-Fi, MQTT, InfluxDB)
2. Initialize all sensors and components
3. Begin continuous monitoring of soil moisture and environmental conditions
4. Automatically water plants based on moisture thresholds
5. Transmit data to MQTT and InfluxDB at configured intervals
6. Display real-time information on the Enviro+ screen

### User Interaction

- Enviro+ pHAT Buttons:
  - A: Toggle display backlight
  - B: Update sensors / Reset water tank (mode-dependent)
  - X: Cycle through display modes
  - Y: Manual watering / Update UV index (mode-dependent)
- External button: Manual watering control

### Display Modes

1. Sensor Mode: Environmental data overview
2. Watering Mode: Soil moisture and watering system status
3. Log Mode: Recent system events and notifications
4. System Mode: Device performance and health metrics

## Troubleshooting

- Check `config.json` for correct network and sensor settings
- Use Log Mode on the display to view recent system events and errors
- Ensure all hardware connections are secure
- Verify MQTT and InfluxDB server accessibility

## Contributing

Contributions to PicoW-Growmat are welcome! Please fork the repository and submit a pull request with your improvements.

## License

This project is open-source and available under the MIT License. See the LICENSE file for full details.

## Acknowledgments

- Pimoroni for the Enviro+ pHAT and related libraries
- The MicroPython community for their excellent work
- InfluxDB and MQTT communities for robust data management solutions