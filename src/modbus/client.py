"""Industrial Modbus TCP Client for Edge AI Vision Systems.

Handles connection pooling, automatic reconnects, thread-safe register/coil writes,
and timed pneumatic actuator firing.
"""

import socket
import struct
import threading
import time
import logging
from typing import List, Optional
from src.modbus.memory_map import (
    COIL_REJECTOR_ACTUATOR,
    COIL_CONVEYOR_RUN,
    COIL_ALARM_BEACON_RED,
    COIL_ALARM_BEACON_GREEN,
    REG_TOTAL_INSPECTED_COUNT,
    REG_PASSED_COUNT,
    REG_DEFECT_COUNT,
    REG_DEFECT_RATE_BPS,
    REG_LAST_DEFECT_TYPE,
    REG_CAMERA_FPS,
    REG_INSPECTION_TIME_MS,
    REG_HEARTBEAT_COUNTER,
)

logger = logging.getLogger("ModbusClient")


class ModbusPLCClient:
    """Modbus TCP Client communicating directly with shop-floor PLCs."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5020, unit_id: int = 1, timeout: float = 3.0):
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self.timeout = timeout

        self.sock: Optional[socket.socket] = None
        self.connected = False
        self.tx_counter = 1
        self.lock = threading.Lock()
        self.heartbeat_val = 0

    def connect(self) -> bool:
        """Establish TCP connection to Modbus PLC Server."""
        with self.lock:
            if self.connected:
                return True
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(self.timeout)
                self.sock.connect((self.host, self.port))
                self.connected = True
                logger.info(f"Connected to Modbus PLC at {self.host}:{self.port}")
                return True
            except Exception as e:
                self.connected = False
                logger.error(f"Failed to connect to Modbus PLC at {self.host}:{self.port} -> {e}")
                return False

    def disconnect(self) -> None:
        with self.lock:
            self.connected = False
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
                self.sock = None

    def _next_tx_id(self) -> int:
        self.tx_counter = (self.tx_counter + 1) & 0xFFFF
        if self.tx_counter == 0:
            self.tx_counter = 1
        return self.tx_counter

    def _send_pdu(self, pdu: bytes) -> Optional[bytes]:
        """Send Modbus PDU wrapped in MBAP header and return response PDU."""
        if not self.connected or not self.sock:
            if not self.connect():
                return None

        try:
            tx_id = self._next_tx_id()
            length = len(pdu) + 1  # PDU + Unit ID
            header = struct.pack(">HHHB", tx_id, 0, length, self.unit_id)
            self.sock.sendall(header + pdu)

            resp_hdr = self.sock.recv(7)
            if not resp_hdr or len(resp_hdr) < 7:
                raise ConnectionResetError("Connection lost during header recv")

            r_tx, r_proto, r_len, r_unit = struct.unpack(">HHHB", resp_hdr)
            r_pdu_len = r_len - 1
            resp_pdu = self.sock.recv(r_pdu_len)
            return resp_pdu
        except Exception as e:
            logger.warning(f"Modbus transmission error: {e}. Reconnecting...")
            self.disconnect()
            return None

    def write_coil(self, coil_addr: int, state: bool) -> bool:
        """FC05: Write Single Coil."""
        with self.lock:
            val = 0xFF00 if state else 0x0000
            pdu = struct.pack(">BHH", 0x05, coil_addr, val)
            res = self._send_pdu(pdu)
            return res is not None and res[0] == 0x05

    def write_holding_register(self, reg_addr: int, val: int) -> bool:
        """FC06: Write Single Register."""
        with self.lock:
            pdu = struct.pack(">BHH", 0x06, reg_addr, val & 0xFFFF)
            res = self._send_pdu(pdu)
            return res is not None and res[0] == 0x06

    def write_multiple_registers(self, start_addr: int, values: List[int]) -> bool:
        """FC16: Write Multiple Registers."""
        with self.lock:
            count = len(values)
            byte_count = count * 2
            pdu = struct.pack(f">BHHB{count}H", 0x10, start_addr, count, byte_count, *[v & 0xFFFF for v in values])
            res = self._send_pdu(pdu)
            return res is not None and res[0] == 0x10

    def trigger_rejector(self, pulse_ms: int = 250) -> None:
        """Non-blocking pneumatic rejector firing with alert tower lamp actuation."""
        def _pulse():
            logger.info("Firing pneumatic rejector cylinder...")
            self.write_coil(COIL_REJECTOR_ACTUATOR, True)
            self.write_coil(COIL_ALARM_BEACON_RED, True)
            self.write_coil(COIL_ALARM_BEACON_GREEN, False)

            time.sleep(pulse_ms / 1000.0)

            self.write_coil(COIL_REJECTOR_ACTUATOR, False)
            self.write_coil(COIL_ALARM_BEACON_RED, False)
            self.write_coil(COIL_ALARM_BEACON_GREEN, True)
            logger.info("Pneumatic cylinder retracted to home position.")

        threading.Thread(target=_pulse, daemon=True).start()

    def sync_telemetry(
        self,
        total_inspected: int,
        passed: int,
        defect: int,
        last_defect_type: int,
        fps: float,
        latency_ms: int,
    ) -> bool:
        """Batch write statistics to PLC Holding Registers in a single Modbus FC16 frame."""
        defect_rate_bps = int(round(defect / total_inspected * 10000)) if total_inspected > 0 else 0
        fps_scaled = int(fps * 10)

        # Registers 40001 to 40008
        values = [
            total_inspected & 0xFFFF,
            passed & 0xFFFF,
            defect & 0xFFFF,
            defect_rate_bps & 0xFFFF,
            last_defect_type & 0xFFFF,
            2,  # RUNNING
            fps_scaled & 0xFFFF,
            latency_ms & 0xFFFF,
        ]
        return self.write_multiple_registers(REG_TOTAL_INSPECTED_COUNT, values)

    def send_heartbeat(self) -> None:
        """Update watchdog heartbeat register."""
        self.heartbeat_val = (self.heartbeat_val + 1) & 0xFFFF
        self.write_holding_register(REG_HEARTBEAT_COUNTER, self.heartbeat_val)
