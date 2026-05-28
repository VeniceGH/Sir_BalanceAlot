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
        self.FRAME_CENTER_X = 160
        self.speed = 1.0
        self.kp = 0.4
        self.kd = 0.1
        self.previous_error = 0
        self.last_turn = 0
        self.lost_frames = 0
        self.LINE_LOST_THRESHOLD = 2
        self.ROI_Y = 150
        self.obstacle_detected = False
        self.state = "line_follow"
        self.obstacle_sequence = []
        self.sequence_start_time = 0
        self.sequence_index = 0

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self.control_loop, daemon=True)
        self.thread.start()

    def set_mode(self, mode):
        print(f"Switchinng mode to: {mode}")
        self.mode = mode
        self.previous_error = 0

        if mode == "manual":
            send_serial_command("L:0 R:0")

    def manual_command(self, command):
        if self.mode != "manual":
            return
        
        if (command == "FORWARD"):
            send_serial_command("L:10 R:10")
        elif (command == "BACKWARD"):
            send_serial_command("L:-10 R:-10")
        elif (command == "RIGHT"):
            send_serial_command("L:10 R:2")
        elif (command == "LEFT"):
            send_serial_command("L:2 R:10")
        elif (command == "STOP"):
            send_serial_command("L:0 R:0")

    def update_obstacle(self, is_detected: bool):
        self.obstacle_detected = is_detected

        if is_detected:
            if self.state != "obstacle":
                self.start_obstacle_avoidance()
        else:
            self.state = "line_follow"
    
    def control_loop(self):
        while self.running:
            if self.mode == "line_follow":
                if self.state == "line_follow":
                    self.run_line_following()

                elif self.state == "obstacle":
                    self.run_obstacle()
            
            time.sleep(0.01)
    
    def run_line_following(self):
        frame = self.camera.get_frame()

        if frame is None:
            return
        
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        _, thresh = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)

        kernel = np.ones((3,3), np.uint8)
        thresh = cv2.erode(thresh, kernel, iterations=1)
        thresh = cv2.dilate(thresh, kernel, iterations=2)

        roi = thresh[self.ROI_Y:240,:]

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
    
    def start_obstacle_avoidance(self):

        self.obstacle_sequence = [

            ("L:0 R:0", 0.5),

            ("L:1.5 R:-1.5", 0.8),

            ("L:1.5 R:1.5", 1.2),

            ("L:-1.5 R:1.5", 0.8),

            ("L:1.5 R:1.5", 1.5),
        ]

        self.sequence_index = 0
        self.sequence_start_time = time.time()

        self.state = "obstacle"

    def run_obstacle(self):

        if self.sequence_index >= len(self.obstacle_sequence):

            self.state = "line_follow"
            return

        command, duration = self.obstacle_sequence[self.sequence_index]

        print(f"Obstacle sequence step {self.sequence_index}: {command} for {duration}s")
        send_serial_command(command)

        if time.time() - self.sequence_start_time > duration:

            self.sequence_index += 1
            self.sequence_start_time = time.time()


