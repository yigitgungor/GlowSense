#!/usr/bin/python3

import socket
import struct
import time
import threading
import json
from rpi_ws281x import PixelStrip, Color

#CAN Parameters
targetIP = '192.168.4.1'
targetPort = 1338

framesToFilter = [
    [0, 0x3f5],
    [0, 0x399],
    [0, 0x33A],
    [0, 0x204],
    [0, 0x273],
]

#LED Strip Parameters
LED_COUNT = 180
LED_PIN = 18
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_BRIGHTNESS = 180
LED_INVERT = False
LED_CHANNEL = 0

COLOR_DEFAULT = Color(255, 40, 0)
COLOR_BLUE = Color(0, 0, 255)
COLOR_RED = Color(255, 0, 0)
COLOR_YELLOW = Color(255, 150, 0)
COLOR_GREEN = Color(0, 255, 0)
COLOR_NONE = Color(0, 0, 0)

#Glowsense Parameters
DEBUG = False
LED_SIGNAL_LENGTH = 20
LED_BLINDSPOT_LENGTH = 10

#region CAN Decoding
def extractValue(data_, valuedef):
    data = data_
    if valuedef['byteorder'] == 'little':
        pass
    elif valuedef['byteorder'] == 'big':
        tmpdata = struct.pack("<Q", data_)
        data = struct.unpack(">Q", tmpdata)[0]

    calculatedValue = ((1 << valuedef['bitlength']) - 1) & (data >> valuedef['bitstart'])
    if (valuedef['signed']):
        if (calculatedValue > pow(2, valuedef['bitlength']-1)):
            calculatedValue = 0 - (pow(2, valuedef['bitlength']) - calculatedValue)
        calculatedValue = float(calculatedValue) * valuedef['factor'] + valuedef['offset']
    else:
        calculatedValue = float(calculatedValue) * valuedef['factor'] + valuedef['offset']
    return calculatedValue

def get_bit_data(frame, start_bit, length, factor=1, offset=0):
    signal = extractValue(frame, {'byteorder': 'little', 'bitlength': length, 'bitstart': start_bit, 'signed': False, 'factor': factor, 'offset': offset})
    return signal

def process_signal(raw_signal, value_map):
    result = value_map.get(raw_signal, "UNKNOWN")
    return result

def parse_turn_signals(turn_signal_frame):
    left_turn_signal_start_bit = 0
    left_turn_signal_length = 2
    right_turn_signal_start_bit = 2
    right_turn_signal_length = 2

    turn_signal_value_map = {
        2: "TURN_SIGNAL_ACTIVE_HIGH",
        1: "TURN_SIGNAL_ACTIVE_LOW",
        0: "TURN_SIGNAL_OFF"
    }

    raw_left_turn_signal = get_bit_data(turn_signal_frame, left_turn_signal_start_bit, left_turn_signal_length)
    raw_right_turn_signal = get_bit_data(turn_signal_frame, right_turn_signal_start_bit, right_turn_signal_length)
    left_turn_signal_status = process_signal(raw_left_turn_signal, turn_signal_value_map)
    right_turn_signal_status = process_signal(raw_right_turn_signal, turn_signal_value_map)

    return left_turn_signal_status, right_turn_signal_status

def parse_soc(soc_frame):
    soc_start_bit = 27 #maybe 27|7
    soc_signal_length = 7

    soc = get_bit_data(soc_frame, soc_start_bit, soc_signal_length)

    return soc

def parse_brightness(ui_frame):
    brightness_start_bit = 32
    brightness_signal_length = 8
    brightness_factor = 0.5
    brightness_offset = 0

    brightness = get_bit_data(ui_frame, brightness_start_bit, brightness_signal_length, brightness_factor, brightness_offset)

    return brightness

def parse_charge_status(charge_status_frame):
    charge_status_start_bit = 56
    charge_status_signal_length = 1

    charge_status = get_bit_data(charge_status_frame, charge_status_start_bit, charge_status_signal_length)

    return charge_status

