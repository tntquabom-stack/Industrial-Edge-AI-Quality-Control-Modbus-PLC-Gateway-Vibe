"""FastAPI Web HMI & SCADA Interface.

Serves live MJPEG camera streams, WebSocket real-time telemetry,
and REST control endpoints for conveyor line operators.
"""

import asyncio
from pathlib import Path
import time
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from src.modbus.memory_map import COIL_CONVEYOR_RUN
from src.modbus.plc_simulator import SimulatedPLC
from src.pipeline.qc_pipeline import QCPipeline

STATIC_DIR = Path(__file__).parent / "static"


def create_app(pipeline: QCPipeline, plc: Optional[SimulatedPLC] = None) -> FastAPI:
    app = FastAPI(title="Industrial Edge AI QC Gateway", version="1.0.0")

    # Mount static assets
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        html_file = STATIC_DIR / "index.html"
        if html_file.exists():
            return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
        return HTMLResponse("<h2>Industrial Edge AI QC Gateway Running</h2>")

    @app.get("/video_feed")
    def video_feed():
        """MJPEG video stream endpoint for HTML <img> tag."""
        def frame_generator():
            while True:
                jpeg = pipeline.get_latest_jpeg()
                if jpeg:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                    )
                time.sleep(0.033)  # ~30 FPS

        return StreamingResponse(
            frame_generator(),
            media_type="multipart/x-mixed-replace; boundary=frame"
        )

    @app.get("/api/status")
    async def get_status():
        payload = pipeline.get_status_payload()
        if plc:
            payload["plc_registers"] = plc.get_snapshot()
        return JSONResponse(payload)

    @app.post("/api/modbus/reject")
    async def manual_reject_trigger():
        pipeline.modbus.trigger_rejector(pulse_ms=250)
        return {"status": "ok", "action": "Pneumatic rejector solenoid pulsed (250ms)"}

    @app.post("/api/modbus/toggle_conveyor")
    async def toggle_conveyor():
        if plc:
            current = plc.coils[COIL_CONVEYOR_RUN]
            new_state = not current
            pipeline.modbus.write_coil(COIL_CONVEYOR_RUN, new_state)
            return {"status": "ok", "conveyor_running": new_state}
        return {"status": "error", "message": "PLC simulator not attached"}

    @app.websocket("/ws/telemetry")
    async def websocket_telemetry(websocket: WebSocket):
        await websocket.accept()
        try:
            while True:
                payload = pipeline.get_status_payload()
                if plc:
                    payload["plc_registers"] = plc.get_snapshot()
                await websocket.send_json(payload)
                await asyncio.sleep(0.15)  # ~6.6 Hz updates
        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    return app
