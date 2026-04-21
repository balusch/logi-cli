"""Tests for mappings.py — button names, action aliases, keystroke parsing."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from mappings import (
    BUTTON_NAMES, BUTTON_SLOTS, ACTION_ALIASES, CARD_NAMES,
    HID_KEYS, HID_MODIFIERS,
    parse_keystroke, get_button_name, get_action_name,
)


class TestButtonMappings:
    def test_button_slots_have_names(self):
        for name, suffix in BUTTON_SLOTS.items():
            assert suffix in BUTTON_NAMES, f"BUTTON_SLOTS[{name}]={suffix} not in BUTTON_NAMES"

    def test_get_button_name_known(self):
        assert get_button_name("mx-master-3s-2b034_c83", "mx-master-3s-2b034") == "Back"
        assert get_button_name("mx-master-3s-2b034_c82", "mx-master-3s-2b034") == "Middle Button"

    def test_get_button_name_unknown(self):
        assert get_button_name("prefix_c999", "prefix") == "c999"


class TestActionAliases:
    def test_aliases_are_valid_card_ids(self):
        for alias, card_id in ACTION_ALIASES.items():
            assert card_id.startswith("card_global_presets_"), f"{alias} -> {card_id}"

    def test_common_aliases_exist(self):
        for name in ["back", "forward", "undo", "redo", "copy", "paste", "cut", "screenshot"]:
            assert name in ACTION_ALIASES


class TestKeystrokeParsing:
    def test_simple_key(self):
        card = parse_keystroke("z")
        assert card is not None
        assert card["macro"]["keystroke"]["code"] == HID_KEYS["z"]
        assert card["macro"]["keystroke"]["modifiers"] == []

    def test_cmd_z(self):
        card = parse_keystroke("Cmd+Z")
        assert card is not None
        ks = card["macro"]["keystroke"]
        assert ks["code"] == HID_KEYS["z"]
        assert ks["modifiers"] == [HID_MODIFIERS["cmd"]]
        assert card["macro"]["actionName"] == "Cmd + Z"

    def test_ctrl_shift_a(self):
        card = parse_keystroke("Ctrl+Shift+A")
        assert card is not None
        ks = card["macro"]["keystroke"]
        assert ks["code"] == HID_KEYS["a"]
        assert HID_MODIFIERS["ctrl"] in ks["modifiers"]
        assert HID_MODIFIERS["shift"] in ks["modifiers"]

    def test_cmd_option_f5(self):
        card = parse_keystroke("Cmd+Option+F5")
        assert card is not None
        ks = card["macro"]["keystroke"]
        assert ks["code"] == HID_KEYS["f5"]
        assert HID_MODIFIERS["cmd"] in ks["modifiers"]
        assert HID_MODIFIERS["option"] in ks["modifiers"]

    def test_invalid_key(self):
        assert parse_keystroke("Cmd+INVALID") is None

    def test_invalid_modifier(self):
        assert parse_keystroke("Meta+Z") is None

    def test_empty(self):
        assert parse_keystroke("") is None


class TestGetActionName:
    def test_known_card(self):
        assignment = {"card": {"id": "card_global_presets_osx_back", "name": "ASSIGNMENT_NAME_BACK"}}
        assert get_action_name(assignment) == "Back"

    def test_unknown_card_strips_prefix(self):
        assignment = {"card": {"id": "card_global_presets_osx_something_new"}}
        assert get_action_name(assignment) == "Osx Something New"

    def test_mouse_settings(self):
        assignment = {"card": {
            "attribute": "MOUSE_SETTINGS",
            "mouseSettings": {"pointerSpeed": {"active": {"value": 0.5, "dpiLevel": 1}}}
        }}
        result = get_action_name(assignment)
        assert "0.5" in result

    def test_scroll_settings(self):
        assignment = {"card": {
            "attribute": "MOUSE_SCROLL_WHEEL_SETTINGS",
            "mouseScrollWheelSettings": {
                "speed": 0.62,
                "smartshift": {"mode": "RATCHET", "sensitivity": 82}
            }
        }}
        result = get_action_name(assignment)
        assert "RATCHET" in result

    def test_empty_card(self):
        assert get_action_name({}) == "Unknown"