def parse_autopilot_and_blindspot_signals(autopilot_blindspot_frame):
    autopilot_hands_on_start_bit = 42
    autopilot_hands_on_length = 4
    autopilot_state_start_bit = 0
    autopilot_state_length = 4
    blindspot_rear_left_start_bit = 4
    blindspot_rear_left_length = 2
    blindspot_rear_right_start_bit = 6
    blindspot_rear_right_length = 2
    forward_collision_warning_start_bit = 22
    forward_collision_warning_length = 2

    autopilot_hands_on_value_map = {
            0: "LC_HANDS_ON_NOT_REQD",
            1: "LC_HANDS_ON_REQD_DETECTED",
            2: "LC_HANDS_ON_REQD_NOT_DETECTED",
            3: "LC_HANDS_ON_REQD_VISUAL",
            4: "LC_HANDS_ON_REQD_CHIME_1",
            5: "LC_HANDS_ON_REQD_CHIME_2",
            6: "LC_HANDS_ON_REQD_SLOWING",
            7: "LC_HANDS_ON_REQD_STRUCK_OUT",
            8: "LC_HANDS_ON_SUSPENDED",
            9: "LC_HANDS_ON_REQD_ESCALATED_CHIME_1",
            10: "LC_HANDS_ON_REQD_ESCALATED_CHIME_2",
            15: "LC_HANDS_ON_SNA"
    }

    autopilot_state_value_map = {
            0: "DISABLED",
            1: "UNAVAILABLE",
            2: "AVAILABLE",
            3: "ACTIVE_NOMINAL",
            4: "ACTIVE_RESTRICTED",
            5: "ACTIVE_NAV",
            6: "FSD?",
            8: "ABORTING",
            9: "ABORTED",
            14: "FAULT",
            15: "SNA"
    }

    blindspot_value_map = {
            0: "NO_WARNING",
            1: "WARNING_LEVEL_1",
            2: "WARNING_LEVEL_2",
            3: "SNA"
    }

    forward_collision_warning_value_map = {
            0: "NONE",
            1: "FORWARD_COLLISION_WARNING",
            3: "SNA"
    }

    raw_autopilot_hands_on = get_bit_data(autopilot_blindspot_frame, autopilot_hands_on_start_bit, autopilot_hands_on_length)
    raw_autopilot_state = get_bit_data(autopilot_blindspot_frame, autopilot_state_start_bit, autopilot_state_length)
    raw_blindspot_rear_left = get_bit_data(autopilot_blindspot_frame, blindspot_rear_left_start_bit, blindspot_rear_left_length)
    raw_blindspot_rear_right = get_bit_data(autopilot_blindspot_frame, blindspot_rear_right_start_bit, blindspot_rear_right_length)
    raw_forward_collision_warning = get_bit_data(autopilot_blindspot_frame, forward_collision_warning_start_bit, forward_collision_warning_length)

    autopilot_hands_on_status = process_signal(raw_autopilot_hands_on, autopilot_hands_on_value_map)
    autopilot_state_status = process_signal(raw_autopilot_state, autopilot_state_value_map)
    blindspot_rear_left_status = process_signal(raw_blindspot_rear_left, blindspot_value_map)
    blindspot_rear_right_status = process_signal(raw_blindspot_rear_right, blindspot_value_map)
    forward_collision_warning_status = process_signal(raw_forward_collision_warning, forward_collision_warning_value_map)

    return autopilot_hands_on_status, autopilot_state_status, blindspot_rear_left_status, blindspot_rear_right_status, forward_collision_warning_status
#endregion

#region Panda Connection
doshutdown = False
def heartbeatFunction():
    while True:
        time.sleep(3)
        print("heartbeat")
        sock.sendto(b"ehllo", (targetIP, targetPort))
        if doshutdown:
            break

def parsePandaPacket(data):
    packetStart = 0
    headerbytes = data[packetStart:packetStart + 8]

    packetStart = packetStart + 8

    unpackedHeader = struct.unpack('<II', headerbytes)
    frameID = unpackedHeader[0] >> 21

    frameLength = unpackedHeader[1] & 0x0F
    frameBusId = unpackedHeader[1] >> 4
    frameData = data[packetStart:packetStart+8]

    return (frameBusId, frameID, frameLength, frameData)
