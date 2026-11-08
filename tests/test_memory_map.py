import unittest
from src.modbus.memory_map import (
    COIL_REJECTOR_ACTUATOR,
    COIL_CONVEYOR_RUN,
    REG_TOTAL_INSPECTED_COUNT,
    REG_PASSED_COUNT,
    REG_DEFECT_COUNT,
    DefectType,
    SystemStatus,
)


class TestMemoryMap(unittest.TestCase):
    def test_defect_type_enum(self):
        self.assertEqual(DefectType.NONE, 0)
        self.assertEqual(DefectType.SURFACE_SCRATCH, 1)
        self.assertEqual(DefectType.BODY_CRACK, 2)
        self.assertEqual(DefectType.MISSING_COMPONENT, 3)
        self.assertEqual(DefectType.CONTAMINATION_STAIN, 4)

    def test_system_status_enum(self):
        self.assertEqual(SystemStatus.INIT, 0)
        self.assertEqual(SystemStatus.RUNNING, 2)
        self.assertEqual(SystemStatus.EMERGENCY_STOP, 4)

    def test_register_constants(self):
        self.assertEqual(COIL_REJECTOR_ACTUATOR, 0)
        self.assertEqual(COIL_CONVEYOR_RUN, 1)
        self.assertEqual(REG_TOTAL_INSPECTED_COUNT, 0)
        self.assertEqual(REG_PASSED_COUNT, 1)
        self.assertEqual(REG_DEFECT_COUNT, 2)


if __name__ == "__main__":
    unittest.main()
