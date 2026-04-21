# logi-cli

CLI tool for Logitech Options+ device management on macOS.

Communicates directly with the `logioptionsplus_agent` daemon via its Unix socket IPC protocol. No GUI needed — the agent runs independently as a system LaunchAgent.

## Requirements

- macOS with Logi Options+ installed (the agent must be running)
- Python 3.9+
- Tested with MX Master 3S

## Install

```bash
pip install -e .
```

Or just run directly:

```bash
python3 logi.py status
```

### Shell completion

```bash
# zsh
source completions/logi.zsh

# bash
source completions/logi.bash
```

## Usage

### Device status

```bash
logi status
```
```
MX Master 3S (Wireless Mouse MX Master 3S)
  State:      ACTIVE
  Connection: BLE
  Firmware:   22.0.3
  Battery:    55% [GOOD]
  Pointer:    speed=0.44 (~3632 DPI)
  SmartShift: mode=RATCHET sensitivity=82 enabled=True
  Scroll:     speed=0.62 dir=STANDARD smooth=False
  DPI Range:  200-8000 (step 50)
```

### Configure settings

```bash
logi set dpi 1600                    # Set DPI
logi set speed 0.5                   # Pointer speed (0.0-1.0)
logi set smartshift free             # SmartShift: on/off/free
logi set smartshift-sensitivity 50   # SmartShift sensitivity (0-100)
logi set scroll-speed 0.8            # Scroll wheel speed
logi set scroll-direction natural    # Scroll direction: natural/standard
```

### Button remapping

```bash
logi buttons                         # Show current assignments
logi button back undo                # Remap to preset action
logi button back "Cmd+Z"             # Remap to custom keystroke
logi button back "Ctrl+Shift+A"      # Any modifier combo
logi button back back                # Restore default
```

Available buttons: `middle`, `back`, `forward`, `gesture`

Available actions: `back`, `forward`, `undo`, `redo`, `copy`, `paste`, `cut`, `screenshot`, `emoji`, `search`, `desktop`, `mission-control`, `launchpad`, `smart-zoom`, `close-tab`, `do-not-disturb`, `lookup`, `switch-apps`, `dictation`

### Per-app profiles

```bash
logi buttons --profile safari        # View Safari-specific buttons
logi button back undo --profile zoom # Set button for Zoom only
logi profiles                        # List all profiles
```

### Config backup/restore

```bash
logi export config.json              # Export all settings
logi import config.json              # Restore settings
```

### Thumb wheel

```bash
logi set thumb-direction natural     # Thumb wheel direction
logi set thumb-smooth off            # Thumb wheel smooth scrolling
```

### Declarative config

```bash
logi apply config.toml               # Apply all settings from TOML file
logi daemon config.toml              # Auto-apply on device connect
```

See [example.toml](example.toml) for the config format.

### Real-time monitoring

```bash
logi watch                           # Watch device events (Ctrl+C to stop)
```

### Multi-device

```bash
logi -d mx status                    # Select device by name
logi -d dev00000000 set dpi 1600     # Select device by ID
```

### System info

```bash
logi info                            # Agent version, OS, etc.
```

### Raw API access

```bash
logi raw GET /permissions
logi raw GET /battery/dev00000000/state
logi raw SET /mouse/dev00000000/pointer_speed --payload '{"active":{"value":0.5}}'
```

## Disclaimer

This is an unofficial, community-developed tool. It is not affiliated with, endorsed by, or associated with Logitech in any way. "Logitech", "Logi Options+", and "MX Master" are trademarks of Logitech International S.A. Use at your own risk.

## Acknowledgements

- [logiops](https://github.com/PixlOne/logiops) — Unofficial Logitech HID++ driver for Linux. Inspired the idea of a CLI-first approach to Logitech device management. logiops communicates directly via HID++ protocol; logi-cli takes a different approach by talking to the Options+ agent via its IPC socket.

## Protocol

See [PROTOCOL.md](PROTOCOL.md) for the reverse-engineered IPC protocol documentation.

83 extracted protobuf definitions are in `extracted_protos/`.

## Architecture

```
┌──────────┐     Unix Socket (JSON)     ┌──────────────────────┐
│ logi CLI ├────────────────────────────►│ logioptionsplus_agent│
└──────────┘  /tmp/logitech_kiros_agent  │  (system daemon)     │
                                         │  RunAtLoad, KeepAlive│
                                         └──────────┬───────────┘
                                                     │ HID++ / BLE
                                                     ▼
                                              ┌──────────────┐
                                              │ MX Master 3S │
                                              └──────────────┘
```
