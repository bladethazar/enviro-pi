# Enviro-Pi: Growspace Monitoring

## Project Overview

Enviro-Pi is a growspace monitoring system built around the Pico Enviro+ Pack. It uses MicroPython to collect reliable environmental data from the built-in sensors and shows it on the onboard LCD, with VPD visibility for plant health tuning.

### Key Features

- Environmental monitoring (temperature, humidity, pressure, light, gas, sound, VPD)
- MQTT integration for remote monitoring and control
- Configurable settings via MQTT for easy customization of configuration values and settings
- Optional InfluxDB integration for long-term data storage and analysis
- Interactive display interface with multiple sensor modes
- Manual control via the Enviro+ pHAT buttons
- Robust error handling and system health monitoring

## Hardware Components

- Raspberry Pi Pico W
- Pimoroni Pico Enviro+ Pack (BME688, LTR-559, mic, LCD, buttons)

## Software Requirements

- MicroPython firmware for Raspberry Pi Pico W (picow-v1.23.0-1-pimoroni-micropython.uf2)
- Custom Enviro-Pi software (included in this repository)

## Setup Instructions

1. Flash the Raspberry Pi Pico W with the specified MicroPython firmware.
2. Clone this repository to your local machine.
3. Copy `config.json.template` to `config.json` and update with your specific settings:

   ``` powershell
   cp config.json.template config.json
   ```

4. Edit `config.json` with your Wi-Fi credentials, MQTT broker details, and optional InfluxDB settings.
5. Upload all project files to your Pico W.

## Configuration

The `config.json` file is the central configuration point for Enviro-Pi. Key configuration sections include:

- Network settings (Wi-Fi, MQTT, optional InfluxDB)
- Environmental thresholds
- Display and LED settings
- System update intervals

Refer to `config.json.template` for a complete list of configurable options.

## Usage

Once powered on and configured, Enviro-Pi will:

1. Establish network connections (Wi-Fi, MQTT, optional InfluxDB)
2. Initialize all sensors and components
3. Begin continuous monitoring of growspace conditions
4. Transmit data to MQTT and (if enabled) InfluxDB at configured intervals
5. Display real-time information on the Enviro+ screen

### User Interaction

- Enviro+ pHAT Buttons:
  - A: Previous display mode
  - B: Toggle display backlight
  - X: Next display mode
  - Y: Reset min/max (sensor modes) or mode-specific action

### Display Modes

1. Overview Mode: Environmental summary
2. Air Mode: Temperature, humidity, dew point, pressure, gas
3. VPD Mode: Vapor pressure deficit with status
4. Light Mode: Light levels and status
5. Sound Mode: Ambient sound level
6. Log Mode: Recent system events and notifications
7. System Mode: Device performance and health metrics

## Troubleshooting

- Check `config.json` for correct network and sensor settings
- Use Log Mode on the display to view recent system events and errors
- Ensure all hardware connections are secure
- Verify MQTT connectivity and (if enabled) InfluxDB accessibility

## Contributing

Contributions to Enviro-Pi are welcome! Please fork the repository and submit a pull request with your improvements.

## License

This project is open-source and available under the MIT License. See the LICENSE file for full details.

## Acknowledgments

- Pimoroni for the Enviro+ pHAT and related libraries
- The MicroPython community for their excellent work
- InfluxDB and MQTT communities for robust data management solutions