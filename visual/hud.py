"""Real-time telemetry HUD, pedal widgets, and mode/help overlays for pygame."""

from __future__ import annotations

import math

import pygame


class HUD:
    """Draw an anchored telemetry panel and throttle/brake pedal widgets."""

    BG = (10, 10, 10, 222)
    TEXT = (235, 235, 235)
    MUTED = (170, 170, 170)
    BORDER = (95, 95, 95)
    FILL = (90, 190, 255)
    ACTIVE = (120, 220, 130)

    def __init__(self) -> None:
        self.font = pygame.font.SysFont("consolas", 17)
        self.small = pygame.font.SysFont("consolas", 14)
        self.title = pygame.font.SysFont("consolas", 21, bold=True)
        self.mode_font = pygame.font.SysFont("consolas", 15, bold=True)
        self.pedal_label = pygame.font.SysFont("consolas", 15, bold=True)
        self.pedal_value = pygame.font.SysFont("consolas", 18, bold=True)

    def _text(self, surface, text, x, y, font=None, color=None) -> None:
        surface.blit(
            (font or self.font).render(text, True, color or self.TEXT),
            (x, y),
        )

    def _draw_pedal(self, surface, rect, label, value) -> None:
        value = max(0.0, min(1.0, float(value)))
        label_surface = self.pedal_label.render(label, True, self.TEXT)
        value_surface = self.pedal_value.render(f"{value * 100:3.0f}%", True, self.TEXT)

        surface.blit(label_surface, (rect.centerx - label_surface.get_width() // 2, rect.top - 42))
        surface.blit(value_surface, (rect.centerx - value_surface.get_width() // 2, rect.top - 21))

        pygame.draw.rect(surface, (22, 22, 22), rect, border_radius=6)
        pygame.draw.rect(surface, self.BORDER, rect, 2, border_radius=6)

        fill_h = int((rect.height - 6) * value)
        if fill_h > 0:
            fill_rect = pygame.Rect(
                rect.left + 3,
                rect.bottom - 3 - fill_h,
                rect.width - 6,
                fill_h,
            )
            pygame.draw.rect(surface, self.FILL, fill_rect, border_radius=4)

    def draw_pedals(self, surface, car) -> None:
        """Draw throttle/brake widgets using the actual applied car inputs."""
        margin = 24
        pedal_w, pedal_h = 58, 135
        gap = 28
        bottom = surface.get_height() - 56
        left = margin

        throttle_rect = pygame.Rect(left, bottom - pedal_h, pedal_w, pedal_h)
        brake_rect = pygame.Rect(throttle_rect.right + gap, bottom - pedal_h, pedal_w, pedal_h)
        self._draw_pedal(surface, throttle_rect, "THROTTLE", car.state.throttle)
        self._draw_pedal(surface, brake_rect, "BRAKE", car.state.brake_pedal)

    def _draw_manual_panel(self, surface, controls, y0: int) -> int:
        width = 430
        height = 128
        x = surface.get_width() - width - 14
        panel = pygame.Surface((width, height), pygame.SRCALPHA)
        panel.fill((15, 15, 15, 232))
        pygame.draw.rect(panel, self.BORDER, panel.get_rect(), 1, border_radius=6)

        pedal_mode = "ON" if controls.manual_mode else "OFF"
        steer_mode = "ON" if controls.manual_steer_mode else "OFF"
        pedal_color = self.ACTIVE if controls.manual_mode else self.MUTED
        steer_color = self.ACTIVE if controls.manual_steer_mode else self.MUTED

        self._text(panel, f"MANUAL PEDALS: {pedal_mode}", 12, 8, self.small, pedal_color)
        self._text(panel, f"MANUAL STEER:  {steer_mode}", 215, 8, self.small, steer_color)

        throttle = f"Throttle: {controls.manual_throttle * 100:3.0f}%"
        brake = f"Brake:    {controls.manual_brake * 100:3.0f}%"
        steering = f"Steer:   {controls.manual_steering_angle_deg:+5.1f} deg"
        selected = controls.manual_field.upper()
        buffer = controls.manual_buffer or "_"

        self._text(panel, throttle, 12, 30, self.small)
        self._text(panel, brake, 12, 48, self.small)
        self._text(panel, steering, 12, 66, self.small)
        self._text(panel, f"Edit: {selected:8s} {buffer}", 215, 30, self.small)
        self._text(panel, "M pedals   K steering", 215, 49, self.small, self.MUTED)
        self._text(panel, "TAB field   digits + ENTER", 215, 67, self.small, self.MUTED)
        self._text(panel, "BACKSPACE erase   '-' = negative steer", 12, 88, self.small, self.MUTED)
        self._text(panel, "Manual values are direct (no smoothing).", 12, 107, self.small, self.MUTED)

        surface.blit(panel, (x, y0))
        return y0 + height

    def draw(
        self,
        surface,
        car,
        params,
        controls_help: bool = True,
        mode: str = "GAME",
        *,
        step_mode: bool = False,
        manual_controls=None,
    ) -> None:
        """Draw telemetry in the upper-right corner and controls at the bottom."""
        s = car.state
        panel_w = 405
        live_rows = [
            f"time                  {s.time:8.2f} s",
            f"speed                 {s.speed:8.3f} m/s",
            f"acceleration          {s.acceleration:8.3f} m/s²",
            f"lateral acceleration  {s.lateral_acceleration:8.3f} m/s²",
            f"slip angle            {math.degrees(s.slip_angle):8.3f} deg",
            f"throttle              {s.throttle * 100:8.1f} %",
            f"brake pedal           {s.brake_pedal * 100:8.1f} %",
            f"steering angle        {s.steering_angle:8.3f} deg (+R/-L)",
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
        panel_h = 40 + 20 + len(live_rows) * 19 + 26 + len(constants) * 19 + 12
        margin = 14
        panel_rect = pygame.Rect(surface.get_width() - panel_w - margin, margin, panel_w, panel_h)

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill(self.BG)
        pygame.draw.rect(panel, self.BORDER, panel.get_rect(), 1, border_radius=8)
        self._text(panel, "CAR PHYSICS SIMULATOR", 14, 9, self.title)
        mode_text = mode + ("  •  STEP" if step_mode else "")
        mode_surface = self.mode_font.render(mode_text, True, self.MUTED)
        panel.blit(mode_surface, (panel_w - mode_surface.get_width() - 14, 13))

        y = 43
        self._text(panel, "REAL-TIME", 14, y, self.small, self.MUTED)
        y += 21
        for line in live_rows:
            self._text(panel, line, 14, y)
            y += 19

        y += 6
        self._text(panel, "CONSTANT PARAMETERS", 14, y, self.small, self.MUTED)
        y += 21
        for line in constants:
            self._text(panel, line, 14, y)
            y += 19

        surface.blit(panel, panel_rect.topleft)
        self.draw_pedals(surface, car)

        if manual_controls is not None:
            self._draw_manual_panel(surface, manual_controls, surface.get_height() - 196)

        if step_mode:
            hint = "STEP MODE: T toggle realtime   F step exactly 1 physics frame   ESC quit"
        elif controls_help:
            hint = "W throttle   S / SPACE brake   A right   D left   T step   M pedals   K steer   ESC quit"
        else:
            hint = "CSV: W/S/A/D/SPACE disabled   T step   F step   M pedals   K steer   ESC quit"
        hint_surface = self.small.render(hint, True, self.MUTED)
        surface.blit(hint_surface, (24, surface.get_height() - 27))
