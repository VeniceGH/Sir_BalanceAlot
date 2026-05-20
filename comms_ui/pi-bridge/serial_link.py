import time
import serial

SERIAL_PORT = "/dev/ttyUSB0"
BAUD_RATE = 115200

ser = None


def connect_serial():
    global ser

    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        time.sleep(2)
        print(f"Serial connected on {SERIAL_PORT}")
    except Exception as e:
        ser = None
        print(f"Serial not connected: {e}")


def send_serial_command(command):
    if ser is None:
        print(f"Serial unavailable. Would have sent: {command}")
        return

    print(f"Sending to ESP32: {command}")
    ser.write((command + "\n").encode())