#!/usr/bin/env python3
"""
logi - CLI tool for Logitech Options+ device management on macOS.

Communicates with the logioptionsplus_agent daemon via Unix socket.
No GUI needed.
"""

import argparse
import datetime
import json
import shutil
import signal
import subprocess
import sys

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # fallback
    except ImportError:
        tomllib = None

from agent import LogiAgent
from mappings import (
    ACTION_ALIASES, BUTTON_NAMES, BUTTON_SLOTS,
    get_action_name, get_button_name, parse_keystroke,
)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_status(args):
    agent = LogiAgent()
    mouse = agent.require_mouse(args.device)
    did = mouse["id"]

    print(f"  {mouse.get('displayName', '?')} ({mouse.get('extendedDisplayName', '')})")
    print(f"    State:      {mouse.get('state', '?')}")
    print(f"    Connection: {mouse.get('connectionType', '?')}")
    print(f"    Firmware:   {mouse.get('activeInterfaces', [{}])[0].get('firmwareVersion', '?')}")

    p = agent.get_ok(f"/battery/{did}/state")
    if p:
        charging = " (charging)" if p.get("charging") else ""
        print(f"    Battery:    {p.get('percentage', '?')}% [{p.get('level', '?')}]{charging}")

    p = agent.get_ok(f"/mouse/{did}/pointer_speed")
    if p:
        speed = p.get("active", {}).get("value", 0)
        info = agent.get_ok(f"/mouse/{did}/info")
        dpi_est = ""
        if info:
            rng = info.get("dpiInfo", {}).get("range", {})
            dpi_min, dpi_max = rng.get("min", 200), rng.get("max", 8000)
            dpi_est = f" (~{int(dpi_min + speed * (dpi_max - dpi_min))} DPI)"
        print(f"    Pointer:    speed={speed}{dpi_est}")

    p = agent.get_ok(f"/smartshift/{did}/params")
    if p:
        print(f"    SmartShift: mode={p.get('mode','?')} sensitivity={p.get('sensitivity','?')} enabled={p.get('isEnabled','?')}")

    p = agent.get_ok(f"/scrollwheel/{did}/params")
    if p:
        print(f"    Scroll:     speed={p.get('speed','?')} dir={p.get('dir','?')} smooth={p.get('isSmooth','?')}")

    # Thumb wheel (from profile assignment)
    profile = agent.get_default_profile()
    if profile:
        for a in agent.get_profile_assignments(profile["id"], did):
            card = a.get("card", {})
            ts = card.get("mouseThumbWheelSettings")
            if ts:
                print(f"    Thumb:      speed={ts.get('speed','?')} dir={ts.get('dir','?')} smooth={ts.get('isSmooth','?')}")
                break

    info = agent.get_ok(f"/mouse/{did}/info")
    if info:
        rng = info.get("dpiInfo", {}).get("range", {})
        if rng:
            print(f"    DPI Range:  {rng.get('min',0)}-{rng.get('max',0)} (step {rng.get('steps',0)})")

    agent.close()


def _set_via_profile(agent, mouse, slot_suffix, settings_key, modifier_fn):
    """Modify a settings assignment (scroll/pointer/thumb) through /v2/assignment."""
    profile = agent.require_profile()
    did = mouse["id"]
    slot_prefix = mouse.get("slotPrefix", "")
    target_slot = f"{slot_prefix}_{slot_suffix}"

    assignments = agent.get_profile_assignments(profile["id"], did)
    for a in assignments:
        if a.get("slotId") == target_slot:
            card = a.get("card", {})
            settings = card.get(settings_key, {})
            if not settings:
                return False
            modifier_fn(settings)
            card[settings_key] = settings
            return agent.set_ok("/v2/assignment", {
                "profileId": profile["id"],
                "assignment": {
                    "cardId": a.get("cardId", card.get("id", "")),
                    "slotId": target_slot,
                    "tags": a.get("tags", []),
                    "card": card,
                },
            })
    return False


