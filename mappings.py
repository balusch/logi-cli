"""
Button/action name mappings and HID keystroke utilities.
"""

# Button slot suffix -> friendly name (MX Master 3S)
BUTTON_NAMES = {
    "c82": "Middle Button",
    "c83": "Back",
    "c86": "Forward",
    "c195": "Gesture Button",
    "c196": "Mode Shift (Scroll)",
    "mouse_settings": "Pointer Settings",
    "mouse_scroll_wheel_settings": "Scroll Wheel",
    "mouse_thumb_wheel_settings": "Thumb Wheel",
    "thumb_wheel_adapter": "Thumb Wheel Adapter",
}

# Reverse: friendly name -> slot suffix
BUTTON_SLOTS = {"middle": "c82", "back": "c83", "forward": "c86", "gesture": "c195"}

# Card ID -> friendly display name
CARD_NAMES = {
    "card_global_presets_gesture_button_highlights": "Gesture (Highlights)",
    "card_global_presets_middle_button": "Middle Click",
    "card_global_presets_osx_back": "Back",
    "card_global_presets_osx_forward": "Forward",
    "card_global_presets_osx_mission_control": "Mission Control",
    "card_global_presets_osx_smart_zoom": "Smart Zoom",
    "card_global_presets_osx_launch_pad": "Launchpad",
    "card_global_presets_mode_shift": "Mode Shift",
    "card_global_presets_one_of_gesture_button": "Gesture Button",
    "card_global_presets_osx_horizontal_scroll": "Horizontal Scroll",
}

# Shorthand action name -> card ID
ACTION_ALIASES = {
    "back": "card_global_presets_osx_back",
    "forward": "card_global_presets_osx_forward",
    "middle": "card_global_presets_middle_button",
    "mission-control": "card_global_presets_osx_mission_control",
    "launchpad": "card_global_presets_osx_launch_pad",
    "smart-zoom": "card_global_presets_osx_smart_zoom",
    "undo": "card_global_presets_osx_undo",
    "redo": "card_global_presets_osx_redo",
    "copy": "card_global_presets_osx_copy",
    "paste": "card_global_presets_osx_paste",
    "cut": "card_global_presets_osx_cut",
    "screenshot": "card_global_presets_osx_screen_capture",
    "emoji": "card_global_presets_osx_emoji",
    "search": "card_global_presets_osx_search",
    "desktop": "card_global_presets_osx_hide_show_desktop",
    "close-tab": "card_global_presets_osx_close_tab",
    "do-not-disturb": "card_global_presets_osx_do_not_disturb",
    "lookup": "card_global_presets_osx_lookup",
    "switch-apps": "card_global_presets_osx_switch_apps",
    "dictation": "card_global_presets_osx_dictation",
    "gesture": "card_global_presets_one_of_gesture_button",
    "mode-shift": "card_global_presets_mode_shift",
}

# HID keyboard usage codes
HID_KEYS = {
    "a": 4, "b": 5, "c": 6, "d": 7, "e": 8, "f": 9, "g": 10, "h": 11,
    "i": 12, "j": 13, "k": 14, "l": 15, "m": 16, "n": 17, "o": 18, "p": 19,
    "q": 20, "r": 21, "s": 22, "t": 23, "u": 24, "v": 25, "w": 26, "x": 27,
    "y": 28, "z": 29,
    "1": 30, "2": 31, "3": 32, "4": 33, "5": 34,
    "6": 35, "7": 36, "8": 37, "9": 38, "0": 39,
    "enter": 40, "esc": 41, "backspace": 42, "tab": 43, "space": 44,
    "-": 45, "=": 46, "[": 47, "]": 48, "\\": 49,
    ";": 51, "'": 52, "`": 53, ",": 54, ".": 55, "/": 56,
    "f1": 58, "f2": 59, "f3": 60, "f4": 61, "f5": 62, "f6": 63,
    "f7": 64, "f8": 65, "f9": 66, "f10": 67, "f11": 68, "f12": 69,
    "delete": 76, "right": 79, "left": 80, "down": 81, "up": 82,
}

# HID modifier codes (Left variants)
HID_MODIFIERS = {
    "ctrl": 224, "shift": 225, "alt": 226, "opt": 226, "option": 226,
    "cmd": 227, "command": 227,
}


def parse_keystroke(combo):
    """Parse 'Cmd+Shift+Z' into a card dict for button assignment. Returns None on failure."""
    parts = [p.strip().lower() for p in combo.split("+")]
    if not parts:
        return None

    key_part = parts[-1]
    mod_parts = parts[:-1]

    key_code = HID_KEYS.get(key_part)
    if key_code is None:
        return None

    modifiers = []
    mod_names = []
    for m in mod_parts:
        mod_code = HID_MODIFIERS.get(m)
        if mod_code is None:
            return None
        modifiers.append(mod_code)
        mod_names.append(m.capitalize())

    action_name = " + ".join(mod_names + [key_part.upper()])

    return {
        "id": f"custom_keystroke_{combo.replace('+', '_').lower()}",
        "name": action_name,
        "attribute": "MACRO_PLAYBACK",
        "readOnly": False,
        "macro": {
            "type": "KEYSTROKE",
            "actionName": action_name,
            "keystroke": {"code": key_code, "modifiers": modifiers, "virtualKeyId": ""},
        },
        "tags": ["PRESET_TAG_KEY_OR_BUTTON"],
    }


def get_button_name(slot_id, slot_prefix):
    suffix = slot_id.replace(f"{slot_prefix}_", "")
    return BUTTON_NAMES.get(suffix, suffix)


def get_action_name(assignment):
    card_data = assignment.get("card", {})
    card_id = card_data.get("id", assignment.get("cardId", ""))
    card_name = card_data.get("name", "")

    if card_id in CARD_NAMES:
        return CARD_NAMES[card_id]

    if card_id.startswith("card_global_presets_"):
        return card_id.replace("card_global_presets_", "").replace("_", " ").title()

    attr = card_data.get("attribute", "")
    if attr == "MOUSE_SCROLL_WHEEL_SETTINGS":
        s = card_data.get("mouseScrollWheelSettings", {})
        ss = s.get("smartshift", {})
        return f"SmartShift={ss.get('mode','?')} sens={ss.get('sensitivity','?')} speed={s.get('speed','?')}"

    if attr == "MOUSE_SETTINGS":
        ps = card_data.get("mouseSettings", {}).get("pointerSpeed", {}).get("active", {})
        return f"PointerSpeed={ps.get('value','?')} dpi_level={ps.get('dpiLevel','?')}"

    if attr == "MOUSE_THUMB_WHEEL_SETTINGS":
        ts = card_data.get("mouseThumbWheelSettings", {})
        return f"dir={ts.get('dir','?')} smooth={ts.get('isSmooth','?')}"

    if card_name:
        return card_name.replace("ASSIGNMENT_NAME_", "").replace("_", " ").title()

    return card_id or "Unknown"
