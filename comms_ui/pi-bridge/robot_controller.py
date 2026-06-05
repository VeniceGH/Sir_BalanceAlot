import threading
import time
import cv2
import numpy as np
from serial_link import send_serial_command

class RobotController:
    def __init__(self, camera):
        self.camera = camera
        self.mode = "manual"
        self.running = False
        self.thread = None
        self.FRAME_CENTER_X = 320 #160
        self.speed = 1.2
        self.kp = 0.35
        self.kd = 0.15
        self.previous_error = 0
        self.last_turn = 0
        self.lost_frames = 0
        self.LINE_LOST_THRESHOLD = 2
        self.ROI_Y = 390 #150
        self.obstacle_detected = False
        self.obstacle_report_pending = False
        self.qr_detector = cv2.QRCodeDetector()
        self.approach_started = False
        self.approach_start_time = None
        self.last_qr_data = None
        self.obstacle_report_pending = False
        self.control_generation = 0
        self.mode_lock = threading.Lock()
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        self.aruco_detector = cv2.aruco.ArucoDetector(self.aruco_dict)
        self.marker_counter = 0
        self.last_marker_id = None
        self.last_marker_time = 0
        self.marker_detected = False

    def start(self):
        self.running = True
        send_serial_command("MODE:MANUAL")
        send_serial_command("L:0 R:0")
        self.thread = threading.Thread(target=self.control_loop, daemon=True)
        self.thread.start()

    def set_mode(self, mode):
        with self.mode_lock:
            print(f"Switchinng mode to: {mode}")
            self.mode = mode
            self.control_generation += 1
        self.previous_error = 0

        if mode == "manual":
            send_serial_command("L:0 R:0")
            self.obstacle_detected = False

    def manual_command(self, command):
        if self.mode != "manual":
            return
        
        if (command == "FORWARD"):
            send_serial_command("L:5 R:5")
        elif (command == "BACKWARD"):
            send_serial_command("L:-5 R:-5")
        elif (command == "RIGHT"):
            send_serial_command("L:5 R:-5")  
        elif (command == "LEFT"):
            send_serial_command("L:-5 R:5")
        elif (command == "STOP"):
            send_serial_command("L:0 R:0")

    def update_obstacle(self, value):
        if value == 1:
            self.obstacle_detected = True
        elif value == 0:
            self.obstacle_detected = False

    def control_loop(self):
        while self.running:
            if self.mode == "line_follow":

                frame = self.camera.get_frame()
                if frame is None:
                    continue

                if not self.obstacle_detected:
                    self.marker_counter += 1
                    if self.marker_counter % 5 == 0:
                        self.detect_markers(frame)
                    if not self.marker_detected:
                        self.run_line_following(frame)
                    else:
                        self.interpret_marker(frame)
                else:
                    self.approach_obstacle(frame)
            time.sleep(0.01)
    
    def run_line_following(self, frame):
        my_generation = self.control_generation
        
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        _, thresh = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)

        kernel = np.ones((3,3), np.uint8)
        thresh = cv2.erode(thresh, kernel, iterations=1)
        thresh = cv2.dilate(thresh, kernel, iterations=2)

        #roi = thresh[self.ROI_Y:240,:]
        roi = thresh[self.ROI_Y:480,:]

        contours, _ = cv2.findContours(roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        output = frame.copy()

        line_detected = False

        if len(contours) > 0:
            largest = max(contours, key=cv2.contourArea)

            if cv2.contourArea(largest) > 500:
                line_detected = True

                largest_shifted = largest.copy()
                largest_shifted[:,:,1] += self.ROI_Y
                cv2.drawContours(output, [largest_shifted], -1, (0, 255, 0), 2)

                M = cv2.moments(largest)
                if M["m00"] != 0:
                    cx = int(M['m10']/M['m00'])
                    cy = int(M['m01']/M['m00']) + self.ROI_Y

                    error = (cx - self.FRAME_CENTER_X) / self.FRAME_CENTER_X

                    cv2.circle(output, (cx,cy), 8, (0, 0, 255), -1)
                    cv2.putText(output, f"Error: {error}", (20, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                    
                    derivative = error - self.previous_error

                    self.previous_error = error

                    turn = (self.kp*error) + (self.kd*derivative)

                    self.last_turn = turn

                    left_speed = self.speed + turn
                    right_speed = self.speed - turn

                    left_speed = max(0, min(5, left_speed))
                    right_speed = max(0, min(5, right_speed))

                    if my_generation != self.control_generation:
                        return

                    send_serial_command(f"L:{left_speed:.2f} R:{right_speed:.2f}")

        if not line_detected:
            self.lost_frames += 1
        else:
            self.lost_frames = 0

        if self.lost_frames > self.LINE_LOST_THRESHOLD:

            if self.last_turn > 0:
                left = self.speed
                right = -self.speed
            else:
                left = -self.speed
                right = self.speed

            left = max(-5, min(5, left))
            right = max(-5, min(5, right))

            if my_generation != self.control_generation:
                return

            send_serial_command(f"L:{left:.2f} R:{right:.2f}")

            cv2.putText(
                output,
                "RECOVERY MODE",
                (20, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2
            )

        self.camera.set_debug_frame(output)
    
    def approach_obstacle(self, frame):
        if not self.approach_started:
            self.approach_started = True
            self.approach_start_time = time.time()
            self.obstacle_report_pending = True
            send_serial_command("MODE:OBSTACLE_APPROACH")
            send_serial_command("L:0.3 R:0.3")

        output = frame.copy()

        cv2.putText(
            output,
            "APPROACHING QR",
            (20, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 0),
            2
        )

        data, bbox, _ = self.qr_detector.detectAndDecode(frame)

        if bbox is not None:
            bbox = bbox.astype(int)

            # Draw box around QR code
            for i in range(len(bbox[0])):
                pt1 = tuple(bbox[0][i])
                pt2 = tuple(bbox[0][(i + 1) % len(bbox[0])])

                cv2.line(output, pt1, pt2, (0, 255, 0), 2)

            # Print detected data
            if data:
                send_serial_command("L:0 R:0")
                self.last_qr_data = data
                self.approach_started = False
                send_serial_command(f"MODE:OBSTACLE_AVOID")
                cv2.putText(
                    output,
                    data,
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2
                )
                self.camera.set_debug_frame(output)
                return

        if time.time() - self.approach_start_time > 60:
            self.last_qr_data = "UNKNOWN"
            send_serial_command(f"MODE:OBSTACLE_AVOID")
            self.approach_started = False
    
        self.camera.set_debug_frame(output)

    def detect_markers(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        corners, ids, _ = self.aruco_detector.detectMarkers(gray)
        if ids is None:
            self.marker_detected = False
            self.last_marker_id = None
        else:
            self.marker_detected = True
            send_serial_command("L:0 R:0")
            self.last_marker_id = int(ids[0][0])
    
    def interpret_marker(self,frame):
        if self.last_marker_id is None:
            return
        if not self.obstacle_report_pending:
            self.marker_detected = False
            return

        if 0<= self.last_marker_id < 15:
            self.aquire_deviation(frame)
        elif self.last_marker_id == 15:
            send_serial_command("L:0 R:0")
            send_serial_command("MODE:DEVIATION_RETURN")
    
    def aquire_deviation(self, frame):        
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        _, thresh = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)

        kernel = np.ones((3,3), np.uint8)
        thresh = cv2.erode(thresh, kernel, iterations=1)
        thresh = cv2.dilate(thresh, kernel, iterations=2)

        roi = thresh[self.ROI_Y:240,:]

        contours, _ = cv2.findContours(roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        output = frame.copy()

        line_detected = False

        send_serial_command(f"L:{self.speed} R:{-self.speed}")

        if len(contours) > 0:
            largest = max(contours, key=cv2.contourArea)

            if cv2.contourArea(largest) > 500:
                self.marker_detected = False

        if not line_detected:
            self.lost_frames += 1
        else:
            self.lost_frames = 0

        if self.lost_frames > self.LINE_LOST_THRESHOLD:

            left = self.speed
            right = -self.speed

            left = max(-5, min(5, left))
            right = max(-5, min(5, right))

            send_serial_command(f"L:{left:.2f} R:{right:.2f}")

            cv2.putText(
                output,
                "DEVIATION RECOVERY",
                (20, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2
            )

        self.camera.set_debug_frame(output)