def _set_scroll_via_profile(agent, mouse, param, value):
    """Set scroll wheel settings through profile assignment."""
    def modify(settings):
        if param == "scroll-speed":
            settings["speed"] = float(value)
        elif param == "scroll-direction":
            dirs = {"natural": "NATURAL", "standard": "STANDARD", "normal": "STANDARD"}
            if value.lower() not in dirs:
                print("Error: value must be natural or standard", file=sys.stderr)
                sys.exit(1)
            settings["dir"] = dirs[value.lower()]

    ok = _set_via_profile(agent, mouse, "mouse_scroll_wheel_settings",
                          "mouseScrollWheelSettings", modify)
    if ok:
        print(f"OK: {param} = {value}")
    return ok


def _set_thumb_via_profile(agent, mouse, param, value):
    """Set thumb wheel settings through profile assignment."""
    def modify(settings):
        if param == "thumb-speed":
            settings["speed"] = float(value)
        elif param == "thumb-direction":
            dirs = {"natural": "NATURAL", "standard": "STANDARD", "normal": "STANDARD"}
            if value.lower() not in dirs:
                print("Error: value must be natural or standard", file=sys.stderr); sys.exit(1)
            settings["dir"] = dirs[value.lower()]
        elif param == "thumb-smooth":
            if value.lower() in ("on", "true", "1"):
                settings["isSmooth"] = True
            elif value.lower() in ("off", "false", "0"):
                settings["isSmooth"] = False
            else:
                print("Error: value must be on or off", file=sys.stderr); sys.exit(1)

    ok = _set_via_profile(agent, mouse, "mouse_thumb_wheel_settings",
                          "mouseThumbWheelSettings", modify)
    if ok:
        print(f"OK: {param} = {value}")
    return ok


def cmd_set(args):
    agent = LogiAgent()
    mouse = agent.require_mouse(args.device)
    did = mouse["id"]
    param, value = args.param, args.value

    if param == "dpi":
        info = agent.get_ok(f"/mouse/{did}/info")
        if not info:
            print("Error: could not read DPI info", file=sys.stderr); sys.exit(1)
        rng = info.get("dpiInfo", {}).get("range", {})
        dpi_min, dpi_max, dpi_step = rng.get("min", 200), rng.get("max", 8000), rng.get("steps", 50)
        val = round(int(value) / dpi_step) * dpi_step
        if not (dpi_min <= val <= dpi_max):
            print(f"Error: DPI must be {dpi_min}-{dpi_max} (step {dpi_step})", file=sys.stderr); sys.exit(1)
        speed = (val - dpi_min) / (dpi_max - dpi_min)
        cur = agent.get_ok(f"/mouse/{did}/pointer_speed") or {}
        dpi_level = cur.get("active", {}).get("dpiLevel", 1)
        if agent.set_ok(f"/mouse/{did}/pointer_speed",
                        {"active": {"value": speed, "highResolutionSensorActive": False, "dpiLevel": dpi_level}}):
            print(f"OK: DPI ~ {val} (speed={speed:.3f})")

    elif param == "speed":
        val = float(value)
        if not (0.0 <= val <= 1.0):
            print("Error: speed must be 0.0-1.0", file=sys.stderr); sys.exit(1)
        if agent.set_ok(f"/mouse/{did}/pointer_speed",
                        {"active": {"value": val, "highResolutionSensorActive": False, "dpiLevel": 1}}):
            print(f"OK: speed = {val}")

    elif param == "smartshift":
        modes = {"on": ("RATCHET", True), "ratchet": ("RATCHET", True),
                 "free": ("FREESPIN", True), "freespin": ("FREESPIN", True),
                 "off": ("RATCHET", False)}
        if value.lower() not in modes:
            print("Error: value must be on/off/free", file=sys.stderr); sys.exit(1)
        mode, enabled = modes[value.lower()]
        cur = agent.get_ok(f"/smartshift/{did}/params")
        if not cur:
            print("Error: could not read SmartShift settings", file=sys.stderr); sys.exit(1)
        cur.pop("@type", None)
        cur["isEnabled"], cur["mode"] = enabled, mode
        if agent.set_ok(f"/smartshift/{did}/params", cur):
            print(f"OK: smartshift = {value}")

    elif param == "smartshift-sensitivity":
        val = int(value)
        if not (0 <= val <= 100):
            print("Error: sensitivity must be 0-100", file=sys.stderr); sys.exit(1)
        cur = agent.get_ok(f"/smartshift/{did}/params")
        if not cur:
            print("Error: could not read SmartShift settings", file=sys.stderr); sys.exit(1)
        cur.pop("@type", None)
        cur["sensitivity"] = val
        if agent.set_ok(f"/smartshift/{did}/params", cur):
            print(f"OK: smartshift-sensitivity = {val}")

    elif param in ("scroll-speed", "scroll-direction"):
        ok = _set_scroll_via_profile(agent, mouse, param, value)
        if not ok:
            print("Error: could not update scroll settings", file=sys.stderr); sys.exit(1)

    elif param in ("thumb-speed", "thumb-direction", "thumb-smooth"):
        ok = _set_thumb_via_profile(agent, mouse, param, value)
        if not ok:
            print("Error: could not update thumb wheel settings", file=sys.stderr); sys.exit(1)

    else:
        print(f"Unknown parameter: {param}", file=sys.stderr)
        print("Available: dpi, speed, smartshift, smartshift-sensitivity,", file=sys.stderr)
        print("  scroll-speed, scroll-direction, thumb-speed, thumb-direction, thumb-smooth", file=sys.stderr)
        sys.exit(1)

    agent.close()