#endregion

#region LED configuration

signal_threads = {
    "left_turn": {"event": threading.Event(), "thread": None},
    "right_turn": {"event": threading.Event(), "thread": None},
    "left_blindspot": {"event": threading.Event(), "thread": None},
    "right_blindspot": {"event": threading.Event(), "thread": None},
    "charging": {"event": threading.Event(), "thread": None},
    "hands_on": {"event": threading.Event(), "thread": None},
    "forward_collision": {"event": threading.Event(), "thread": None},
    "autopilot": {"event": threading.Event(), "thread": None},
}

CURRENT_BASE = COLOR_DEFAULT

strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
strip.begin()

def set_strip_color(color, start=0, end=LED_COUNT):
    for i in range(start, end):
        strip.setPixelColor(i, color)
    strip.show()

def turn_off_strip():
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(0, 0, 0))
    strip.show()

def clear_strip(start=0, end=LED_COUNT):
    set_strip_color(CURRENT_BASE, start, end)

def default_base_strip():
    global CURRENT_BASE
    CURRENT_BASE = COLOR_DEFAULT
    set_strip_color(COLOR_DEFAULT)

def autopilot_base_strip():
    global CURRENT_BASE
    CURRENT_BASE = COLOR_BLUE
    set_strip_color(COLOR_BLUE)

default_base_strip()

#endregion

results = {
            "Left Turn Signal Status": "UNKNOWN",
            "Right Turn Signal Status": "UNKNOWN",
            "Autopilot Hands-On Status": "UNKNOWN",
            "Autopilot State": "UNKNOWN",
            "Blindspot Rear Left Status": "UNKNOWN",
            "Blindspot Rear Right Status": "UNKNOWN",
            "SoC": "UNKNOWN",
            "Charge Status": "UNKNOWN"
        }

#region LED functions
def leftTurnSignal(stop_event, blindspot_event):
    color = COLOR_GREEN
    start_led = LED_COUNT - LED_SIGNAL_LENGTH
    end_led = LED_COUNT
    running = False
    while not stop_event.is_set():
        is_left_blindspot_active = (
            signal_threads["left_blindspot"]["thread"] is not None and
            signal_threads["left_blindspot"]["thread"].is_alive()
        )
        if is_left_blindspot_active:
            end_led = (LED_COUNT-LED_BLINDSPOT_LENGTH)
        else:
            end_led = LED_COUNT

        running = True
        set_strip_color(color, start_led, end_led)
        time.sleep(0.45)
        clear_strip(start_led, end_led)
        time.sleep(0.45)

    if running == True:
        clear_strip(start_led, end_led)
        running = False

def rightTurnSignal(stop_event, blindspot_event):
    color = COLOR_GREEN
    start_led = 0
    end_led = LED_SIGNAL_LENGTH
    running = False
    while not stop_event.is_set():
        is_right_blindspot_active = (
            signal_threads["right_blindspot"]["thread"] is not None and
            signal_threads["right_blindspot"]["thread"].is_alive()
        )
        if is_right_blindspot_active:
            start_led = LED_BLINDSPOT_LENGTH
        else:
            start_led = 0

        running = True
        set_strip_color(color, start_led, end_led)
        time.sleep(0.45)
        clear_strip(start_led, end_led)
        time.sleep(0.45)

    if running == True:
        clear_strip(start_led, end_led)
        running = False

def leftBlindSpot(stop_event):
    running = False
    while not stop_event.is_set():
        is_left_signal_active = (
            signal_threads["left_turn"]["thread"] is not None and
            signal_threads["left_turn"]["thread"].is_alive()
        )

        running = True
        if is_left_signal_active:
            set_strip_color(COLOR_RED, start=(LED_COUNT-LED_BLINDSPOT_LENGTH), end=LED_COUNT)
            time.sleep(0.15)
            set_strip_color(COLOR_NONE, start=(LED_COUNT-LED_BLINDSPOT_LENGTH), end=LED_COUNT)
            time.sleep(0.15)
        else:
            set_strip_color(COLOR_RED, start=(LED_COUNT-LED_BLINDSPOT_LENGTH), end=LED_COUNT)

    if running == True:
        set_strip_color(CURRENT_BASE, start=(LED_COUNT-LED_BLINDSPOT_LENGTH), end=LED_COUNT)
        running = False


