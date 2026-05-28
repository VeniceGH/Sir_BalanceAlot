import time
import serial
import threading

SERIAL_PORT = "/dev/ttyUSB0"
BAUD_RATE = 115200

ser = None
lock = threading.Lock()

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

    with lock:
        ser.write((command + "\n").encode())

def set_obstacle_callback(callback):
    global obstacle_callback
    obstacle_callback = callback

def start_serial_reader():
    t = threading.Thread(target=serial_reader_loop, daemon=True)
    t.start()

def serial_reader_loop():
    while True:
        if ser is None:
            time.sleep(0.5)
            continue

        try:
            line = ser.readline().decode('utf-8', errors='ignore').strip()

            if not line:
                continue

            print("ESP32:", line)

            if line.startswith("OBSTACLE:"):
                value = int(line.split(":")[1])

                if obstacle_callback:
                    obstacle_callback(value == 1)

        except Exception as e:
            print(f"Serial read error: {e}")
            time.sleep(0.1)