def cmd_button(args):
    button = args.button.lower()
    action = args.action.lower()

    slot_suffix = BUTTON_SLOTS.get(button)
    if not slot_suffix:
        print(f"Unknown button: {button}", file=sys.stderr)
        print(f"Available: {', '.join(sorted(BUTTON_SLOTS))}", file=sys.stderr)
        sys.exit(1)

    # Resolve action
    custom_card = None
    card_id = ACTION_ALIASES.get(action)
    if not card_id:
        if action.startswith("card_"):
            card_id = action
        elif "+" in args.action:
            custom_card = parse_keystroke(args.action)
            if not custom_card:
                print(f"Invalid keystroke: {args.action}", file=sys.stderr)
                print("Format: Cmd+Z, Ctrl+Shift+A, etc.", file=sys.stderr)
                sys.exit(1)
            card_id = custom_card["id"]
        else:
            _print_action_help(action)
            sys.exit(1)

    agent = LogiAgent()
    mouse = agent.require_mouse(args.device)
    profile = agent.require_profile(args.profile)
    slot_id = f"{mouse.get('slotPrefix')}_{slot_suffix}"

    if custom_card:
        card = custom_card
    else:
        card = None
        for a in profile.get("assignments", []):
            if a.get("card", {}).get("id") == card_id:
                card = a.get("card")
                break
        if not card:
            card = {"id": card_id, "attribute": "MACRO_PLAYBACK", "readOnly": True}

    if agent.set_ok("/v2/assignment", {
        "profileId": profile["id"],
        "assignment": {"cardId": card_id, "slotId": slot_id, "tags": ["UI_PAGE_BUTTONS"], "card": card},
    }):
        print(f"OK: {BUTTON_NAMES.get(slot_suffix, button)} -> {action}")

    agent.close()


