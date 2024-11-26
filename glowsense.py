import socket
import struct
import time
import threading
from rpi_ws281x import PixelStrip, Color

#region CAN Decoding
targetIP = '192.168.4.1'
targetPort = 1338

framesToFilter = [
    [0, 0x3f5],
    [0, 0x399],
    [0, 0x33A],
    [0, 0x204],
]

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

def get_bit_data(frame, start_bit, length):
    signal = extractValue(frame, {'byteorder': 'little', 'bitlength': length, 'bitstart': start_bit, 'signed': False, 'factor': 1, 'offset': 0})
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
    soc_start_bit = 48 #maybe 27|7
    soc_signal_length = 7

    soc = get_bit_data(soc_frame, soc_start_bit, soc_signal_length)

    return soc

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

    raw_autopilot_hands_on = get_bit_data(autopilot_blindspot_frame, autopilot_hands_on_start_bit, autopilot_hands_on_length)
    raw_autopilot_state = get_bit_data(autopilot_blindspot_frame, autopilot_state_start_bit, autopilot_state_length)
    raw_blindspot_rear_left = get_bit_data(autopilot_blindspot_frame, blindspot_rear_left_start_bit, blindspot_rear_left_length)
    raw_blindspot_rear_right = get_bit_data(autopilot_blindspot_frame, blindspot_rear_right_start_bit, blindspot_rear_right_length)

    autopilot_hands_on_status = process_signal(raw_autopilot_hands_on, autopilot_hands_on_value_map)
    autopilot_state_status = process_signal(raw_autopilot_state, autopilot_state_value_map)
    blindspot_rear_left_status = process_signal(raw_blindspot_rear_left, blindspot_value_map)
    blindspot_rear_right_status = process_signal(raw_blindspot_rear_right, blindspot_value_map)

    return autopilot_hands_on_status, autopilot_state_status, blindspot_rear_left_status, blindspot_rear_right_status
#endregion

#region Panda Connection
doshutdown = False
def heartbeatFunction():
    while True:
        time.sleep(4)
        print("sending ehllo")
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

#region LED Configuration

# LED strip configuration:
LED_COUNT = 60      # Number of LEDs in the strip
LED_PIN = 18        # GPIO pin connected to the strip (must support PWM)
LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800kHz)
LED_DMA = 10        # DMA channel to use for generating signal
LED_BRIGHTNESS = 255  # Brightness (0-255)
LED_INVERT = False   # True to invert the signal
LED_CHANNEL = 0      # Channel to use

# Initialize the LED strip
strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
strip.begin()

# Utility: Set all LEDs to a single color
def set_strip_color(color, start=0, end=LED_COUNT):
    for i in range(start, end):
        strip.setPixelColor(i, color)
    strip.show()

# Utility: Turn off LEDs
def clear_strip():
    set_strip_color(Color(0, 0, 0))

# LED colors
COLOR_WARM_WHITE = Color(255, 147, 41)
COLOR_BLUE = Color(0, 0, 255)
COLOR_RED = Color(255, 0, 0)
COLOR_GREEN = Color(0, 255, 0)

set_strip_color(COLOR_WARM_WHITE)
#endregion

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
random_port_offset = 0
used_port = targetPort+random_port_offset
print("Using port " + str(used_port))
sock.bind(("0.0.0.0", used_port))

print("sending ehllo")
sock.sendto(str.encode("ehllo"), (targetIP, targetPort))

data, addr = sock.recvfrom(1024)
parsedData = parsePandaPacket(data)
if parsedData[0] == 15 and parsedData[1] == 6:
    pass
elif parsedData[0] == 15 and parsedData[1] == 7:
    print("Connection refused")
    exit(1)
else:
    print("Failed to get a valid response")
    exit(1)


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

#region LED states
# Default state
def set_default():
    set_strip_color(COLOR_WARM_WHITE)

# Autopilot state
def set_autopilot():
    set_strip_color(COLOR_BLUE)

