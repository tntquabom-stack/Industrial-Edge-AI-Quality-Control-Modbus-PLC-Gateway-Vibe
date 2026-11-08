"""System configuration loader."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict
import json


@dataclass
class CameraConfig:
    mode: str = "synthetic"  # synthetic, webcam, file
    device_id: int = 0
    video_path: str = ""
    fps: int = 30
    width: int = 640
    height: int = 480


@dataclass
class InspectionConfig:
    defect_confidence_threshold: float = 0.65
    min_defect_area_px: int = 5  # Micro-defect sensitivity
    max_defect_area_px: int = 8000
    inspect_interval_ms: int = 100


@dataclass
class ModbusConfig:
    server_host: str = "127.0.0.1"
    server_port: int = 5020
    unit_id: int = 1
    timeout: float = 3.0
    reconnect_interval_s: float = 2.0
    rejection_pulse_ms: int = 250


@dataclass
class WebConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    enable_hmi: bool = True


@dataclass
class AppConfig:
    system_name: str = "Industrial Edge AI QC Gateway"
    version: str = "1.0.0"
    log_level: str = "INFO"
    camera: CameraConfig = field(default_factory=CameraConfig)
    inspection: InspectionConfig = field(default_factory=InspectionConfig)
    modbus: ModbusConfig = field(default_factory=ModbusConfig)
    web: WebConfig = field(default_factory=WebConfig)

    @classmethod
    def load(cls, config_path: str = "config/config.yaml") -> "AppConfig":
        path = Path(config_path)
        data: Dict[str, Any] = {}

        if path.exists():
            try:
                import yaml  # type: ignore
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            except ImportError:
                # If pyyaml is not yet installed, try reading simple key-values or fallback
                pass

        sys_data = data.get("system", {})
        cam_data = data.get("camera", {})
        insp_data = data.get("inspection", {})
        mb_data = data.get("modbus", {})
        web_data = data.get("web", {})

        return cls(
            system_name=sys_data.get("name", "Industrial Edge AI QC Gateway"),
            version=sys_data.get("version", "1.0.0"),
            log_level=sys_data.get("log_level", "INFO"),
            camera=CameraConfig(
                mode=cam_data.get("mode", "synthetic"),
                device_id=int(cam_data.get("device_id", 0)),
                video_path=cam_data.get("video_path", ""),
                fps=int(cam_data.get("fps", 30)),
                width=int(cam_data.get("width", 640)),
                height=int(cam_data.get("height", 480)),
            ),
            inspection=InspectionConfig(
                defect_confidence_threshold=float(insp_data.get("defect_confidence_threshold", 0.65)),
                min_defect_area_px=int(insp_data.get("min_defect_area_px", 45)),
                max_defect_area_px=int(insp_data.get("max_defect_area_px", 8000)),
                inspect_interval_ms=int(insp_data.get("inspect_interval_ms", 100)),
            ),
            modbus=ModbusConfig(
                server_host=mb_data.get("server_host", "127.0.0.1"),
                server_port=int(mb_data.get("server_port", 5020)),
                unit_id=int(mb_data.get("unit_id", 1)),
                timeout=float(mb_data.get("timeout", 3.0)),
                reconnect_interval_s=float(mb_data.get("reconnect_interval_s", 2.0)),
                rejection_pulse_ms=int(mb_data.get("rejection_pulse_ms", 250)),
            ),
            web=WebConfig(
                host=web_data.get("host", "0.0.0.0"),
                port=int(web_data.get("port", 8000)),
                enable_hmi=bool(web_data.get("enable_hmi", True)),
            ),
        )
