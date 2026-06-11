import time
import serial
import threading

SERIAL_PORT = "/dev/ttyUSB0"
BAUD_RATE = 115200

ser = None

last_sent_command = None
command_lock = threading.Lock()

obstacle_callback = None

serial_reader = None

running = False

latest_telemetry = {
    "time_ms": 0,
    "angle_deg": 0.0,
    "gyro_dps": 0.0,
    "motor_left": 0.0,
    "motor_right": 0.0,
    "fuel_percent": 100.0,
    "mode": "NO DATA",
    "package_dropped": False,
}

def get_latest_telemetry():
    return latest_telemetry

def connect_serial():
    global ser, running

    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        running = True
        time.sleep(2)
        print(f"Serial connected on {SERIAL_PORT}")
    except Exception as e:
        ser = None
        print(f"Serial not connected: {e}")

def start_serial():
    global running
    global serial_reader

    running = True

    serial_reader = threading.Thread(target=serial_reader_loop)
    serial_reader.start()

def send_serial_command(command):
    global last_sent_command
    if ser is None:
        print(f"Serial unavailable. Would have sent: {command}")
        return

    with command_lock:
        if last_sent_command == command:
            return
        ser.write((command + "\n").encode())
        print(f"Sending to ESP32: {command}")
        last_sent_command = command

def set_obstacle_callback(callback):
    global obstacle_callback
    obstacle_callback = callback

def serial_reader_loop():
    while running:
        if ser is None:
            time.sleep(0.5)
            continue

        try:
            line = ser.readline().decode('utf-8', errors='ignore').strip()

            if not line:
                continue

            if line.startswith("OBSTACLE:"):
                value = int(line.split(":")[1])

                if obstacle_callback:
                    obstacle_callback(value)

            if line.startswith("TEL:"):
                parts = line[4:].split(",")

                if len(parts) != 7:
                    print(f"Bad telemetry line: {line}")
                    continue

                latest_telemetry["time_ms"] = int(parts[0])
                latest_telemetry["angle_deg"] = float(parts[1])
                latest_telemetry["gyro_dps"] = float(parts[2])
                latest_telemetry["motor_left"] = float(parts[3])
                latest_telemetry["motor_right"] = float(parts[4])
                latest_telemetry["fuel_percent"] = float(parts[5])
                latest_telemetry["mode"] = parts[6]

                continue

        except Exception as e:
            print(f"Serial read error: {e}")
            time.sleep(0.1)

def stop_serial():
    global running
    running = False
    if serial_reader:
        serial_reader.join()
    if ser:
        ser.close()

    