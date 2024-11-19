# GlowSense: Dynamic Ambient Lighting for Tesla Model 3

  GlowSense brings dynamic ambient lighting to your Tesla Model 3, transforming the interior of your car based on real-time driving events. Reacting to signals such as turn signals, autopilot activation, and blind spot warnings, this project provides an engaging, visual cue system that enhances your driving experience.

## Features
  - Ambient lighting reacts to Tesla Model 3 CAN bus data.
  - Changes colors based on events like:
    - Left and right turn signals
    - Autopilot activation
    - Blind spot warnings
  - Uses an RGB LED strip for lighting effects.
  - Easy setup with a Raspberry Pi Zero W.

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yigitgungor/GlowSense.git

2. **Set up your hardware**:

  Raspberry Pi Zero W
  RGB LED strip connected via GPIO
  Ensure your Raspberry Pi has internet access and Wi-Fi setup for communication with the Tesla Model 3.

3. **Install dependencies**:
  GlowSense requires Python 3 and some libraries:
    ```bash
    pip install -r requirements.txt

4. **Configure the connection to the Tesla Model 3**:
  Make sure your Raspberry Pi can connect to the car's CAN bus data.
  Refer to the documentation for your specific setup to interface with Tesla's CAN system.

5. **Run the script**:
  Start the script with:
    ```bash
    python glowSense.py
    This will start the dynamic lighting system, responding to Tesla Model 3 events.

## License
  This project is licensed under the GNU General Public License v3.0. You are free to use, modify, and distribute this software for personal use, as long as any derivative works are also open-source under the same license. See the LICENSE file for more details.

## Disclaimer
  This software is provided "as-is" without any warranty of any kind. Use at your own risk. Make sure to only use the hardware for personal purposes and follow all safety guidelines for working with electronic components.