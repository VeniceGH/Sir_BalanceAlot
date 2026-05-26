from picamera2 import Picamera2
import threading
import time

class Camera:
    def __init__(self):
        self.picam2 = Picamera2()
        config = self.picam2.create_preview_configuration(
            main={"size": (640, 480)}
        )
        self.picam2.configure(config)

        self.latest_frame = None
        self.lock = threading.Lock()
        self.running = False

    def start(self):
        self.picam2.start()
        self.running = True

        thread = threading.Thread(target=self._loop, daemon=True)
        thread.start()

    def _loop(self):
        while self.running:
            frame = self.picam2.capture_array()

            with self.lock:
                self.latest_frame = frame

            time.sleep(0.01)  # ~30–60 FPS

    def get_frame(self):
        with self.lock:
            return self.latest_frame
