"""Tests for colors.py — terminal color helpers."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from colors import red, green, yellow, bold, dim, battery_color, state_color


class TestColorFunctions:
    def test_red_contains_text(self):
        assert "hello" in red("hello")

    def test_green_contains_text(self):
        assert "world" in green("world")

    def test_bold_contains_text(self):
        assert "test" in bold("test")


class TestBatteryColor:
    def test_critical(self):
        result = battery_color(5, "CRITICAL")
        assert "5%" in result

    def test_low(self):
        result = battery_color(20, "LOW")
        assert "20%" in result

    def test_good(self):
        result = battery_color(80, "GOOD")
        assert "80%" in result

    def test_low_by_percentage(self):
        result = battery_color(10)
        assert "10%" in result

    def test_full_by_percentage(self):
        result = battery_color(100)
        assert "100%" in result


class TestStateColor:
    def test_active(self):
        result = state_color("ACTIVE")
        assert "ACTIVE" in result

    def test_inactive(self):
        result = state_color("INACTIVE")
        assert "INACTIVE" in result

    def test_unknown(self):
        result = state_color("LOADING")
        assert "LOADING" in result
