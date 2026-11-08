import unittest
import numpy as np
from src.vision.detector import EdgeAIDefectDetector, InspectionResult
from src.vision.synthetic_conveyor import SyntheticConveyorBelt, SyntheticPart


class TestVisionInspection(unittest.TestCase):
    def test_synthetic_conveyor_frame_shape(self):
        conveyor = SyntheticConveyorBelt(width=640, height=480)
        frame = conveyor.update_and_render()
        self.assertIsInstance(frame, np.ndarray)
        self.assertEqual(frame.shape, (480, 640, 3))
        self.assertEqual(frame.dtype, np.uint8)

    def test_edge_ai_detector_execution(self):
        conveyor = SyntheticConveyorBelt(width=640, height=480)
        detector = EdgeAIDefectDetector(confidence_threshold=0.6, min_defect_area_px=5)

        # Run for 15 frames
        results = []
        for _ in range(15):
            frame = conveyor.update_and_render()
            res = detector.inspect(frame)
            self.assertIsInstance(res, InspectionResult)
            self.assertGreaterEqual(res.inspection_time_ms, 0.0)
            self.assertIsNotNone(res.annotated_frame)
            self.assertEqual(res.annotated_frame.shape, (480, 640, 3))
            results.append(res)

        self.assertEqual(len(results), 15)

    def test_micro_scratch_sensitivity(self):
        detector = EdgeAIDefectDetector(min_defect_area_px=5)

        # Test micro scratch near center bore
        cb = SyntheticConveyorBelt(640, 480)
        p = SyntheticPart(320, 240, 1)
        p.has_defect = True
        p.defect_type = 1
        p.defect_details = {"dx": 10, "dy": 12, "len": 22, "angle": 1.15}
        cb.parts = [p]
        frame = cb.update_and_render()

        res = detector.inspect(frame)
        self.assertTrue(res.part_present)
        self.assertTrue(res.is_defective)
        self.assertGreaterEqual(len(res.defects), 1)

    def test_clean_conforming_part_has_zero_false_positives(self):
        detector = EdgeAIDefectDetector(min_defect_area_px=5)

        cb = SyntheticConveyorBelt(640, 480)
        p = SyntheticPart(320, 240, 2)
        p.has_defect = False
        p.defect_type = 0
        cb.parts = [p]
        frame = cb.update_and_render()

        res = detector.inspect(frame)
        self.assertTrue(res.part_present)
        self.assertFalse(res.is_defective)
        self.assertEqual(len(res.defects), 0)


if __name__ == "__main__":
    unittest.main()
