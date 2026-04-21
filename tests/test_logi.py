"""Tests for logi.py — CLI logic that doesn't need agent connection."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from logi import GESTURE_MODES, DEFAULT_CONFIG_PATH


class TestGestureModes:
    def test_all_modes_have_ids(self):
        for name, mode_id in GESTURE_MODES.items():
            assert isinstance(mode_id, str)
            assert "_" in mode_id or mode_id == "pan"

    def test_short_aliases(self):
        assert GESTURE_MODES["window"] == "window_navigation"
        assert GESTURE_MODES["media"] == "media_control"
        assert GESTURE_MODES["zoom"] == "zoom_rotate"
        assert GESTURE_MODES["app"] == "application_navigation"
        assert GESTURE_MODES["pan"] == "pan"
        assert GESTURE_MODES["custom"] == "custom_gesture"

    def test_long_names(self):
        assert "window-navigation" in GESTURE_MODES
        assert "media-control" in GESTURE_MODES
        assert "zoom-rotate" in GESTURE_MODES
        assert "app-navigation" in GESTURE_MODES


class TestDefaultConfig:
    def test_path_in_home(self):
        assert ".config/logi-cli" in DEFAULT_CONFIG_PATH
        assert DEFAULT_CONFIG_PATH.endswith(".toml")


class TestCLIHelp:
    """Verify argparse setup by importing main."""
    def test_main_exists(self):
        from logi import main
        assert callable(main)

    def test_all_commands_registered(self):
        from logi import main
        import argparse
        # Just verify it doesn't crash on --help
        # (actual help output tested via subprocess in integration tests)
        expected = ["status", "watch", "info", "set", "button", "buttons",
                    "profiles", "gesture", "switch", "flow", "permissions",
                    "reset", "export", "import", "init", "apply", "daemon", "raw"]
        # All commands should be in the source
        import logi as logi_module
        source = open(logi_module.__file__).read()
        for cmd in expected:
            assert f'"{cmd}"' in source, f"Command {cmd} not found in logi.py"
