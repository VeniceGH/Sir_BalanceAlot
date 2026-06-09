import time
import serial
import threading

SERIAL_PORT = "/dev/ttyUSB0"
BAUD_RATE = 115200

ser = None

latest_command = None
last_sent_command = None
command_lock = threading.Lock()

obstacle_callback = None

serial_writer = None
serial_reader = None

running = False

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
    global serial_writer
    global serial_reader

    running = True

    serial_writer = threading.Thread(target=serial_writer_loop)
    serial_reader = threading.Thread(target=serial_reader_loop)

    serial_writer.start()
    serial_reader.start()


def send_serial_command(command):
    global latest_command

    if ser is None:
        return

    with command_lock:
        latest_command = command

def serial_writer_loop():
    global latest_command
    global last_sent_command

    while running:
        if ser is None:
            time.sleep(0.5)
            continue

        cmd_to_send = None

        with command_lock:
            if latest_command is not None and latest_command != last_sent_command:
                cmd_to_send = latest_command
                last_sent_command = latest_command
            
        if cmd_to_send:
            try:
                print(f"Sending serial command: {cmd_to_send}")
                ser.write((cmd_to_send + "\n").encode())

            except Exception as e:
                print(f"Serial write error: {e}")
        
        time.sleep(0.1)

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

        except Exception as e:
            print(f"Serial read error: {e}")
            time.sleep(0.1)

def stop_serial():
    global running
    running = False
    if serial_writer:
        serial_writer.join()
    if serial_reader:
        serial_reader.join()
    if ser:
        ser.close()

    