def _print_action_help(attempted):
    """Print helpful action suggestions, using fzf if available."""
    all_actions = sorted(ACTION_ALIASES.keys())

    if shutil.which("fzf") and sys.stdin.isatty():
        print(f"Unknown action: {attempted}. Select one:", file=sys.stderr)
        try:
            result = subprocess.run(
                ["fzf", "--height=15", "--prompt=Action> "],
                input="\n".join(all_actions),
                capture_output=True, text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                print(f"Hint: logi button <button> {result.stdout.strip()}", file=sys.stderr)
                return
        except Exception:
            pass

    print(f"Unknown action: {attempted}", file=sys.stderr)
    print(f"Available: {', '.join(all_actions)}", file=sys.stderr)
    print("Or use a keystroke combo: Cmd+Z, Ctrl+Shift+A, etc.", file=sys.stderr)


def cmd_buttons(args):
    agent = LogiAgent()
    mouse = agent.require_mouse(args.device)
    did = mouse["id"]
    slot_prefix = mouse.get("slotPrefix", "")
    profile = agent.require_profile(args.profile)

    assignments = agent.get_profile_assignments(profile["id"], did, ["UI_PAGE_BUTTONS"])
    print(f"  Button Assignments (Profile: {args.profile or 'Default'})")
    print()
    for a in assignments:
        slot_id = a.get("slotId", "")
        if slot_prefix not in slot_id:
            continue
        print(f"    {get_button_name(slot_id, slot_prefix):25s} -> {get_action_name(a)}")
    agent.close()


def cmd_profiles(args):
    agent = LogiAgent()
    for p in agent.get_profiles():
        app_id = p.get("applicationId", "")
        is_default = "application_id" not in app_id
        label = "Default" if is_default else app_id
        marker = " *" if p.get("activeForApplication") else ""
        n = len(p.get("assignments", []))
        print(f"  {label}{marker}: {p.get('id', '?')} ({n} assignments)")
    agent.close()


def cmd_info(args):
    agent = LogiAgent()

    p = agent.get_ok("/system/info")
    if p:
        print(f"  Apple Silicon: {p.get('isCpuAppleSilicon', '?')}")

    p = agent.get_ok("/scarif/info")
    if p:
        print(f"  App Version:  {p.get('appVersion', '?')}")
        print(f"  OS:           {p.get('osName', '?')} {p.get('osVersion', '?')}")
        print(f"  Mac Model:    {p.get('model', '?')}")

    p = agent.get_ok("/configuration")
    if p:
        print(f"  Language:     {p.get('language', {}).get('value', '?')}")
        print(f"  Theme:        {p.get('theme', {}).get('value', '?')}")

    agent.close()


def cmd_watch(args):
    agent = LogiAgent()
    for p in ["/devices/state/changed", "/battery/state/changed",
              "/devices/options/device_arrival", "/devices/options/device_removal",
              "/devices/easy_switch", "/mouse/global/swap", "/devices/fn_inversion/notify"]:
        agent._send("SUBSCRIBE", p)

    running = True
    signal.signal(signal.SIGINT, lambda *_: setattr(cmd_watch, '_stop', True))
    cmd_watch._stop = False

    print("Watching device events... (Ctrl+C to stop)\n")
    while not cmd_watch._stop:
        msg = agent.recv_message(timeout=1)
        if not msg:
            continue
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        path = msg.get("path", "?")
        payload = msg.get("payload", {})

        if "battery" in path:
            print(f"  [{ts}] Battery: {payload.get('percentage','?')}% {payload.get('level','')}")
        elif "device_arrival" in path or "device_removal" in path:
            event = "connected" if "arrival" in path else "disconnected"
            for d in payload.get("deviceInfos", [{}]):
                print(f"  [{ts}] Device {event}: {d.get('displayName', '?')}")
        elif "state/changed" in path:
            for d in payload.get("deviceInfos", []):
                print(f"  [{ts}] {d.get('displayName','?')}: state={d.get('state','?')}")
        else:
            ptype = payload.get("@type", "").split(".")[-1]
            print(f"  [{ts}] {msg.get('verb','?')} {path} ({ptype})")

    print("\nStopped.")
    agent.close()


def cmd_export(args):
    agent = LogiAgent()
    mouse = agent.require_mouse(args.device)
    did = mouse["id"]

    config = {"device": {
        "displayName": mouse.get("displayName"),
        "deviceModel": mouse.get("deviceModel"),
        "slotPrefix": mouse.get("slotPrefix"),
    }}

    for key, path in [("pointer_speed", f"/mouse/{did}/pointer_speed"),
                       ("smartshift", f"/smartshift/{did}/params"),
                       ("scroll_wheel", f"/scrollwheel/{did}/params")]:
        p = agent.get_ok(path)
        if p:
            p.pop("@type", None)
            config[key] = p

    profile = agent.get_default_profile()
    if profile:
        slot_prefix = mouse.get("slotPrefix", "")
        assignments = agent.get_profile_assignments(profile["id"], did, ["UI_PAGE_BUTTONS"])
        config["buttons"] = {}
        for a in assignments:
            sid = a.get("slotId", "")
            if slot_prefix not in sid:
                continue
            suffix = sid.replace(f"{slot_prefix}_", "")
            config["buttons"][BUTTON_NAMES.get(suffix, suffix)] = {
                "slotId": sid, "cardId": a.get("card", {}).get("id", ""), "card": a.get("card", {}),
            }

    output = json.dumps(config, indent=2)
    if args.file:
        with open(args.file, "w") as f:
            f.write(output)
        print(f"Exported to {args.file}")
    else:
        print(output)
    agent.close()


def cmd_import(args):
    with open(args.file) as f:
        config = json.load(f)

    agent = LogiAgent()
    mouse = agent.require_mouse(args.device)
    did = mouse["id"]
    applied = []

    for key, path in [("pointer_speed", f"/mouse/{did}/pointer_speed"),
                       ("smartshift", f"/smartshift/{did}/params")]:
        if key in config and agent.set_ok(path, config[key]):
            applied.append(key)

    # Scroll wheel: SET via profile assignment (direct path no longer supports SET)
    if "scroll_wheel" in config:
        def apply_scroll(settings):
            for k, v in config["scroll_wheel"].items():
                if k != "@type":
                    settings[k] = v
        if _set_via_profile(agent, mouse, "mouse_scroll_wheel_settings",
                            "mouseScrollWheelSettings", apply_scroll):
            applied.append("scroll_wheel")

    if "buttons" in config:
        profile = agent.get_default_profile()
        if profile:
            for btn_name, btn_data in config["buttons"].items():
                card = btn_data.get("card", {})
                if not card.get("id"):
                    continue
                if agent.set_ok("/v2/assignment", {
                    "profileId": profile["id"],
                    "assignment": {"cardId": card["id"], "slotId": btn_data["slotId"],
                                   "tags": ["UI_PAGE_BUTTONS"], "card": card},
                }):
                    applied.append(f"button:{btn_name}")

    print(f"Imported {len(applied)} settings: {', '.join(applied)}" if applied else "No settings applied.")
    agent.close()


def cmd_apply(args):
    """Apply settings from a TOML config file."""
    if tomllib is None:
        print("Error: TOML support requires Python 3.11+ or 'pip install tomli'", file=sys.stderr)
        sys.exit(1)

    with open(args.file, "rb") as f:
        config = tomllib.load(f)

    agent = LogiAgent()
    mouse = agent.require_mouse(args.device)
    _apply_config(agent, mouse, config)
    agent.close()


def cmd_daemon(args):
    """Watch for device connections and auto-apply config."""
    if tomllib is None:
        print("Error: TOML support requires Python 3.11+ or 'pip install tomli'", file=sys.stderr)
        sys.exit(1)

    config_file = args.config
    with open(config_file, "rb") as f:
        config = tomllib.load(f)

    agent = LogiAgent()
    for p in ["/devices/state/changed", "/devices/options/device_arrival"]:
        agent._send("SUBSCRIBE", p)

    signal.signal(signal.SIGINT, lambda *_: setattr(cmd_daemon, '_stop', True))
    cmd_daemon._stop = False

    print(f"Daemon: watching for device connections, will apply {config_file}")
    print(f"Press Ctrl+C to stop.\n")

    # Apply once on start if device is connected
    mouse = agent.find_mouse()
    if mouse:
        print(f"  Device already connected: {mouse.get('displayName')}")
        _apply_config(agent, mouse, config)

    while not cmd_daemon._stop:
        msg = agent.recv_message(timeout=2)
        if not msg:
            continue

        path = msg.get("path", "")
        if "device_arrival" in path or "state/changed" in path:
            payload = msg.get("payload", {})
            for d in payload.get("deviceInfos", []):
                if d.get("deviceType") == "MOUSE" and d.get("state") == "ACTIVE":
                    ts = datetime.datetime.now().strftime("%H:%M:%S")
                    print(f"  [{ts}] {d.get('displayName','?')} connected, applying config...")
                    # Re-fetch mouse to get full device info
                    mouse = agent.find_mouse()
                    if mouse:
                        _apply_config(agent, mouse, config)

    print("\nDaemon stopped.")
    agent.close()


def _apply_config(agent, mouse, config):
    """Apply a parsed TOML config dict to a mouse device."""
    did = mouse["id"]
    applied = []

    ptr = config.get("pointer", {})
    if "dpi" in ptr:
        info = agent.get_ok(f"/mouse/{did}/info")
        if info:
            rng = info.get("dpiInfo", {}).get("range", {})
            dpi_min, dpi_max, dpi_step = rng.get("min", 200), rng.get("max", 8000), rng.get("steps", 50)
            val = round(int(ptr["dpi"]) / dpi_step) * dpi_step
            speed = (val - dpi_min) / (dpi_max - dpi_min)
            cur = agent.get_ok(f"/mouse/{did}/pointer_speed") or {}
            dpi_level = cur.get("active", {}).get("dpiLevel", 1)
            if agent.set_ok(f"/mouse/{did}/pointer_speed",
                            {"active": {"value": speed, "highResolutionSensorActive": False, "dpiLevel": dpi_level}}):
                applied.append(f"dpi={val}")
    elif "speed" in ptr:
        if agent.set_ok(f"/mouse/{did}/pointer_speed",
                        {"active": {"value": float(ptr["speed"]), "highResolutionSensorActive": False, "dpiLevel": 1}}):
            applied.append(f"speed={ptr['speed']}")

    ss = config.get("smartshift", {})
    if ss:
        cur = agent.get_ok(f"/smartshift/{did}/params")
        if cur:
            cur.pop("@type", None)
            modes = {"ratchet": ("RATCHET", True), "on": ("RATCHET", True),
                     "freespin": ("FREESPIN", True), "free": ("FREESPIN", True),
                     "off": ("RATCHET", False)}
            if "mode" in ss and ss["mode"].lower() in modes:
                mode, enabled = modes[ss["mode"].lower()]
                cur["mode"], cur["isEnabled"] = mode, enabled
            if "sensitivity" in ss:
                cur["sensitivity"] = int(ss["sensitivity"])
            if agent.set_ok(f"/smartshift/{did}/params", cur):
                applied.append("smartshift")

    scroll = config.get("scroll", {})
    if scroll:
        def mod_scroll(s):
            if "speed" in scroll: s["speed"] = float(scroll["speed"])
            if "direction" in scroll: s["dir"] = "NATURAL" if scroll["direction"].lower() == "natural" else "STANDARD"
        if _set_via_profile(agent, mouse, "mouse_scroll_wheel_settings", "mouseScrollWheelSettings", mod_scroll):
            applied.append("scroll")

    thumb = config.get("thumb", {})
    if thumb:
        def mod_thumb(s):
            if "speed" in thumb: s["speed"] = float(thumb["speed"])
            if "direction" in thumb: s["dir"] = "NATURAL" if thumb["direction"].lower() == "natural" else "STANDARD"
            if "smooth" in thumb: s["isSmooth"] = bool(thumb["smooth"])
        if _set_via_profile(agent, mouse, "mouse_thumb_wheel_settings", "mouseThumbWheelSettings", mod_thumb):
            applied.append("thumb")

    buttons = config.get("buttons", {})
    if buttons:
        profile = agent.require_profile()
        slot_prefix = mouse.get("slotPrefix", "")
        for btn_name, action_str in buttons.items():
            slot_suffix = BUTTON_SLOTS.get(btn_name.lower())
            if not slot_suffix: continue
            card_id = ACTION_ALIASES.get(action_str.lower())
            custom_card = None
            if not card_id and "+" in action_str:
                custom_card = parse_keystroke(action_str)
                if custom_card: card_id = custom_card["id"]
            if not card_id: continue
            card = custom_card
            if not card:
                for a in profile.get("assignments", []):
                    if a.get("card", {}).get("id") == card_id:
                        card = a["card"]; break
            if not card:
                card = {"id": card_id, "attribute": "MACRO_PLAYBACK", "readOnly": True}
            if agent.set_ok("/v2/assignment", {
                "profileId": profile["id"],
                "assignment": {"cardId": card_id, "slotId": f"{slot_prefix}_{slot_suffix}",
                               "tags": ["UI_PAGE_BUTTONS"], "card": card},
            }):
                applied.append(f"button:{btn_name}")

    if applied:
        print(f"    Applied: {', '.join(applied)}")


def cmd_raw(args):
    agent = LogiAgent()
    payload = json.loads(args.payload) if args.payload else None
    r = agent.call(args.verb.upper(), args.path, payload)
    print(json.dumps(r, indent=2) if r else "No response (timeout)")
    agent.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(prog="logi", description="CLI for Logitech Options+ device management")
    parser.add_argument("--device", "-d", help="Device name or ID (for multi-device setups)")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="Show live device status")
    sub.add_parser("watch", help="Watch real-time device events")
    sub.add_parser("info", help="Show agent and system info")

    p = sub.add_parser("set", help="Set a device parameter")
    p.add_argument("param", help="dpi, speed, smartshift, smartshift-sensitivity, scroll-speed, scroll-direction")
    p.add_argument("value")

    p = sub.add_parser("button", help="Remap a mouse button")
    p.add_argument("button", help="middle, back, forward, gesture")
    p.add_argument("action", help="Preset action, card ID, or keystroke combo (Cmd+Z)")
    p.add_argument("--profile", help="App profile (e.g. safari, zoom)")

    p = sub.add_parser("buttons", help="Show button assignments")
    p.add_argument("--profile", help="App profile (e.g. safari, zoom)")

    sub.add_parser("profiles", help="List all profiles")

    p = sub.add_parser("export", help="Export config to JSON")
    p.add_argument("file", nargs="?", help="Output file (default: stdout)")

    p = sub.add_parser("import", help="Import config from JSON")
    p.add_argument("file", help="JSON config file")

    p = sub.add_parser("apply", help="Apply settings from TOML config file")
    p.add_argument("file", help="TOML config file (see example.toml)")

    p = sub.add_parser("daemon", help="Watch for device connections and auto-apply config")
    p.add_argument("config", help="TOML config file to apply on connect")

    p = sub.add_parser("raw", help="Send raw request to agent")
    p.add_argument("verb", help="GET, SET, SUBSCRIBE")
    p.add_argument("path")
    p.add_argument("--payload", help="JSON payload")

    args = parser.parse_args()

    commands = {
        "status": cmd_status, "watch": cmd_watch, "info": cmd_info,
        "set": cmd_set, "button": cmd_button, "buttons": cmd_buttons,
        "profiles": cmd_profiles, "export": cmd_export, "import": cmd_import,
        "apply": cmd_apply, "daemon": cmd_daemon, "raw": cmd_raw,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
