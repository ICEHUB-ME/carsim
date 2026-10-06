"""Real-time telemetry HUD and pedal widgets for pygame."""

from __future__ import annotations

import math

import pygame


class HUD:
    """Draw an anchored telemetry panel and throttle/brake pedal widgets."""

    BG = (10, 10, 10, 215)
    TEXT = (235, 235, 235)
    MUTED = (170, 170, 170)
    BORDER = (95, 95, 95)
    FILL = (90, 190, 255)

    def __init__(self) -> None:
        self.font = pygame.font.SysFont("consolas", 18)
        self.small = pygame.font.SysFont("consolas", 15)
        self.title = pygame.font.SysFont("consolas", 22, bold=True)
        self.mode_font = pygame.font.SysFont("consolas", 16, bold=True)
        self.pedal_label = pygame.font.SysFont("consolas", 16, bold=True)
        self.pedal_value = pygame.font.SysFont("consolas", 18, bold=True)

    def _text(
        self,
        surface: pygame.Surface,
        text: str,
        x: int,
        y: int,
        font=None,
        color=None,
    ) -> None:
        surface.blit(
            (font or self.font).render(text, True, color or self.TEXT),
            (x, y),
        )

    def _draw_pedal(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        label: str,
        value: float,
    ) -> None:
        value = max(0.0, min(1.0, value))
        label_surface = self.pedal_label.render(label, True, self.TEXT)
        value_surface = self.pedal_value.render(f"{value * 100:3.0f}%", True, self.TEXT)

        surface.blit(
            label_surface,
            (rect.centerx - label_surface.get_width() // 2, rect.top - 44),
        )
        surface.blit(
            value_surface,
            (rect.centerx - value_surface.get_width() // 2, rect.top - 23),
        )

        pygame.draw.rect(surface, (22, 22, 22), rect, border_radius=6)
        pygame.draw.rect(surface, self.BORDER, rect, 2, border_radius=6)

        fill_h = int(rect.height * value)
        if fill_h > 0:
            fill_rect = pygame.Rect(
                rect.left + 3,
                rect.bottom - 3 - fill_h,
                rect.width - 6,
                fill_h,
            )
            pygame.draw.rect(surface, self.FILL, fill_rect, border_radius=4)

    def draw_pedals(self, surface: pygame.Surface, car) -> None:
        """Draw throttle/brake widgets using the actual current driver inputs."""
        margin = 24
        pedal_w, pedal_h = 58, 135
        gap = 28
        bottom = surface.get_height() - 54
        left = margin

        throttle_rect = pygame.Rect(left, bottom - pedal_h, pedal_w, pedal_h)
        brake_rect = pygame.Rect(
            throttle_rect.right + gap, bottom - pedal_h, pedal_w, pedal_h
        )

        self._draw_pedal(surface, throttle_rect, "THROTTLE", car.state.throttle)
        self._draw_pedal(surface, brake_rect, "BRAKE", car.state.brake_pedal)

    def draw(
        self,
        surface: pygame.Surface,
        car,
        params,
        controls_help: bool = True,
        mode: str = "GAME",
    ) -> None:
        """Draw live telemetry in the upper-right corner."""
        s = car.state
        panel_w = 405
        panel_h = 558
        margin = 14
        panel_rect = pygame.Rect(
            surface.get_width() - panel_w - margin,
            margin,
            panel_w,
            panel_h,
        )

        live = [
            f"speed                 {s.speed:8.3f} m/s",
            f"acceleration          {s.acceleration:8.3f} m/s²",
            f"lateral acceleration  {s.lateral_acceleration:8.3f} m/s²",
            f"slip angle            {math.degrees(s.slip_angle):8.3f} deg",
            f"throttle              {s.throttle * 100:8.1f} %",
            f"brake pedal           {s.brake_pedal * 100:8.1f} %",
            f"steering angle        {s.steering_angle:8.3f} deg",
            f"lateral velocity      {s.lateral_velocity:8.3f} m/s",
            f"propulsion force      {s.propulsion_force:8.1f} N",
            f"drag force            {s.drag_force:8.1f} N",
            f"rolling resistance    {s.rolling_resistance:8.1f} N",
            f"braking force         {s.braking_force:8.1f} N",
            f"lateral force         {s.lateral_force:8.1f} N",
        ]
        constants = [
            f"mass                  {params.mass:8.1f} kg",
            f"friction coefficient  {params.friction_coefficient:8.3f}",
            f"drag coefficient      {params.drag_coefficient:8.3f}",
            f"rolling resistance    {params.rolling_resistance_coefficient:8.3f}",
            f"gear ratio            {params.gear_ratio:8.3f}:1",
            f"wheel radius          {params.wheel_radius:8.3f} m",
        ]

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill(self.BG)
        pygame.draw.rect(panel, self.BORDER, panel.get_rect(), 1, border_radius=8)
        self._text(panel, "CAR PHYSICS SIMULATOR", 14, 10, self.title)
        self._text(panel, mode, panel_w - self.mode_font.size(mode)[0] - 14, 14, self.mode_font, self.MUTED)

        y = 48
        self._text(panel, "REAL-TIME", 14, y, self.small, self.MUTED)
        y += 22
        for line in live:
            self._text(panel, line, 14, y)
            y += 20

        y += 8
        self._text(panel, "CONSTANT PARAMETERS", 14, y, self.small, self.MUTED)
        y += 22
        for line in constants:
            self._text(panel, line, 14, y)
            y += 20

        surface.blit(panel, panel_rect.topleft)
        self.draw_pedals(surface, car)

        if controls_help:
            hint = "W throttle   S / SPACE brake   A/D steer   ESC quit"
        else:
            hint = "CSV REPLAY: player controls disabled   ESC quit"
        hint_surface = self.small.render(hint, True, self.MUTED)
        surface.blit(hint_surface, (24, surface.get_height() - 28))