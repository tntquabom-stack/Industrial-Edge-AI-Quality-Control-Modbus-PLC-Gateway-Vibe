import time
import unittest
from src.modbus.client import ModbusPLCClient
from src.modbus.plc_simulator import SimulatedPLC
from src.modbus.memory_map import (
    COIL_REJECTOR_ACTUATOR,
    COIL_CONVEYOR_RUN,
    REG_TOTAL_INSPECTED_COUNT,
    REG_PASSED_COUNT,
    REG_DEFECT_COUNT,
)


class TestModbusCommunication(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = SimulatedPLC(host="127.0.0.1", port=5999, unit_id=1)
        cls.server.start()
        time.sleep(0.2)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_01_client_connection_and_coil_write(self):
        client = ModbusPLCClient(host="127.0.0.1", port=5999, unit_id=1, timeout=2.0)
        self.assertTrue(client.connect())

        # Test write coil
        success = client.write_coil(COIL_CONVEYOR_RUN, False)
        self.assertTrue(success)
        self.assertFalse(self.server.coils[COIL_CONVEYOR_RUN])

        success = client.write_coil(COIL_CONVEYOR_RUN, True)
        self.assertTrue(success)
        self.assertTrue(self.server.coils[COIL_CONVEYOR_RUN])

        client.disconnect()

    def test_02_telemetry_batch_sync(self):
        client = ModbusPLCClient(host="127.0.0.1", port=5999, unit_id=1, timeout=2.0)
        self.assertTrue(client.connect())

        # Batch sync FC16
        success = client.sync_telemetry(
            total_inspected=150,
            passed=140,
            defect=10,
            last_defect_type=1,
            fps=29.8,
            latency_ms=14,
        )
        self.assertTrue(success)

        snap = self.server.get_snapshot()
        self.assertEqual(snap["total_inspected"], 150)
        self.assertEqual(snap["passed_count"], 140)
        self.assertEqual(snap["defect_count"], 10)
        self.assertEqual(snap["defect_rate_pct"], 6.67)
        self.assertEqual(snap["fps"], 29.8)
        self.assertEqual(snap["latency_ms"], 14)

        client.disconnect()


if __name__ == "__main__":
    unittest.main()
