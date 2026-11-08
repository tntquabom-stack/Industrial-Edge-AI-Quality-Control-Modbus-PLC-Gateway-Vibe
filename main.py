"""Main Entrypoint for Industrial Edge AI QC Gateway.

Launches:
1. Virtual Industrial Modbus TCP PLC Server (Port 5020)
2. Computer Vision & Edge AI Defect Detection Pipeline (30 FPS)
3. Modbus TCP Master Client with Automated Rejection Interlock
4. Real-time FastAPI HMI & SCADA Web Server (Port 8000)
"""

import argparse
import logging
import signal
import sys
import time

try:
    import uvicorn
    from fastapi import FastAPI
except ImportError:
    print("\n[ERROR] Required packages not found!")
    print("Please install requirements by running:")
    print("    pip install -r requirements.txt\n")
    sys.exit(1)

from src.config import AppConfig
from src.modbus.client import ModbusPLCClient
from src.modbus.plc_simulator import SimulatedPLC
from src.pipeline.qc_pipeline import QCPipeline
from src.web.app import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("IndustrialGateway")


def main() -> None:
    parser = argparse.ArgumentParser(description="Industrial Edge AI QC Gateway")
    parser.add_argument("--config", default="config/config.yaml", help="Path to config file")
    parser.add_argument("--port", type=int, default=8000, help="Web HMI port")
    parser.add_argument("--modbus-port", type=int, default=5020, help="Modbus TCP Server port")
    parser.add_argument("--no-sim-plc", action="store_true", help="Connect to external physical PLC instead of internal simulator")
    args = parser.parse_args()

    config = AppConfig.load(args.config)
    if args.port:
        config.web.port = args.port
    if args.modbus_port:
        config.modbus.server_port = args.modbus_port

    logger.info("=" * 65)
    logger.info(f"   STARTING {config.system_name.upper()} v{config.version}")
    logger.info("   Standard: IEC 61131-3 & Modbus Application Protocol V1.1b3")
    logger.info("=" * 65)

    # 1. Start Simulated Modbus TCP PLC Server
    plc_sim = None
    if not args.no_sim_plc:
        logger.info(f"[1/4] Spawning Virtual Industrial PLC on 127.0.0.1:{config.modbus.server_port}...")
        plc_sim = SimulatedPLC(host="127.0.0.1", port=config.modbus.server_port, unit_id=config.modbus.unit_id)
        plc_sim.start()
        time.sleep(0.2)  # Give socket time to bind

    # 2. Start Modbus Client
    logger.info(f"[2/4] Connecting Edge AI Modbus Client to PLC at {config.modbus.server_host}:{config.modbus.server_port}...")
    modbus_client = ModbusPLCClient(
        host=config.modbus.server_host,
        port=config.modbus.server_port,
        unit_id=config.modbus.unit_id,
        timeout=config.modbus.timeout,
    )
    if not modbus_client.connect():
        logger.warning("Could not establish immediate Modbus connection. Will retry in background.")

    # 3. Start Quality Control Vision Pipeline
    logger.info(f"[3/4] Initializing Edge AI Optical Inspection Pipeline (Mode: {config.camera.mode.upper()})...")
    pipeline = QCPipeline(config=config, modbus_client=modbus_client)
    pipeline.start()

    # 4. Start FastAPI HMI Web Server
    logger.info(f"[4/4] Launching Web HMI Dashboard at http://localhost:{config.web.port}...")
    app = create_app(pipeline=pipeline, plc=plc_sim)

    def shutdown(sig, frame):
        logger.info("\nShutting down industrial services...")
        pipeline.stop()
        modbus_client.disconnect()
        if plc_sim:
            plc_sim.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Run Uvicorn ASGI server
    uvicorn.run(app, host=config.web.host, port=config.web.port, log_level="warning")


if __name__ == "__main__":
    main()
