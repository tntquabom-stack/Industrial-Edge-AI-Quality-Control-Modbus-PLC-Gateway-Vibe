"""Core Industrial Quality Control Pipeline.

Orchestrates frame capture, computer vision inspection, stateful part tracking,
Modbus PLC actuator triggering, and real-time telemetry publishing.
"""

from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
import logging
import threading
import time
from typing import Deque, Dict, List, Optional
import numpy as np

from src.config import AppConfig
from src.modbus.client import ModbusPLCClient
from src.modbus.memory_map import DefectType
from src.vision.camera import VideoStream
from src.vision.detector import EdgeAIDefectDetector, InspectionResult

logger = logging.getLogger("QCPipeline")


@dataclass
class QCEventLog:
    id: int
    timestamp: str
    result: str  # "PASS" or "REJECT"
    defect_label: str
    confidence: float
    latency_ms: float


class QCPipeline:
    """Threaded high-throughput industrial inspection pipeline."""

    def __init__(self, config: AppConfig, modbus_client: ModbusPLCClient):
        self.config = config
        self.modbus = modbus_client

        self.stream = VideoStream(
            mode=config.camera.mode,
            device_id=config.camera.device_id,
            video_path=config.camera.video_path,
            width=config.camera.width,
            height=config.camera.height,
            fps=config.camera.fps,
        )

        self.detector = EdgeAIDefectDetector(
            confidence_threshold=config.inspection.defect_confidence_threshold,
            min_defect_area_px=config.inspection.min_defect_area_px,
        )

        # Statistics & Counters
        self.total_inspected = 0
        self.total_passed = 0
        self.total_defect = 0
        self.last_defect_type = DefectType.NONE
        self.fps = 0.0
        self.last_latency_ms = 0.0

        # Stateful part debouncer (avoids duplicate trigger on single part passing zone)
        self.part_currently_in_station = False
        self.current_part_defective = False
        self.current_part_defects: List[str] = []

        # Event log history (Ring buffer)
        self.event_log: Deque[QCEventLog] = deque(maxlen=50)
        self.event_id_counter = 1

        # Thread synchronization
        self.latest_frame_jpeg: Optional[bytes] = None
        self.latest_annotated_frame: Optional[np.ndarray] = None
        self.lock = threading.Lock()
        self.running = False
        self.worker_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self.running = True
        self.stream.start()
        self.worker_thread = threading.Thread(target=self._run_loop, daemon=True, name="QCPipelineThread")
        self.worker_thread.start()
        logger.info("Industrial QC Pipeline started successfully.")

    def stop(self) -> None:
        self.running = False
        self.stream.stop()
        if self.worker_thread:
            self.worker_thread.join(timeout=2.0)
        logger.info("Industrial QC Pipeline stopped.")

    def _run_loop(self) -> None:
        frame_times = deque(maxlen=20)
        last_modbus_sync = time.time()
        last_heartbeat = time.time()

        while self.running:
            t0 = time.perf_counter()
            ret, frame = self.stream.read_frame()
            if not ret:
                time.sleep(0.01)
                continue

            # Run Computer Vision / AI Inspection
            res: InspectionResult = self.detector.inspect(frame)
            self.last_latency_ms = res.inspection_time_ms

            # Part Tracking & Stateful Decision Machine
            self._process_part_tracking(res)

            # Store frame for web stream
            jpeg = VideoStream.encode_jpeg(res.annotated_frame)
            with self.lock:
                self.latest_frame_jpeg = jpeg
                self.latest_annotated_frame = res.annotated_frame

            # Calculate Moving Average FPS
            dt = time.perf_counter() - t0
            frame_times.append(dt)
            if frame_times:
                self.fps = round(len(frame_times) / sum(frame_times), 1)

            # Sync with PLC Holding Registers at ~5Hz
            now = time.time()
            if now - last_modbus_sync > 0.2:
                last_modbus_sync = now
                self.modbus.sync_telemetry(
                    total_inspected=self.total_inspected,
                    passed=self.total_passed,
                    defect=self.total_defect,
                    last_defect_type=int(self.last_defect_type),
                    fps=self.fps,
                    latency_ms=int(self.last_latency_ms),
                )

            # Send watchdog heartbeat every 1s
            if now - last_heartbeat > 1.0:
                last_heartbeat = now
                self.modbus.send_heartbeat()

            # Target ~30 FPS loop pace
            elapsed = time.perf_counter() - t0
            sleep_time = (1.0 / self.config.camera.fps) - elapsed
            if sleep_time > 0.002:
                time.sleep(sleep_time)

    def _process_part_tracking(self, res: InspectionResult) -> None:
        """State machine to detect rising edge of part arrival and falling edge of part departure."""
        # Rising edge: Workpiece enters inspection zone
        if res.part_present and not self.part_currently_in_station:
            self.part_currently_in_station = True
            self.current_part_defective = False
            self.current_part_defects.clear()

        # Part is under inspection
        if self.part_currently_in_station and res.part_present:
            if res.is_defective and not self.current_part_defective:
                self.current_part_defective = True
                self.current_part_defects = [d.label for d in res.defects]
                self.last_defect_type = res.defects[0].defect_type if res.defects else DefectType.SURFACE_SCRATCH

                # Trigger Pneumatic Rejection Actuator through Modbus
                self.modbus.trigger_rejector(pulse_ms=self.config.modbus.rejection_pulse_ms)

        # Falling edge: Workpiece departed inspection zone
        if not res.part_present and self.part_currently_in_station:
            self.part_currently_in_station = False
            self.total_inspected += 1

            now_str = datetime.now().strftime("%H:%M:%S.%f")[:-4]
            if self.current_part_defective:
                self.total_defect += 1
                event = QCEventLog(
                    id=self.event_id_counter,
                    timestamp=now_str,
                    result="REJECT",
                    defect_label=", ".join(self.current_part_defects) or "DEFECT",
                    confidence=0.91,
                    latency_ms=self.last_latency_ms,
                )
                logger.warning(f"🚫 Part #{self.total_inspected} REJECTED -> {event.defect_label}")
            else:
                self.total_passed += 1
                event = QCEventLog(
                    id=self.event_id_counter,
                    timestamp=now_str,
                    result="PASS",
                    defect_label="NONE",
                    confidence=0.99,
                    latency_ms=self.last_latency_ms,
                )
                logger.info(f"✅ Part #{self.total_inspected} PASSED")

            self.event_id_counter += 1
            self.event_log.appendleft(event)

    def get_latest_jpeg(self) -> Optional[bytes]:
        with self.lock:
            return self.latest_frame_jpeg

    def get_status_payload(self) -> Dict[str, any]:
        defect_rate = round((self.total_defect / self.total_inspected * 100.0), 2) if self.total_inspected > 0 else 0.0
        return {
            "total_inspected": self.total_inspected,
            "total_passed": self.total_passed,
            "total_defect": self.total_defect,
            "defect_rate_pct": defect_rate,
            "fps": self.fps,
            "latency_ms": self.last_latency_ms,
            "modbus_connected": self.modbus.connected,
            "events": [asdict(e) for e in list(self.event_log)[:15]],
        }
