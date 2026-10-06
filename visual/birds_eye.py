"""Bird's-eye/top-down car and path renderer."""

from __future__ import annotations

import math
from collections import deque

import pygame


class BirdsEyeRenderer:
    def __init__(
        self,
        width: int,
        height: int,
        pixels_per_meter: float = 7.5,
        max_path_points: int = 10_000,
    ) -> None:
        self.width = width
        self.height = height
        self.scale = pixels_per_meter
        self.path = deque(maxlen=max_path_points)

    def reset_path(self) -> None:
        self.path.clear()

    def add_point(self, x: float, y: float) -> None:
        self.path.append((x, y))

    def world_to_screen(self, x: float, y: float, camera_x: float, camera_y: float) -> tuple[int, int]:
        sx = self.width * 0.5 + (x - camera_x) * self.scale
        sy = self.height * 0.5 - (y - camera_y) * self.scale
        return int(round(sx)), int(round(sy))

    def _draw_grid(self, surface: pygame.Surface, camera_x: float, camera_y: float) -> None:
        grid_spacing_m = 10.0
        half_w = self.width / self.scale / 2.0
        half_h = self.height / self.scale / 2.0
        x0 = math.floor((camera_x - half_w) / grid_spacing_m) * grid_spacing_m
        x1 = math.ceil((camera_x + half_w) / grid_spacing_m) * grid_spacing_m
        y0 = math.floor((camera_y - half_h) / grid_spacing_m) * grid_spacing_m
        y1 = math.ceil((camera_y + half_h) / grid_spacing_m) * grid_spacing_m

        x = x0
        while x <= x1:
            a = self.world_to_screen(x, camera_y - half_h, camera_x, camera_y)
            b = self.world_to_screen(x, camera_y + half_h, camera_x, camera_y)
            pygame.draw.line(surface, (55, 55, 55), a, b, 1)
            x += grid_spacing_m

        y = y0
        while y <= y1:
            a = self.world_to_screen(camera_x - half_w, y, camera_x, camera_y)
            b = self.world_to_screen(camera_x + half_w, y, camera_x, camera_y)
            pygame.draw.line(surface, (55, 55, 55), a, b, 1)
            y += grid_spacing_m

    def draw(self, surface: pygame.Surface, car) -> None:
        camera_x = car.state.x
        camera_y = car.state.y
        surface.fill((28, 30, 32))
        self._draw_grid(surface, camera_x, camera_y)

        # Path
        if len(self.path) >= 2:
            points = [self.world_to_screen(x, y, camera_x, camera_y) for x, y in self.path]
            pygame.draw.lines(surface, (80, 210, 255), False, points, 3)

        # World origin marker.
        ox, oy = self.world_to_screen(0.0, 0.0, camera_x, camera_y)
        pygame.draw.circle(surface, (180, 180, 180), (ox, oy), 4)

        # Car footprint: a simple 2.2 m x 1.1 m rectangle with a nose triangle.
        length = 2.2
        width = 1.1
        heading = car.state.heading
        fx, fy = math.cos(heading), math.sin(heading)
        lx, ly = -fy, fx
        center_x, center_y = car.state.x, car.state.y
        front_center = (center_x + fx * length / 2, center_y + fy * length / 2)
        rear_center = (center_x - fx * length / 2, center_y - fy * length / 2)
        corners_world = [
            (front_center[0] + lx * width / 2, front_center[1] + ly * width / 2),
            (front_center[0] - lx * width / 2, front_center[1] - ly * width / 2),
            (rear_center[0] - lx * width / 2, rear_center[1] - ly * width / 2),
            (rear_center[0] + lx * width / 2, rear_center[1] + ly * width / 2),
        ]
        corners = [self.world_to_screen(x, y, camera_x, camera_y) for x, y in corners_world]
        pygame.draw.polygon(surface, (220, 220, 220), corners)
        pygame.draw.polygon(surface, (25, 25, 25), corners, 3)

        # Heading arrow.
        tip = self.world_to_screen(
            center_x + fx * 1.9,
            center_y + fy * 1.9,
            camera_x,
            camera_y,
        )
        center = self.world_to_screen(center_x, center_y, camera_x, camera_y)
        pygame.draw.line(surface, (255, 90, 90), center, tip, 4)
