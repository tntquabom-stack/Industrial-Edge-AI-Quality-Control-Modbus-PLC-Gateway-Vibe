"""Unified Video Acquisition Interface.

Abstracts video capture sources across synthetic conveyor simulator,
USB Industrial GigE / UVC webcams, and pre-recorded industrial test video clips.
"""

import io
import time
from typing import Optional, Tuple
import numpy as np
from PIL import Image

from src.vision.synthetic_conveyor import SyntheticConveyorBelt


class VideoStream:
    """Manages acquisition and frame encoding from active camera source."""

    def __init__(self, mode: str = "synthetic", device_id: int = 0, video_path: str = "", width: int = 640, height: int = 480, fps: int = 30):
        self.mode = mode.lower()
        self.device_id = device_id
        self.video_path = video_path
        self.width = width
        self.height = height
        self.fps = fps

        self.synthetic_source: Optional[SyntheticConveyorBelt] = None
        self.cv2_cap = None
        self.is_running = False

    def start(self) -> None:
        self.is_running = True
        if self.mode == "synthetic":
            self.synthetic_source = SyntheticConveyorBelt(width=self.width, height=self.height)
        else:
            try:
                import cv2  # type: ignore
                src = self.video_path if self.mode == "file" and self.video_path else self.device_id
                self.cv2_cap = cv2.VideoCapture(src)
                self.cv2_cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                self.cv2_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            except Exception:
                # If OpenCV or physical camera fails, gracefully fallback to synthetic
                self.mode = "synthetic"
                self.synthetic_source = SyntheticConveyorBelt(width=self.width, height=self.height)

    def read_frame(self) -> Tuple[bool, np.ndarray]:
        if not self.is_running:
            return False, np.zeros((self.height, self.width, 3), dtype=np.uint8)

        if self.mode == "synthetic" or self.synthetic_source is not None:
            frame = self.synthetic_source.update_and_render()
            return True, frame

        if self.cv2_cap and self.cv2_cap.isOpened():
            ret, frame = self.cv2_cap.read()
            if ret:
                # Convert BGR to RGB
                try:
                    import cv2  # type: ignore
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                except Exception:
                    pass
                return True, frame
            elif self.mode == "file":
                # Loop video file
                self.cv2_cap.set(1, 0)

        # Fallback empty frame
        return False, np.zeros((self.height, self.width, 3), dtype=np.uint8)

    def stop(self) -> None:
        self.is_running = False
        if self.cv2_cap:
            try:
                self.cv2_cap.release()
            except Exception:
                pass
            self.cv2_cap = None

    @staticmethod
    def encode_jpeg(frame: np.ndarray, quality: int = 80) -> bytes:
        """Compress numpy RGB image array into JPEG binary byte stream."""
        try:
            import cv2  # type: ignore
            # cv2 expects BGR
            bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            _, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
            return buf.tobytes()
        except Exception:
            # Fallback to PIL
            img = Image.fromarray(frame)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality)
            return buf.getvalue()