def rightBlindSpot(stop_event):
    running = False
    while not stop_event.is_set():
        is_right_signal_active = (
            signal_threads["right_turn"]["thread"] is not None and
            signal_threads["right_turn"]["thread"].is_alive()
        )

        running = True
        if is_right_signal_active:
            set_strip_color(COLOR_RED, start=0, end=LED_BLINDSPOT_LENGTH)
            time.sleep(0.15)
            set_strip_color(COLOR_NONE, start=0, end=LED_BLINDSPOT_LENGTH)
            time.sleep(0.15)
        else:
            set_strip_color(COLOR_RED, start=0, end=LED_BLINDSPOT_LENGTH)

    if running == True:
        set_strip_color(CURRENT_BASE, start=0, end=LED_BLINDSPOT_LENGTH)
        running = False

def autopilot(stop_event):
    running = False
    while not stop_event.is_set():
        if running == False:
            running = True
            autopilot_base_strip()

    if running == True:
        default_base_strip()
        running = False

def handsOnAlert(stop_event):
    running = False
    while not stop_event.is_set():
        running = True
        set_strip_color(COLOR_BLUE)
        time.sleep(0.5)
        set_strip_color(COLOR_NONE)
        time.sleep(0.5)

    if running == True:
        clear_strip()
        running = False


def forwardCollisionAlert(stop_event):
    running = False
    while not stop_event.is_set():
        running = True
        set_strip_color(COLOR_RED)
        time.sleep(0.15)
        set_strip_color(COLOR_NONE)
        time.sleep(0.15)

    if running == True:
        clear_strip()
        running = False

def charging(stop_event):
    running = False
    while not stop_event.is_set():
        running = True
        soc = results["SoC"]
        soc = min(int(soc), 100)

        num_lit_leds = int((soc / 100.0) * LED_COUNT)
        max_brightness = max(LED_BRIGHTNESS, 130)
        for brightness in range(max_brightness, 25, -5):
            for i in range(LED_COUNT - num_lit_leds, LED_COUNT):
                strip.setPixelColor(i, Color(0, brightness, 0))
            strip.show()
            time.sleep(0.05)

        time.sleep(1)

        for brightness in range(25, max_brightness, 5):
            for i in range(LED_COUNT - num_lit_leds, LED_COUNT):
                strip.setPixelColor(i, Color(0, brightness, 0))
            strip.show()
            time.sleep(0.05)

        time.sleep(0.2)

    if running == True:
        default_base_strip()
        running = False


#endregion

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
random_port_offset = 0
used_port = targetPort+random_port_offset
print("Using port " + str(used_port))
print("Socket timeout " + str(5))
sock.settimeout(5)
sock.bind(("0.0.0.0", used_port))

