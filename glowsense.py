"""
GlowSense: Dynamic Ambient Lighting for Legacy Model 3
---------------------
A Python script to control an RGB LED strip based on Tesla Model 3 CAN data 
received via the Enhance Commander 2 interface.

Features:
- Displays turn signals, autopilot states, and blind spot warnings.
- Provides default color and error indications.
- Automatically retries connection on startup issues.

Author: Yigit Gungor
License: GNU General Public License v3.0 (See LICENSE file for details)
"""

import socket
import time
import cantools
from rpi_ws281x import PixelStrip, Color

# ---- Configuration ----

# LED Strip Settings
LED_COUNT = 60         # Number of LED pixels
LED_PIN = 18           # GPIO pin connected to the pixels (must support PWM)
LED_FREQ_HZ = 800000   # LED signal frequency in Hz (usually 800kHz)
LED_DMA = 10           # DMA channel to use for generating signal
LED_BRIGHTNESS = 255   # Brightness (0-255)
LED_INVERT = False     # True to invert the signal (depends on hardware)
LED_CHANNEL = 0        # GPIO channel

# CAN Receiver Settings
CAN_SERVER_IP = "192.168.4.1"
CAN_SERVER_PORT = 1338

# DBC File Path
DBC_FILE = "Model3CAN.dbc"

# Default Color
DEFAULT_COLOR = Color(255, 165, 0)  # Subtle orange/yellow

# ---- Initialize Components ----

# Load the DBC file
dbc = cantools.database.load_file(DBC_FILE)

# Initialize the LED Strip
strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
strip.begin()

# ---- LED Strip Control Functions ----

def set_whole_strip_color(color):
    """
    Set the entire LED strip to a single color.
    :param color: Color object
    """
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
    strip.show()

def animate_turn_signal(direction):
    """
    Animate turn signals (sliding yellow light).
    :param direction: 'left' or 'right'
    """
    for i in range(strip.numPixels()):
        if direction == 'left':
            strip.setPixelColor(i, Color(255, 255, 0))  # Yellow
        elif direction == 'right':
            strip.setPixelColor(strip.numPixels() - 1 - i, Color(255, 255, 0))
        strip.show()
        time.sleep(0.05)
        strip.setPixelColor(i, DEFAULT_COLOR)  # Reset to default

def set_blind_spot_warning(side):
    """
    Set a red warning section for blind spots.
    :param side: 'left' or 'right'
    """
    if side == 'left':
        for i in range(5):  # Left end section
            strip.setPixelColor(i, Color(255, 0, 0))
    elif side == 'right':
        for i in range(strip.numPixels() - 5, strip.numPixels()):  # Right end section
            strip.setPixelColor(i, Color(255, 0, 0))
    strip.show()

def set_glowing_red():
    """
    Create a glowing red effect for autopilot nag.
    """
    for brightness in range(0, 256, 5):
        color = Color(brightness, 0, 0)
        set_whole_strip_color(color)
        time.sleep(0.02)
    for brightness in range(255, -1, -5):
        color = Color(brightness, 0, 0)
        set_whole_strip_color(color)
        time.sleep(0.02)

# ---- CAN Data Processing ----

def process_can_data(can_id, can_data):
    """
    Process CAN data and control the LED strip accordingly.
    :param can_id: CAN ID of the message
    :param can_data: Raw CAN data
    """
    message = dbc.get_message_by_frame_id(can_id)
    if not message:
        return  # Ignore unknown messages

    decoded = message.decode(can_data)

    # Autopilot States
    if 'DAS_autopilotState' in decoded:
        autopilot_state = decoded['DAS_autopilotState']
        if autopilot_state in [3, 5]:  # Active
            set_whole_strip_color(Color(0, 0, 255))  # Blue
        elif autopilot_state in [0, 1, 14]:  # Inactive
            set_whole_strip_color(DEFAULT_COLOR)

    if 'DAS_autopilotHandsOnState' in decoded:
        hands_on_state = decoded['DAS_autopilotHandsOnState']
        if hands_on_state in [4, 5, 9, 10, 6, 7]:  # Nag
            set_glowing_red()

    # Turn Signals
    if 'VCFRONT_turnSignalLeftStatus' in decoded and decoded['VCFRONT_turnSignalLeftStatus'] == 1:
        animate_turn_signal('left')
    elif 'VCFRONT_turnSignalRightStatus' in decoded and decoded['VCFRONT_turnSignalRightStatus'] == 1:
        animate_turn_signal('right')

    # Blind Spot Warnings
    if 'DAS_blindSpotRearLeft' in decoded and decoded['DAS_blindSpotRearLeft'] in [1, 2]:
        set_blind_spot_warning('left')
    elif 'DAS_blindSpotRearRight' in decoded and decoded['DAS_blindSpotRearRight'] in [1, 2]:
        set_blind_spot_warning('right')

# ---- Main Function ----

def main():
    """
    Main function to connect to the CAN server and control the LED strip.
    """
    set_whole_strip_color(DEFAULT_COLOR)  # Default startup color

    # Attempt to connect to CAN server
    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((CAN_SERVER_IP, CAN_SERVER_PORT))
            break
        except socket.error:
            set_whole_strip_color(Color(255, 0, 0))  # Blink red for connection issue
            time.sleep(1)

    last_signal_time = time.time()

    try:
        while True:
            # Receive raw CAN data
            frame = sock.recv(16)
            if not frame:
                continue
            can_id, can_data = parse_can_frame(frame)
            process_can_data(can_id, can_data)
            last_signal_time = time.time()

            # Timeout handling
            if time.time() - last_signal_time > 10:
                set_whole_strip_color(Color(255, 255, 0))  # Blink yellow
                time.sleep(1)
                set_whole_strip_color(DEFAULT_COLOR)

    except KeyboardInterrupt:
        sock.close()
        set_whole_strip_color(DEFAULT_COLOR)  # Reset on exit

def parse_can_frame(frame):
    """
    Parse a raw CAN frame into CAN ID and data.
    :param frame: Raw CAN frame
    :return: CAN ID, CAN data
    """
    can_id = int.from_bytes(frame[:4], 'big')
    can_data = frame[8:]
    return can_id, can_data

if __name__ == "__main__":
    main()