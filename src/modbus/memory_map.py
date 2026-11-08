"""Industrial Modbus Memory Map Specification.

Compliant with IEC 61131-3 & Modbus Application Protocol V1.1b3.
Standard addressing for PLC controllers (Siemens S7-1200/1500, Mitsubishi iQ-R/FX5U, Beckhoff ADS/Modbus).
"""

from enum import IntEnum


class DefectType(IntEnum):
    NONE = 0
    SURFACE_SCRATCH = 1
    BODY_CRACK = 2
    MISSING_COMPONENT = 3
    CONTAMINATION_STAIN = 4
    DIMENSION_OUT_OF_SPEC = 5


class SystemStatus(IntEnum):
    INIT = 0
    IDLE = 1
    RUNNING = 2
    WARNING = 3
    EMERGENCY_STOP = 4


# --- COIL REGISTERS (0x - Read/Write Single/Multiple Coils, FC01 / FC05 / FC15) ---
COIL_REJECTOR_ACTUATOR = 0       # 00001: Pneumatic rejection cylinder solenoid valve (1 = Extend, 0 = Retract)
COIL_CONVEYOR_RUN = 1            # 00002: Main conveyor belt motor contactor (1 = Run, 0 = Stop)
COIL_ALARM_BEACON_RED = 2        # 00003: Tower lamp red beacon (Defect alert)
COIL_ALARM_BEACON_GREEN = 3      # 00004: Tower lamp green beacon (Normal operation)
COIL_SYSTEM_RESET_CMD = 4        # 00005: Remote reset trigger from HMI/SCADA

# --- DISCRETE INPUTS (1x - Read-Only Inputs, FC02) ---
INPUT_PE_TRIGGER_SENSOR = 0      # 10001: Photoelectric part-present arrival sensor (1 = Part detected)
INPUT_AIR_PRESSURE_OK = 1        # 10002: Pneumatic regulator pressure switch (1 = Normal, 0 = Low air pressure)
INPUT_SAFETY_LIGHT_CURTAIN = 2   # 10003: Safety light curtain interlock (1 = Clear, 0 = Tripped)

# --- HOLDING REGISTERS (4x - Read/Write Registers, FC03 / FC06 / FC16) ---
REG_TOTAL_INSPECTED_COUNT = 0    # 40001: Total parts inspected (UInt16)
REG_PASSED_COUNT = 1             # 40002: Total parts passed inspection (UInt16)
REG_DEFECT_COUNT = 2             # 40003: Total parts rejected/defective (UInt16)
REG_DEFECT_RATE_BPS = 3          # 40004: Defect rate in basis points (e.g. 350 = 3.50%)
REG_LAST_DEFECT_TYPE = 4         # 40005: Last detected DefectType enum value
REG_SYSTEM_STATUS = 5            # 40006: SystemStatus enum value
REG_CAMERA_FPS = 6               # 40007: Vision system FPS (scaled x10, e.g. 295 = 29.5 FPS)
REG_INSPECTION_TIME_MS = 7       # 40008: Last frame inference latency in ms
REG_REJECTION_PULSE_MS = 8       # 40009: Configured pneumatic pulse duration (default 250ms)
REG_HEARTBEAT_COUNTER = 9        # 40010: Incrementing watchdog heartbeat from Edge AI
