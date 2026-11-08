"""Synthetic Industrial Conveyor Belt Simulator.

Generates photorealistic industrial inspection frames with moving machined parts,
conveyor rollers, guide rails, and randomized defects (scratches, cracks, missing components, stains).
Enables turnkey testing and demonstration without physical industrial hardware.
"""

import math
import random
import time
from typing import Dict, List, Optional, Tuple
import numpy as np


class SyntheticPart:
    """Represents a discrete industrial manufactured part traveling on conveyor."""

    def __init__(self, x: float, y: float, part_id: int):
        self.x = x
        self.y = y
        self.part_id = part_id
        self.width = 110
        self.height = 110
        self.inspected = False

        # Randomly assign defect (approx 25% defect rate for good demo visibility)
        self.has_defect = random.random() < 0.28
        self.defect_type: int = 0
        self.defect_details: Dict[str, any] = {}

        if self.has_defect:
            self.defect_type = random.choice([1, 2, 3, 4])
            # Choose a quadrant away from center bore (r=18) to place surface flaws
            side_x = random.choice([-1, 1])
            side_y = random.choice([-1, 1])
            base_ox = side_x * random.randint(18, 28)
            base_oy = side_y * random.randint(18, 28)

            if self.defect_type == 1:  # Scratch
                self.defect_details = {
                    "dx": base_ox,
                    "dy": base_oy,
                    "len": random.randint(22, 38),
                    "angle": random.uniform(0, math.pi),
                }
            elif self.defect_type == 2:  # Crack (branching jagged line on outer body)
                start_x, start_y = base_ox, base_oy
                points = [(start_x, start_y)]
                curr_x, curr_y = start_x, start_y
                for _ in range(4):
                    curr_x += random.randint(-8, 8)
                    curr_y += random.randint(-8, 8)
                    points.append((curr_x, curr_y))
                self.defect_details = {"points": points}
            elif self.defect_type == 3:  # Missing Screw / Hole defect
                self.defect_details = {
                    "screw_idx": random.choice([0, 1, 2, 3])
                }
            elif self.defect_type == 4:  # Contamination Stain
                self.defect_details = {
                    "cx": base_ox,
                    "cy": base_oy,
                    "radius": random.randint(7, 13)
                }