while True:
    try:
        print("sending cancel")
        sock.sendto(str.encode("bye"), (targetIP, targetPort))
        print("sending ehllo")
        sock.sendto(str.encode("ehllo"), (targetIP, targetPort))
        data, addr = sock.recvfrom(1024)
        parsedData = parsePandaPacket(data)

        if parsedData[0] == 15 and parsedData[1] == 6:
            for i in range(175, 180):
                strip.setPixelColor(i, COLOR_GREEN)
            strip.show()
            time.sleep(0.3)
            clear_strip()
            x = threading.Thread(target=heartbeatFunction)
            x.start()
            for filterEntry in framesToFilter:
                filterData = struct.pack("!BBH", 0x0F, filterEntry[0], filterEntry[1] )
                print("Filter: " + str(filterData))
                sock.sendto(filterData, (targetIP, targetPort))

            while True:
                try:
                    data, addr = sock.recvfrom(1024)
                    dataLength = len(data)
                    packetStart = 0

                    while packetStart < dataLength:
                        headerbytes = data[packetStart:packetStart + 8]

                        packetStart = packetStart + 8

                        unpackedHeader = struct.unpack('<II', headerbytes)
                        frameID = unpackedHeader[0] >> 21

                        frameLength = unpackedHeader[1] & 0x0F
                        frameBusId = unpackedHeader[1] >> 4
                        frameData = data[packetStart:packetStart+8]

                        if (DEBUG):
                            print (int(time.time() * 1000), end='')
                            print(" ", end='')
                            print("can%d " % (frameBusId), end='')
                            print("{0:03X}#".format(frameID), end='')

                            for payloadByte in frameData:
                                print("{0:08b}".format(payloadByte), end=' ')
                            print("")
                            print("")
                            print(json.dumps(results))
                            print("")
                            print("")

                        unpackedData = struct.unpack("<Q", frameData)[0]

                        if(frameID == 1013):
                            results["Left Turn Signal Status"], results["Right Turn Signal Status"] = parse_turn_signals(unpackedData)
                            if results["Left Turn Signal Status"] in ["TURN_SIGNAL_ACTIVE_HIGH","TURN_SIGNAL_ACTIVE_LOW"]:
                                if signal_threads["left_turn"]["thread"] is None or not signal_threads["left_turn"]["thread"].is_alive():
                                    signal_threads["left_turn"]["event"].clear()
                                    signal_threads["left_turn"]["thread"] = threading.Thread(target=leftTurnSignal, args=(signal_threads["left_turn"]["event"], signal_threads["left_blindspot"]["event"]))
                                    signal_threads["left_turn"]["thread"].start()
                            else:
                                signal_threads["left_turn"]["event"].set()

                            if results["Right Turn Signal Status"] in ["TURN_SIGNAL_ACTIVE_HIGH","TURN_SIGNAL_ACTIVE_LOW"]:
                                if signal_threads["right_turn"]["thread"] is None or not signal_threads["right_turn"]["thread"].is_alive():
                                    signal_threads["right_turn"]["event"].clear()
                                    signal_threads["right_turn"]["thread"] = threading.Thread(target=rightTurnSignal, args=(signal_threads["right_turn"]["event"], signal_threads["right_blindspot"]["event"]))
                                    signal_threads["right_turn"]["thread"].start()
                            else:
                                signal_threads["right_turn"]["event"].set()
                        elif(frameID == 921):
                            autopilot_hands_on_status, autopilot_state_status, blindspot_rear_left_status, blindspot_rear_right_status, forward_collision_warning_status = parse_autopilot_and_blindspot_signals(unpackedData)
                            results["Autopilot Hands-On Status"] = autopilot_hands_on_status
                            results["Autopilot State"] = autopilot_state_status
                            results["Blindspot Rear Left Status"] = blindspot_rear_left_status
                            results["Blindspot Rear Right Status"] = blindspot_rear_right_status
                            results["Forward Collision Warning"]= forward_collision_warning_status

                            if results["Autopilot State"] in ["ACTIVE_NOMINAL","ACTIVE_NAV","FSD?"]:
                                if signal_threads["autopilot"]["thread"] is None or not signal_threads["autopilot"]["thread"].is_alive():
                                    signal_threads["autopilot"]["event"].clear()
                                    signal_threads["autopilot"]["thread"] = threading.Thread(target=autopilot, args=(signal_threads["autopilot"]["event"],))
                                    signal_threads["autopilot"]["thread"].start()
                            else:
                                signal_threads["autopilot"]["event"].set()

                            if results["Blindspot Rear Left Status"] in ["WARNING_LEVEL_1","WARNING_LEVEL_2"]:
                                if signal_threads["left_blindspot"]["thread"] is None or not signal_threads["left_blindspot"]["thread"].is_alive():
                                    signal_threads["left_blindspot"]["event"].clear()
                                    signal_threads["left_blindspot"]["thread"] = threading.Thread(target=leftBlindSpot, args=(signal_threads["left_blindspot"]["event"],))
                                    signal_threads["left_blindspot"]["thread"].start()
                            else:
                                signal_threads["left_blindspot"]["event"].set()

                            if results["Blindspot Rear Right Status"] in ["WARNING_LEVEL_1","WARNING_LEVEL_2"]:
                                if signal_threads["right_blindspot"]["thread"] is None or not signal_threads["right_blindspot"]["thread"].is_alive():
                                    signal_threads["right_blindspot"]["event"].clear()
                                    signal_threads["right_blindspot"]["thread"] = threading.Thread(target=rightBlindSpot, args=(signal_threads["right_blindspot"]["event"],))
                                    signal_threads["right_blindspot"]["thread"].start()
                            else:
                                signal_threads["right_blindspot"]["event"].set()

                            if results["Autopilot Hands-On Status"] in [
"LC_HANDS_ON_REQD_VISUAL","LC_HANDS_ON_REQD_CHIME_1","LC_HANDS_ON_REQD_CHIME_2","LC_HANDS_ON_REQD_ESCALATED_CHIME_1","LC_HANDS_ON_REQD_ESCALATED_CHIME_2"]:
                                if signal_threads["hands_on"]["thread"] is None or not signal_threads["hands_on"]["thread"].is_alive():
                                    signal_threads["hands_on"]["event"].clear()
                                    signal_threads["hands_on"]["thread"] = threading.Thread(target=handsOnAlert, args=(signal_threads["hands_on"]["event"],))
                                    signal_threads["hands_on"]["thread"].start()
                            else:
                                signal_threads["hands_on"]["event"].set()

                            if results["Forward Collision Warning"] in ["FORWARD_COLLISION_WARNING"]:
                                if signal_threads["forward_collision"]["thread"] is None or not signal_threads["forward_collision"]["thread"].is_alive():
                                    signal_threads["forward_collision"]["event"].clear()
                                    signal_threads["forward_collision"]["thread"] = threading.Thread(target=forwardCollisionAlert, args=(signal_threads["forward_collision"]["event"],))
                                    signal_threads["forward_collision"]["thread"].start()
                            else:
                                signal_threads["forward_collision"]["event"].set()

                        elif(frameID == 826):
                            results["SoC"] = parse_soc(unpackedData)
                        elif(frameID == 516):
                            results["Charge Status"] = parse_charge_status(unpackedData)
                            if results["Charge Status"] == 1:
                                if signal_threads["charging"]["thread"] is None or not signal_threads["charging"]["thread"].is_alive():
                                    signal_threads["charging"]["event"].clear()
                                    signal_threads["charging"]["thread"] = threading.Thread(target=charging, args=(signal_threads["charging"]["event"],))
                                    signal_threads["charging"]["thread"].start()
                            else:
                                signal_threads["charging"]["event"].set()
                        elif(frameID == 627):
                            brightness = parse_brightness(unpackedData)
                            brightness = 5 if brightness < 10 else brightness
                            LED_BRIGHTNESS = int(min(brightness, 100) / 100 * 255)
                            strip.setBrightness(LED_BRIGHTNESS)
                            strip.show()
                        else:
                            print("Not sure what this means, but it's okay.")
                        packetStart = packetStart + 8
                except Exception as e:
                    print(e)
                    set_strip_color(COLOR_RED)
                    time.sleep(0.3)
                    default_base_strip()
                    break
        elif parsedData[0] == 15 and parsedData[1] == 7:
            set_strip_color(COLOR_RED)
            time.sleep(0.3)
            clear_strip()
            time.sleep(0.3)
            print("Connection refused, retrying...")
        else:
            set_strip_color(COLOR_RED)
            time.sleep(0.3)
            clear_strip()
            time.sleep(0.3)
            print("Failed to get a valid response, retrying...")
    except:
        for i in range(175, 180):
            strip.setPixelColor(i, COLOR_RED)
        strip.show()
        time.sleep(0.3)
        clear_strip()
        print("Error, retrying...")
        time.sleep(5)
    time.sleep(1)