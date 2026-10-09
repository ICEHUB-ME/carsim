"""Bird's-eye/top-down car and path renderer."""

from __future__ import annotations

import math
from collections import deque

import pygame


BACKGROUND_COLOR = (28, 30, 32)
GRID_COLOR = (55, 55, 55)
GRID_LABEL_COLOR = (155, 155, 155)
ORIGIN_COLOR = (180, 180, 180)
CAR_BODY_COLOR = (220, 220, 220)
CAR_OUTLINE_COLOR = (25, 25, 25)
PATH_COLOR = (80, 210, 255)
HEADING_COLOR = (255, 90, 90)
CAR_LENGTH_M = 2.2
CAR_WIDTH_M = 1.1
HEADING_ARROW_LENGTH_M = 1.9


class BirdsEyeRenderer:
    def __init__(
        self,
        width: int,
        height: int,
        pixels_per_meter: float = 7.5,
        max_path_points: int = 10_000,
        grid_spacing_m: float = 10.0,
    ) -> None:
        self.width = width
        self.height = height
        self.scale = pixels_per_meter
        self.grid_spacing_m = grid_spacing_m
        self.path = deque(maxlen=max_path_points)

    def reset_path(self) -> None:
        self.path.clear()

    def add_point(self, x: float, y: float) -> None:
        self.path.append((x, y))

    def world_to_screen(
        self, x: float, y: float, camera_x: float, camera_y: float
    ) -> tuple[int, int]:
        sx = self.width * 0.5 + (x - camera_x) * self.scale
        sy = self.height * 0.5 - (y - camera_y) * self.scale
        return int(round(sx)), int(round(sy))

    def _draw_grid(
        self,
        surface: pygame.Surface,
        camera_x: float,
        camera_y: float,
    ) -> None:
        grid_spacing_m = self.grid_spacing_m
        half_w = self.width / self.scale / 2.0
        half_h = self.height / self.scale / 2.0
        x0 = math.floor((camera_x - half_w) / grid_spacing_m) * grid_spacing_m
        x1 = math.ceil((camera_x + half_w) / grid_spacing_m) * grid_spacing_m
        y0 = math.floor((camera_y - half_h) / grid_spacing_m) * grid_spacing_m
        y1 = math.ceil((camera_y + half_h) / grid_spacing_m) * grid_spacing_m

        label_font = pygame.font.SysFont("consolas", 13)
        label_color = GRID_LABEL_COLOR

        x = x0
        while x <= x1:
            a = self.world_to_screen(x, camera_y - half_h, camera_x, camera_y)
            b = self.world_to_screen(x, camera_y + half_h, camera_x, camera_y)
            pygame.draw.line(surface, GRID_COLOR, a, b, 1)
            label = label_font.render(f"{x:g} m", True, label_color)
            label_x = min(max(a[0] + 3, 2), self.width - label.get_width() - 2)
            surface.blit(label, (label_x, 4))
            x += grid_spacing_m

        y = y0
        while y <= y1:
            a = self.world_to_screen(camera_x - half_w, y, camera_x, camera_y)
            b = self.world_to_screen(camera_x + half_w, y, camera_x, camera_y)
            pygame.draw.line(surface, GRID_COLOR, a, b, 1)
            label = label_font.render(f"{y:g} m", True, label_color)
            label_y = min(max(a[1] + 3, 2), self.height - label.get_height() - 2)
            surface.blit(label, (4, label_y))
            y += grid_spacing_m

    def draw(self, surface: pygame.Surface, car) -> None:
        camera_x = car.state.x
        camera_y = car.state.y
        surface.fill(BACKGROUND_COLOR)
        self._draw_grid(surface, camera_x, camera_y)

        # Path
        if len(self.path) >= 2:
            points = [
                self.world_to_screen(x, y, camera_x, camera_y)
                for x, y in self.path
            ]
            pygame.draw.lines(surface, PATH_COLOR, False, points, 3)

        # World origin marker.
        ox, oy = self.world_to_screen(0.0, 0.0, camera_x, camera_y)
        pygame.draw.circle(surface, ORIGIN_COLOR, (ox, oy), 4)

        self._draw_vehicle(surface, car, camera_x, camera_y)

    def _draw_vehicle(self, surface, car, camera_x: float, camera_y: float) -> None:
        """Draw the car body and heading cue in world coordinates."""
        length = CAR_LENGTH_M
        width = CAR_WIDTH_M
        heading = car.state.heading
        forward_x, forward_y = math.cos(heading), math.sin(heading)
        left_x, left_y = -forward_y, forward_x
        center_x, center_y = car.state.x, car.state.y
        front_center = (
            center_x + forward_x * length / 2,
            center_y + forward_y * length / 2,
        )
        rear_center = (
            center_x - forward_x * length / 2,
            center_y - forward_y * length / 2,
        )
        corners_world = [
            (
                front_center[0] + left_x * width / 2,
                front_center[1] + left_y * width / 2,
            ),
            (
                front_center[0] - left_x * width / 2,
                front_center[1] - left_y * width / 2,
            ),
            (
                rear_center[0] - left_x * width / 2,
                rear_center[1] - left_y * width / 2,
            ),
            (
                rear_center[0] + left_x * width / 2,
                rear_center[1] + left_y * width / 2,
            ),
        ]
        corners = [
            self.world_to_screen(x, y, camera_x, camera_y)
            for x, y in corners_world
        ]
        pygame.draw.polygon(surface, CAR_BODY_COLOR, corners)
        pygame.draw.polygon(surface, CAR_OUTLINE_COLOR, corners, 3)

        tip = self.world_to_screen(
            center_x + forward_x * HEADING_ARROW_LENGTH_M,
            center_y + forward_y * HEADING_ARROW_LENGTH_M,
            camera_x,
            camera_y,
        )
        center = self.world_to_screen(center_x, center_y, camera_x, camera_y)
        pygame.draw.line(surface, HEADING_COLOR, center, tip, 4)