class SyntheticConveyorBelt:
    """Generates continuous video frames of an automated conveyor assembly line."""

    def __init__(self, width: int = 640, height: int = 480, speed_px_per_sec: float = 180.0):
        self.width = width
        self.height = height
        self.speed = speed_px_per_sec
        self.parts: List[SyntheticPart] = []
        self.last_time = time.time()
        self.part_counter = 1
        self.spawn_distance_px = 240
        self.roller_offset = 0.0

        # Initialize with one starting part
        self.parts.append(SyntheticPart(x=50.0, y=height / 2.0, part_id=self.part_counter))
        self.part_counter += 1

    def update_and_render(self) -> np.ndarray:
        now = time.time()
        dt = max(0.001, min(0.1, now - self.last_time))
        self.last_time = now

        # Update conveyor roller animation offset
        self.roller_offset = (self.roller_offset + self.speed * dt) % 40.0

        # Move parts forward
        for part in self.parts:
            part.x += self.speed * dt

        # Spawn new part if gap is sufficient
        if not self.parts or self.parts[-1].x > self.spawn_distance_px:
            self.parts.append(SyntheticPart(x=-60.0, y=self.height / 2.0, part_id=self.part_counter))
            self.part_counter += 1

        # Remove parts that exited right boundary
        self.parts = [p for p in self.parts if p.x < (self.width + 120)]

        # Render background conveyor frame
        frame = self._render_conveyor()

        # Render each manufactured metal workpiece
        for part in self.parts:
            self._render_part(frame, part)

        # Raw frame returned cleanly without artificial laser line contamination
        return frame

    def _render_conveyor(self) -> np.ndarray:
        frame = np.full((self.height, self.width, 3), 35, dtype=np.uint8)  # Dark industrial rubber belt

        # Conveyor steel guide rails (Top and bottom)
        frame[0:45, :, :] = [70, 75, 80]
        frame[self.height - 45:self.height, :, :] = [70, 75, 80]
        frame[43:45, :, :] = [130, 135, 140]  # Rail bevel edge
        frame[self.height - 45:self.height - 43, :, :] = [130, 135, 140]

        # Belt texture / roller lines
        x_roller = int(self.roller_offset)
        while x_roller < self.width:
            frame[45:self.height - 45, x_roller:min(self.width, x_roller + 2), :] = [45, 45, 48]
            x_roller += 40

        return frame

    def _render_part(self, frame: np.ndarray, part: SyntheticPart) -> None:
        px = int(part.x)
        py = int(part.y)
        half_w = part.width // 2
        half_h = part.height // 2

        x1 = max(0, px - half_w)
        y1 = max(0, py - half_h)
        x2 = min(self.width, px + half_w)
        y2 = min(self.height, py + half_h)

        if x1 >= x2 or y1 >= y2:
            return

        # Machined aluminum base block (brushed silver)
        base_color = np.array([195, 200, 205], dtype=np.uint8)
        bevel_color = np.array([120, 125, 130], dtype=np.uint8)

        # Draw workpiece body
        frame[y1:y2, x1:x2, :] = base_color

        # Draw bevel chamfers
        if px - half_w >= 0 and px + half_w <= self.width:
            frame[y1:y1 + 4, x1:x2, :] = [230, 230, 235]
            frame[y2 - 4:y2, x1:x2, :] = bevel_color
            frame[y1:y2, x1:x1 + 4, :] = [230, 230, 235]
            frame[y1:y2, x2 - 4:x2, :] = bevel_color

        # 4 Mountholes / Screws at corners
        screw_offsets = [(-35, -35), (35, -35), (-35, 35), (35, 35)]
        for idx, (sox, soy) in enumerate(screw_offsets):
            sx = px + sox
            sy = py + soy
            # Check if this screw is the missing defect
            is_missing = (part.has_defect and part.defect_type == 3 and part.defect_details.get("screw_idx") == idx)
            self._draw_circle(frame, sx, sy, radius=9, color=[70, 75, 80] if is_missing else [140, 145, 150])
            if not is_missing:
                self._draw_circle(frame, sx, sy, radius=4, color=[220, 220, 220])  # Screw head reflection

        # Center bore hole
        self._draw_circle(frame, px, py, radius=18, color=[50, 55, 60])
        self._draw_circle(frame, px, py, radius=14, color=[30, 30, 35])

        # Render defect if present
        if part.has_defect:
            self._render_defect(frame, part, px, py)

    def _render_defect(self, frame: np.ndarray, part: SyntheticPart, px: int, py: int) -> None:
        dtype = part.defect_type
        det = part.defect_details

        if dtype == 1:  # Surface Scratch
            cx = px + det.get("dx", 0)
            cy = py + det.get("dy", 0)
            length = det.get("len", 30)
            angle = det.get("angle", 0.5)
            x_end = int(cx + length * math.cos(angle))
            y_end = int(cy + length * math.sin(angle))
            self._draw_line(frame, cx, cy, x_end, y_end, color=[40, 40, 45], thickness=2)

        elif dtype == 2:  # Body Crack (jagged fissure)
            pts = det.get("points", [])
            for i in range(len(pts) - 1):
                x_a = px + pts[i][0]
                y_a = py + pts[i][1]
                x_b = px + pts[i + 1][0]
                y_b = py + pts[i + 1][1]
                self._draw_line(frame, x_a, y_a, x_b, y_b, color=[30, 20, 20], thickness=2)

        elif dtype == 4:  # Contamination Stain (dark grease/oil blotch)
            cx = px + det.get("cx", 0)
            cy = py + det.get("cy", 0)
            rad = det.get("radius", 12)
            self._draw_circle(frame, cx, cy, radius=rad, color=[40, 45, 30])

    def _render_sensor_zone(self, frame: np.ndarray) -> None:
        # Inspection zone crosshair / Optical trigger line at x = width / 2
        sensor_x = self.width // 2
        # Vertical laser scan beam
        frame[45:self.height - 45, sensor_x:sensor_x + 1, :] = [0, 220, 255]  # Bright amber PE optical beam

    def _draw_circle(self, frame: np.ndarray, cx: int, cy: int, radius: int, color: List[int]) -> None:
        h, w, _ = frame.shape
        y_min = max(0, cy - radius)
        y_max = min(h, cy + radius + 1)
        x_min = max(0, cx - radius)
        x_max = min(w, cx + radius + 1)
        if x_min >= x_max or y_min >= y_max:
            return

        yy, xx = np.ogrid[y_min - cy:y_max - cy, x_min - cx:x_max - cx]
        mask = (xx * xx + yy * yy) <= (radius * radius)
        frame[y_min:y_max, x_min:x_max][mask] = color

    def _draw_line(self, frame: np.ndarray, x0: int, y0: int, x1: int, y1: int, color: List[int], thickness: int = 1) -> None:
        # Bresenham-like algorithm for drawing line without requiring external cv2
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        h, w, _ = frame.shape

        while True:
            for tx in range(-thickness // 2, (thickness + 1) // 2):
                for ty in range(-thickness // 2, (thickness + 1) // 2):
                    cur_x, cur_y = x0 + tx, y0 + ty
                    if 0 <= cur_x < w and 0 <= cur_y < h:
                        frame[cur_y, cur_x] = color

            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy
