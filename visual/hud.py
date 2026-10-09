"""Pygame telemetry, pedal indicators, and controls overlays."""

from __future__ import annotations

import math

import pygame

from config import CarParameters
from simulation.step import Car

PERCENT_SCALE = 100.0


class HUD:
    """Draw vehicle telemetry and input controls over the simulation view."""

    BACKGROUND = (10, 10, 10, 222)
    TEXT = (235, 235, 235)
    MUTED = (170, 170, 170)
    BORDER = (95, 95, 95)
    FILL = (90, 190, 255)
    ACTIVE = (120, 220, 130)

    PANEL_WIDTH = 405
    PANEL_MARGIN = 14
    ROW_HEIGHT = 19
    PEDAL_MARGIN = 24
    PEDAL_WIDTH = 58
    PEDAL_HEIGHT = 135
    PEDAL_GAP = 28
    PEDAL_BOTTOM_MARGIN = 56
    HINT_BOTTOM_MARGIN = 27
    MANUAL_PANEL_BOTTOM = 196

    def __init__(self) -> None:
        self.font = pygame.font.SysFont("consolas", 17)
        self.small = pygame.font.SysFont("consolas", 14)
        self.title = pygame.font.SysFont("consolas", 21, bold=True)
        self.mode_font = pygame.font.SysFont("consolas", 15, bold=True)
        self.pedal_label = pygame.font.SysFont("consolas", 15, bold=True)
        self.pedal_value = pygame.font.SysFont("consolas", 18, bold=True)

    def _text(
        self,
        surface: pygame.Surface,
        text: str,
        x: int,
        y: int,
        font: pygame.font.Font | None = None,
        color: tuple[int, ...] | None = None,
    ) -> None:
        text_surface = (font or self.font).render(
            text,
            True,
            color or self.TEXT,
        )
        surface.blit(text_surface, (x, y))

    def _draw_pedal(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        label: str,
        value: float,
    ) -> None:
        value = max(0.0, min(1.0, float(value)))
        label_surface = self.pedal_label.render(label, True, self.TEXT)
        value_surface = self.pedal_value.render(
            f"{value * PERCENT_SCALE:3.0f}%",
            True,
            self.TEXT,
        )
        surface.blit(
            label_surface,
            (rect.centerx - label_surface.get_width() // 2, rect.top - 42),
        )
        surface.blit(
            value_surface,
            (rect.centerx - value_surface.get_width() // 2, rect.top - 21),
        )

        pygame.draw.rect(surface, (22, 22, 22), rect, border_radius=6)
        pygame.draw.rect(surface, self.BORDER, rect, 2, border_radius=6)
        fill_height = int((rect.height - 6) * value)
        if fill_height:
            fill_rect = pygame.Rect(
                rect.left + 3,
                rect.bottom - 3 - fill_height,
                rect.width - 6,
                fill_height,
            )
            pygame.draw.rect(surface, self.FILL, fill_rect, border_radius=4)

    def draw_pedals(self, surface: pygame.Surface, car: Car) -> None:
        """Show the applied throttle and brake values as vertical gauges."""
        bottom = surface.get_height() - self.PEDAL_BOTTOM_MARGIN
        throttle_rect = pygame.Rect(
            self.PEDAL_MARGIN,
            bottom - self.PEDAL_HEIGHT,
            self.PEDAL_WIDTH,
            self.PEDAL_HEIGHT,
        )
        brake_rect = pygame.Rect(
            throttle_rect.right + self.PEDAL_GAP,
            bottom - self.PEDAL_HEIGHT,
            self.PEDAL_WIDTH,
            self.PEDAL_HEIGHT,
        )
        self._draw_pedal(surface, throttle_rect, "THROTTLE", car.state.throttle)
        self._draw_pedal(surface, brake_rect, "BRAKE", car.state.brake_pedal)

    def _draw_manual_panel(
        self,
        surface: pygame.Surface,
        controls,
        top: int,
    ) -> int:
        panel_width = 430
        panel_height = 128
        left = surface.get_width() - panel_width - self.PANEL_MARGIN
        panel = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        panel.fill((15, 15, 15, 232))
        pygame.draw.rect(
            panel,
            self.BORDER,
            panel.get_rect(),
            1,
            border_radius=6,
        )

        pedal_mode = "ON" if controls.manual_mode else "OFF"
        steer_mode = "ON" if controls.manual_steer_mode else "OFF"
        pedal_color = self.ACTIVE if controls.manual_mode else self.MUTED
        steer_color = self.ACTIVE if controls.manual_steer_mode else self.MUTED
        self._text(
            panel, f"MANUAL PEDALS: {pedal_mode}", 12, 8,
            self.small, pedal_color
        )
        self._text(
            panel, f"MANUAL STEER:  {steer_mode}", 215, 8,
            self.small, steer_color
        )

        throttle = f"Throttle: {controls.manual_throttle * PERCENT_SCALE:6.2f}%"
        brake = f"Brake:    {controls.manual_brake * PERCENT_SCALE:6.2f}%"
        steering = f"Steer:   {controls.manual_steering_angle_deg:+5.1f} deg"
        selected = controls.manual_field.upper()
        buffer = controls.manual_buffer or "_"
        self._text(panel, throttle, 12, 30, self.small)
        self._text(panel, brake, 12, 48, self.small)
        self._text(panel, steering, 12, 66, self.small)
        self._text(panel, f"Edit: {selected:8s} {buffer}", 215, 30, self.small)
        self._text(panel, "M pedals   K steering", 215, 49, self.small, self.MUTED)
        self._text(panel, "TAB field   digits + ENTER", 215, 67, self.small, self.MUTED)
        self._text(
            panel,
            "BACKSPACE erase   '-' = negative steer",
            12,
            88,
            self.small,
            self.MUTED,
        )
        self._text(
            panel,
            "Manual values are direct (no smoothing).",
            12,
            107,
            self.small,
            self.MUTED,
        )
        surface.blit(panel, (left, top))
        return top + panel_height

    def _draw_telemetry_panel(
        self,
        surface: pygame.Surface,
        car: Car,
        params: CarParameters,
        mode: str,
        step_mode: bool,
    ) -> None:
        state = car.state
        live_rows = (
            f"time                  {state.time:8.2f} s",
            f"speed                 {state.speed:8.3f} m/s",
            f"acceleration          {state.acceleration:8.3f} m/s²",
            f"lateral acceleration  {state.lateral_acceleration:8.3f} m/s²",
            f"slip angle            {math.degrees(state.slip_angle):8.3f} deg",
            f"throttle              {state.throttle * PERCENT_SCALE:8.1f} %",
            f"brake pedal           {state.brake_pedal * PERCENT_SCALE:8.1f} %",
            f"steering angle        {state.steering_angle:8.3f} deg (+R/-L)",
            f"lateral velocity      {state.lateral_velocity:8.3f} m/s",
            f"propulsion force      {state.propulsion_force:8.1f} N",
            f"drag force            {state.drag_force:8.1f} N",
            f"rolling resistance    {state.rolling_resistance:8.1f} N",
            f"braking force         {state.braking_force:8.1f} N",
            f"lateral force         {state.lateral_force:8.1f} N",
        )
        parameter_rows = (
            f"mass                  {params.mass:8.1f} kg",
            f"friction coefficient  {params.friction_coefficient:8.3f}",
            f"drag coefficient      {params.drag_coefficient:8.3f}",
            f"rolling resistance    {params.rolling_resistance_coefficient:8.3f}",
            f"gear ratio            {params.gear_ratio:8.3f}:1",
            f"wheel radius          {params.wheel_radius:8.3f} m",
        )
        panel_height = (
            40
            + 20
            + len(live_rows) * self.ROW_HEIGHT
            + 26
            + len(parameter_rows) * self.ROW_HEIGHT
            + 12
        )
        panel_rect = pygame.Rect(
            surface.get_width() - self.PANEL_WIDTH - self.PANEL_MARGIN,
            self.PANEL_MARGIN,
            self.PANEL_WIDTH,
            panel_height,
        )
        panel = pygame.Surface((self.PANEL_WIDTH, panel_height), pygame.SRCALPHA)
        panel.fill(self.BACKGROUND)
        pygame.draw.rect(panel, self.BORDER, panel.get_rect(), 1, border_radius=8)
        self._text(panel, "CAR PHYSICS SIMULATOR", 14, 9, self.title)
        mode_text = mode + ("  •  STEP" if step_mode else "")
        mode_surface = self.mode_font.render(mode_text, True, self.MUTED)
        panel.blit(mode_surface, (self.PANEL_WIDTH - mode_surface.get_width() - 14, 13))

        y = 43
        self._text(panel, "REAL-TIME", 14, y, self.small, self.MUTED)
        y += 21
        for line in live_rows:
            self._text(panel, line, 14, y)
            y += self.ROW_HEIGHT
        y += 6
        self._text(panel, "CONSTANT PARAMETERS", 14, y, self.small, self.MUTED)
        y += 21
        for line in parameter_rows:
            self._text(panel, line, 14, y)
            y += self.ROW_HEIGHT
        surface.blit(panel, panel_rect.topleft)

    def _draw_help_overlay(
        self,
        surface: pygame.Surface,
        car: Car,
        controls_help: bool,
        step_mode: bool,
        manual_controls,
    ) -> None:
        self.draw_pedals(surface, car)
        if manual_controls is not None:
            panel_top = surface.get_height() - self.MANUAL_PANEL_BOTTOM
            self._draw_manual_panel(surface, manual_controls, panel_top)

        if step_mode:
            hint = (
                "STEP MODE: T toggle realtime   F step exactly 1 physics "
                "frame   ESC quit"
            )
        elif controls_help:
            hint = (
                "W throttle   S / SPACE brake   A right   D left   T step   "
                "M pedals   K steer   ESC quit"
            )
        else:
            hint = (
                "CSV: W/S/A/D/SPACE disabled   T step   F step   "
                "M pedals   K steer   ESC quit"
            )
        hint_surface = self.small.render(hint, True, self.MUTED)
        surface.blit(
            hint_surface,
            (24, surface.get_height() - self.HINT_BOTTOM_MARGIN),
        )

    def draw(
        self,
        surface: pygame.Surface,
        car: Car,
        params: CarParameters,
        controls_help: bool = True,
        mode: str = "GAME",
        *,
        step_mode: bool = False,
        manual_controls=None,
    ) -> None:
        """Compose telemetry and controls overlays over the simulation view."""
        self._draw_telemetry_panel(surface, car, params, mode, step_mode)
        self._draw_help_overlay(
            surface,
            car,
            controls_help,
            step_mode,
            manual_controls,
        )