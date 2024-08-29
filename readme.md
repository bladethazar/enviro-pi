# PicoW-Growmat: Advanced Plant Monitoring and Watering System

## Project Overview

PicoW-Growmat is an advanced plant monitoring and watering system using a Raspberry Pi Pico W with MicroPython. It integrates various sensors and components to create a comprehensive solution for plant care, environmental monitoring, and automated watering.

### Key Features

- Automated plant watering based on soil moisture levels
- Dual moisture sensing with M5 Watering Unit and DFRobot Capacitive Soil Moisture Sensor
- Environmental monitoring (temperature, humidity, pressure, light, gas, sound)
- MQTT integration for remote monitoring and control
- InfluxDB integration for data storage and retrieval
- Display interface for real-time data visualization
- Configurable settings for easy customization
- Manual control with external momentary button

## Hardware Requirements

- Raspberry Pi Pico W
- M5-Stack Watering Unit
- Pimoroni Pico Enviro+ pHAT
- LTR-390 UV and Ambient Light Sensor
- Momentary button for manual control

## Software Requirements

- MicroPython firmware for Raspberry Pi Pico W (picow-v1.23.0-1-pimoroni-micropython.uf2)
- Required MicroPython libraries (included in the project)

## Project Structure

```
.
├── readme.md
└── src
    ├── components
    │   ├── af_ltr390.py
    │   ├── m5_watering_unit.py
    │   ├── momentary_button.py
    │   ├── pp_enviro_plus.py
    │   └── water_tank.py
    ├── config.json
    ├── config.json.template
    ├── config.py
    ├── lib
    │   └── umqtt_simple.py
    ├── main.py
    └── managers
        ├── data_manager.py
        ├── influx_data_manager.py
        ├── led_manager.py
        ├── log_manager.py
        ├── mqtt_manager.py
        ├── pp_enviro_plus_display_mgr.py
        ├── system_manager.py
        └── wifi_manager.py
```

## Setup Instructions

1. Flash the Raspberry Pi Pico W with the provided MicroPython firmware (`picow-v1.23.0-1-pimoroni-micropython.uf2`).
2. Clone this repository to your local machine.
3. Copy `config.json.template` to `config.json` and update with your specific settings:

   ```shell
   cp config.json.template config.json
   ```

4. Edit `config.json` with your Wi-Fi credentials, MQTT broker details, InfluxDB settings, and other configuration options.
5. Upload all project files to your Pico W.

## Configuration

The system is configured using the `config.json` file. Key configuration sections include:

- Wi-Fi Settings
- MQTT Settings
- InfluxDB Settings
- Watering Unit Settings (M5 and DFRobot)
- Enviro+ Settings
- Light Schedule Settings
- System Settings

Refer to the `config.json.template` file for a complete list of configuration options.

## Usage

Once configured and powered on, the system will:

1. Connect to Wi-Fi
2. Initialize all sensors and components
3. Start monitoring soil moisture and environmental conditions
4. Water the plant when soil moisture falls below the threshold
5. Send data to the MQTT broker and InfluxDB at regular intervals
6. Display current readings on the Enviro+ screen

You can interact with the system using the buttons on the Enviro+ pHAT:

- Button A: Toggle display backlight
- Button B: Trigger sensor update or reset water tank (mode-dependent)
- Button X: Cycle through display modes
- Button Y: Trigger manual watering or update UV index (mode-dependent)

The external momentary button can be used for manual watering control.

## Display Modes

1. Sensor Mode: Displays environmental data
2. Watering Mode: Shows soil moisture and watering system status
3. Log Mode: Displays recent system logs
4. System Mode: Shows system performance metrics

## Troubleshooting

- If the system fails to connect to Wi-Fi, check your `config.json` settings.
- For MQTT or InfluxDB connection issues, verify your broker/database address and credentials.
- If sensors are not reading correctly, check wiring and pin configurations.
- Use the Log Mode on the display to view recent system events and errors.

## Contributing

Contributions to this project are welcome! Please fork the repository and submit a pull request with your improvements.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Thanks to Pimoroni for the Enviro+ pHAT and libraries
- Thanks to the MicroPython community for their excellent work
- Thanks to the InfluxDB and MQTT communities for their robust data management solutions
