"""Simulated Industrial Modbus TCP PLC Server.

Emulates a Siemens S7-1200 or Mitsubishi FX5U PLC with Modbus TCP server capability.
Maintains state of digital coils (pneumatic rejector, conveyor motor, tower lamps)
and 16-bit holding registers (production counters, defect rates, latency).
"""

import socket
import struct
import threading
import time
import logging
from typing import Dict, List, Optional
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
    REG_SYSTEM_STATUS,
    REG_CAMERA_FPS,
    REG_INSPECTION_TIME_MS,
    REG_REJECTION_PULSE_MS,
    REG_HEARTBEAT_COUNTER,
    SystemStatus,
)

logger = logging.getLogger("PLC_Simulator")


class SimulatedPLC:
    """In-memory Modbus TCP Server simulating an industrial PLC."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5020, unit_id: int = 1):
        self.host = host
        self.port = port
        self.unit_id = unit_id

        # Modbus Data Stores (0-indexed)
        self.coils: List[bool] = [False] * 128
        self.discrete_inputs: List[bool] = [False] * 128
        self.holding_registers: List[int] = [0] * 128
        self.input_registers: List[int] = [0] * 128

        # Initial PLC State
        self.coils[COIL_CONVEYOR_RUN] = True
        self.coils[COIL_ALARM_BEACON_GREEN] = True
        self.holding_registers[REG_SYSTEM_STATUS] = int(SystemStatus.RUNNING)
        self.holding_registers[REG_REJECTION_PULSE_MS] = 250

        # Operational metrics
        self.rejections_triggered = 0
        self.lock = threading.Lock()
        self.running = False
        self._server_socket: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the Modbus TCP server in a background daemon thread."""
        self.running = True
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.host, self.port))
        self._server_socket.listen(5)
        self._server_socket.settimeout(1.0)

        self._thread = threading.Thread(target=self._run_server, daemon=True, name="ModbusServerThread")
        self._thread.start()
        logger.info(f"Simulated PLC Modbus TCP Server listening on {self.host}:{self.port} (Unit ID: {self.unit_id})")

    def stop(self) -> None:
        """Stop the server socket."""
        self.running = False
        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("Simulated PLC stopped.")

    def _run_server(self) -> None:
        while self.running:
            try:
                client_sock, addr = self._server_socket.accept()
                threading.Thread(target=self._handle_client, args=(client_sock,), daemon=True).start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.debug(f"Socket accept exception: {e}")
                break

    def _handle_client(self, client_sock: socket.socket) -> None:
        client_sock.settimeout(5.0)
        while self.running:
            try:
                # Read Modbus TCP MBAP Header (7 bytes: TxID[2], ProtoID[2], Length[2], UnitID[1])
                header = client_sock.recv(7)
                if not header or len(header) < 7:
                    break

                tx_id, proto_id, length, unit_id = struct.unpack(">HHHB", header)
                if proto_id != 0:
                    continue  # Invalid Modbus TCP protocol

                pdu_len = length - 1
                pdu = client_sock.recv(pdu_len)
                if len(pdu) < pdu_len:
                    break

                response_pdu = self._process_pdu(pdu)
                if response_pdu:
                    resp_length = len(response_pdu) + 1
                    resp_header = struct.pack(">HHHB", tx_id, proto_id, resp_length, unit_id)
                    client_sock.sendall(resp_header + response_pdu)

            except socket.timeout:
                continue
            except Exception as e:
                break
        try:
            client_sock.close()
        except Exception:
            pass

    def _process_pdu(self, pdu: bytes) -> bytes:
        if not pdu:
            return b""
        fc = pdu[0]

        with self.lock:
            # FC 01: Read Coils
            if fc == 0x01:
                start_addr, count = struct.unpack(">HH", pdu[1:5])
                byte_count = (count + 7) // 8
                byte_vals = [0] * byte_count
                for i in range(count):
                    addr = start_addr + i
                    if addr < len(self.coils) and self.coils[addr]:
                        byte_vals[i // 8] |= (1 << (i % 8))
                return struct.pack(f">BBB{byte_count}B", fc, byte_count, *byte_vals)

            # FC 02: Read Discrete Inputs
            elif fc == 0x02:
                start_addr, count = struct.unpack(">HH", pdu[1:5])
                byte_count = (count + 7) // 8
                byte_vals = [0] * byte_count
                for i in range(count):
                    addr = start_addr + i
                    if addr < len(self.discrete_inputs) and self.discrete_inputs[addr]:
                        byte_vals[i // 8] |= (1 << (i % 8))
                return struct.pack(f">BBB{byte_count}B", fc, byte_count, *byte_vals)

            # FC 03: Read Holding Registers
            elif fc == 0x03:
                start_addr, count = struct.unpack(">HH", pdu[1:5])
                byte_count = count * 2
                vals = [self.holding_registers[start_addr + i] if (start_addr + i) < len(self.holding_registers) else 0 for i in range(count)]
                return struct.pack(f">BBB{count}H", fc, byte_count, *vals)

            # FC 05: Write Single Coil
            elif fc == 0x05:
                addr, val = struct.unpack(">HH", pdu[1:5])
                is_on = (val == 0xFF00)
                if addr < len(self.coils):
                    prev = self.coils[addr]
                    self.coils[addr] = is_on
                    if addr == COIL_REJECTOR_ACTUATOR and is_on and not prev:
                        self.rejections_triggered += 1
                        logger.warning(f"⚡ [PLC ACTUATOR] Pneumatic Rejector Cylinder FIRED! Total rejects: {self.rejections_triggered}")
                return pdu[:5]

            # FC 06: Write Single Register
            elif fc == 0x06:
                addr, val = struct.unpack(">HH", pdu[1:5])
                if addr < len(self.holding_registers):
                    self.holding_registers[addr] = val & 0xFFFF
                return pdu[:5]

            # FC 16 (0x10): Write Multiple Registers
            elif fc == 0x10:
                start_addr, count, byte_count = struct.unpack(">HHB", pdu[1:6])
                vals = struct.unpack(f">{count}H", pdu[6:6 + byte_count])
                for i, v in enumerate(vals):
                    addr = start_addr + i
                    if addr < len(self.holding_registers):
                        self.holding_registers[addr] = v & 0xFFFF
                return struct.pack(">BHH", fc, start_addr, count)

            # Unsupported Function Code Exception
            else:
                return struct.pack(">BB", fc | 0x80, 0x01)

    def get_snapshot(self) -> Dict[str, any]:
        """Return human-readable state of PLC for inspection / dashboard."""
        with self.lock:
            return {
                "conveyor_running": self.coils[COIL_CONVEYOR_RUN],
                "rejector_active": self.coils[COIL_REJECTOR_ACTUATOR],
                "beacon_red": self.coils[COIL_ALARM_BEACON_RED],
                "beacon_green": self.coils[COIL_ALARM_BEACON_GREEN],
                "total_inspected": self.holding_registers[REG_TOTAL_INSPECTED_COUNT],
                "passed_count": self.holding_registers[REG_PASSED_COUNT],
                "defect_count": self.holding_registers[REG_DEFECT_COUNT],
                "defect_rate_pct": round(self.holding_registers[REG_DEFECT_RATE_BPS] / 100.0, 2),
                "last_defect_type": self.holding_registers[REG_LAST_DEFECT_TYPE],
                "system_status": self.holding_registers[REG_SYSTEM_STATUS],
                "rejections_triggered": self.rejections_triggered,
                "fps": round(self.holding_registers[REG_CAMERA_FPS] / 10.0, 1),
                "latency_ms": self.holding_registers[REG_INSPECTION_TIME_MS],
            }