# Turn signal states
def blink_left_signal():
    while results["Left Turn Signal Status"] == "TURN_SIGNAL_ACTIVE_HIGH":
        set_strip_color(COLOR_RED, start=0, end=LED_COUNT // 2)
        time.sleep(0.5)
        clear_strip()
        time.sleep(0.5)
    set_default()

def blink_right_signal():
    while results["Right Turn Signal Status"] == "TURN_SIGNAL_ACTIVE_HIGH":
        set_strip_color(COLOR_RED, start=LED_COUNT // 2, end=LED_COUNT)
        time.sleep(0.5)
        clear_strip()
        time.sleep(0.5)
    set_default()

# Blindspot warning states
def blink_left_blindspot():
    while results["Blindspot Rear Left Status"] == "WARNING_LEVEL_1":
        set_strip_color(COLOR_RED, start=0, end=5)
        time.sleep(0.5)
        clear_strip()
        time.sleep(0.5)
    set_default()

def blink_right_blindspot():
    while results["Blindspot Rear Right Status"] == "WARNING_LEVEL_1":
        set_strip_color(COLOR_RED, start=LED_COUNT - 5, end=LED_COUNT)
        time.sleep(0.5)
        clear_strip()
        time.sleep(0.5)
    set_default()

# Charging state
def set_charging(soc):
    while results["Charge Status"] == 1:  # Charging active
        green_leds = int((soc / 100) * LED_COUNT)
        set_strip_color(COLOR_GREEN, start=0, end=green_leds)
        clear_strip(start=green_leds, end=LED_COUNT)
        time.sleep(0.5)
    set_default()

#Start with Default
set_default()
#endregion

x = threading.Thread(target=heartbeatFunction)
x.start()

for filterEntry in framesToFilter:
    filterData = struct.pack("!BBH", 0x0F, filterEntry[0], filterEntry[1] )
    print("Filter: " + filterData)
    sock.sendto(filterData, (targetIP, targetPort))

doPrint = True

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

            doPrint = False

            if (doPrint):
                print (int(time.time() * 1000), end='')
                print(" ", end='')
                print("can%d " % (frameBusId), end='')
                print("{0:03X}#".format(frameID), end='')

                for payloadByte in frameData:
                    print("{0:08b}".format(payloadByte), end=' ')
                print("")

            unpackedData = struct.unpack("<Q", frameData)[0]

            if(frameID == 1013):
                #ID3F5VCFRONT_lighting
                results["Left Turn Signal Status"], results["Right Turn Signal Status"] = parse_turn_signals(unpackedData)
                if results["Left Turn Signal Status"] == "TURN_SIGNAL_ACTIVE_HIGH":
                    threading.Thread(target=blink_left_signal).start()
                if results["Right Turn Signal Status"] == "TURN_SIGNAL_ACTIVE_HIGH":
                    threading.Thread(target=blink_right_signal).start()
            elif(frameID == 921):
                #ID399DAS_status
                autopilot_hands_on_status, autopilot_state_status, blindspot_rear_left_status, blindspot_rear_right_status = parse_autopilot_and_blindspot_signals(unpackedData)
                results["Autopilot Hands-On Status"] = autopilot_hands_on_status
                results["Autopilot State"] = autopilot_state_status
                results["Blindspot Rear Left Status"] = blindspot_rear_left_status
                results["Blindspot Rear Right Status"] = blindspot_rear_right_status
                if results["Autopilot State"] == "ACTIVE_NOMINAL":
                    set_autopilot()
                if results["Blindspot Rear Left Status"] == "WARNING_LEVEL_1":
                    threading.Thread(target=blink_left_blindspot).start()
                if results["Blindspot Rear Right Status"] == "WARNING_LEVEL_1":
                    threading.Thread(target=blink_right_blindspot).start()
            elif(frameID == 826):
                #ID33AUI_rangeSOC
                results["SoC"] = parse_soc(unpackedData)
            elif(frameID == 516):
                #ID204PCS_chgStatus
                results["Charge Status"] = parse_charge_status(unpackedData)
                if results["Charge Status"] == 1:
                    threading.Thread(target=set_charging, args=(results["SoC"],)).start()
            else:
                print("?")
            print(results)

            packetStart = packetStart + 8
    except:
        sock.sendto(b"bye", (targetIP, targetPort))
        doshutdown = True
        break