# Logi Options+ Agent Protocol - Reverse Engineering Notes

## Overview

The `logioptionsplus_agent` communicates with clients (GUI, CLI) via a Unix domain socket
using a custom framing protocol with JSON payloads.

**Status: Protocol fully working — GET, SET, SUBSCRIBE all verified.**

## Agent Process

The `logioptionsplus_agent` is an independent background daemon, **not** part of the GUI.
It runs as a LaunchAgent (`/Library/LaunchAgents/com.logi.optionsplus.plist`) with
`RunAtLoad=true` and `KeepAlive`, meaning it starts at boot and restarts on crash.

The GUI (`/Applications/logioptionsplus.app`) is just an Electron frontend that connects
to the same agent socket. You can use this CLI without ever opening the GUI.

## Socket Location

```
/tmp/logitech_kiros_agent-<hash>
```

The hash is deterministic per installation. Find it with:
```bash
ls /tmp/logitech_kiros_agent-*
```

## Wire Protocol (VERIFIED)

### Framing

Each message on the wire is:
```
[4 bytes LE total_size] [frame1] [frame2] ...
```

Where each frame is:
```
[4 bytes BE frame_length] [frame_data]
```

### Handshake (VERIFIED)

1. **Server sends**: LE-prefixed handshake containing two frames:
   - Frame 1: `"protobuf"` (the server's native protocol)
   - Frame 2: Protobuf-encoded `Message { verb=OPTIONS, path="/", origin="backend" }`

2. **Client responds** with a JSON type announcement (no OPTIONS needed):
   ```
   [LE total] [BE 4] "json"
   ```

3. After this, the client can send JSON requests.

### Request Format (VERIFIED)

```
[LE total] [BE 4 "json"] [BE N json_payload]
```

```json
{
  "msg_id": "1",
  "verb": "GET",
  "path": "/permissions",
  "payload": {}
}
```

### Response Format (VERIFIED)

Same framing. Note: request uses `msg_id`, response uses `msgId` (camelCase).

```json
{
  "msgId": "1",
  "verb": "GET",
  "path": "/permissions",
  "origin": "backend",
  "result": { "code": "SUCCESS", "what": "" },
  "payload": {
    "@type": "type.googleapis.com/logi.protocol.app_permissions.Permissions",
    ...
  }
}
```

### Verbs

| Verb | Description | Status |
|------|-------------|--------|
| GET | Read data | VERIFIED |
| SET | Write data | VERIFIED |
| SUBSCRIBE | Subscribe to broadcasts | VERIFIED |
| BROADCAST | Server push events | VERIFIED (observed) |
| REMOVE | Delete | Not tested |
| OPTIONS | Route discovery | Observed in handshake |
| UNSUBSCRIBE | Unsubscribe | Not tested |

### Result Codes

| Code | Meaning |
|------|---------|
| SUCCESS | OK |
| NO_SUCH_PATH | Path doesn't exist |
| INVALID_ARG | Bad argument or verb for this path |
| INVALID_DEVICE | Device not found |
| NOT_FOUND | Resource not found (e.g. profile ID) |
| NOT_READY | Service still loading |

## Initialization Sequence

Device-specific paths require prior SUBSCRIBE to event channels.
Without subscriptions, `/devices/list` returns empty or times out.

**Required subscriptions before querying devices:**
```
SUBSCRIBE /devices/state/changed
SUBSCRIBE /battery/state/changed
SUBSCRIBE /devices/options/device_arrival
SUBSCRIBE /devices/options/device_removal
```

## Device-Specific Paths (VERIFIED)

Device IDs are assigned by the agent (e.g. `dev00000000`). Discover via `GET /devices/list`.

| Path | Verb | Payload Type | Description |
|------|------|-------------|-------------|
| `/devices/list` | GET | `devices.Device.Info.List` | List all devices (ID, model, state, capabilities) |
| `/battery/{id}/state` | GET | `wireless.Battery` | Battery %, charging status, level |
| `/mouse/{id}/pointer_speed` | GET/SET | `mouse.PointerSpeed` | Pointer speed (0.0-1.0) |
| `/mouse/{id}/info` | GET | `mouse.Info` | DPI range (min/max/step), capabilities |
| `/smartshift/{id}/params` | GET/SET | `mouse.SmartShiftSettings` | SmartShift mode/sensitivity |
| `/scrollwheel/{id}/params` | GET/SET | `mouse.ScrollWheelSettings` | Scroll speed/direction |

### Payload Examples

**PointerSpeed** (GET/SET):
```json
{"active": {"value": 0.44, "highResolutionSensorActive": false, "dpiLevel": 1}}
```

**SmartShiftSettings** (GET/SET):
```json
{"isEnabled": true, "sensitivity": 82, "mode": "RATCHET", "isScrollForceEnabled": false, "scrollForce": 0}
```

**ScrollWheelSettings** (GET/SET):
```json
{"speed": 0.62, "dir": "STANDARD", "isSmooth": false}
```

**Battery** (GET):
```json
{"deviceId": "dev00000000", "percentage": 55, "charging": false, "level": "GOOD"}
```

## Profile & Button Remapping (VERIFIED)

### Get Profiles

`GET /v2/profiles` returns all profiles with assignments.

Profile discovery: the default profile has `applicationId` that does NOT contain `application_id`.
App-specific profiles have IDs like `application_id_apple_safari`.

### Get Button Assignments

`GET /v2/profiles/slice/preview` with payload:
```json
{
  "profileId": "<uuid>",
  "appId": "<uuid>",
  "deviceId": "dev00000000",
  "tags": ["UI_PAGE_BUTTONS"]
}
```

### Set Button Assignment (VERIFIED)

`SET /v2/assignment`

**Preset action:**
```json
{
  "profileId": "<uuid>",
  "assignment": {
    "cardId": "card_global_presets_osx_undo",
    "slotId": "mx-master-3s-2b034_c83",
    "tags": ["UI_PAGE_BUTTONS"],
    "card": {
      "id": "card_global_presets_osx_undo",
      "attribute": "MACRO_PLAYBACK",
      "readOnly": true,
      "macro": {
        "type": "KEYSTROKE",
        "actionName": "Cmd + Z",
        "keystroke": {"code": 29, "modifiers": [227], "virtualKeyId": "VK_Z"}
      },
      "tags": ["PRESET_TAG_KEY_OR_BUTTON"]
    }
  }
}
```

**Custom keystroke:**
```json
{
  "profileId": "<uuid>",
  "assignment": {
    "cardId": "custom_keystroke",
    "slotId": "mx-master-3s-2b034_c83",
    "tags": ["UI_PAGE_BUTTONS"],
    "card": {
      "id": "custom_keystroke",
      "attribute": "MACRO_PLAYBACK",
      "readOnly": false,
      "macro": {
        "type": "KEYSTROKE",
        "actionName": "Ctrl + Shift + A",
        "keystroke": {"code": 4, "modifiers": [224, 225]}
      }
    }
  }
}
```

### HID Modifier Codes

| Modifier | Code |
|----------|------|
| Left Ctrl | 224 |
| Left Shift | 225 |
| Left Alt/Option | 226 |
| Left Cmd | 227 |

### Button Slot IDs (MX Master 3S)

| Slot Suffix | Button |
|-------------|--------|
| c82 | Middle button |
| c83 | Back |
| c86 | Forward |
| c195 | Gesture button |
| c196 | Mode shift (scroll wheel) |

### Available Preset Actions (macOS)

Card IDs follow pattern `card_global_presets_osx_<action>`:

back, forward, undo, redo, copy, paste, cut, delete, search, screen_capture,
emoji, mission_control, launch_pad, smart_zoom, hide_show_desktop, close_tab,
do_not_disturb, lookup, switch_apps, dictation, language_switch, refresh, print,
home, end, page_up, page_down

## General API Paths (VERIFIED)

| Path | Payload Type | Description |
|------|-------------|-------------|
| `/permissions` | `app_permissions.Permissions` | App feature flags |
| `/configuration` | `application.Configuration` | App config (language, theme) |
| `/system/info` | `api.system_info` | OS info (Apple Silicon) |
| `/scarif/info` | `scarif.Info` | App version, OS, analytics |
| `/v2/profiles` | `profiles_v2.Profiles` | All profiles with assignments |
| `/options/devices/list` | `devices_support.OptionsDevices` | Supported device catalog |
| `/logioptions/info` | `logioptions.LogiOptionsInfo` | Legacy Options info |
| `/lps/endpoint/info` | `lps.Endpoint.Information` | Plugin service state |
| `/crash_reporting/status` | `crash_reporting.Status` | Crash reporting config |
| `/macos_security/bluetooth` | `PermissionState` | BT permission |
| `/accounts/is_authenticated` | `List` | Auth status |

## Extracted Protobuf Definitions

83 `.proto` files extracted from the agent binary using
[protodump](https://github.com/arkadiyt/protodump). Located in `extracted_protos/`.

Key files:
- `logi/common_protocol/message.proto` — Wire format (Message, Result, Verb enum)
- `logi/protocol/mouse.proto` — DPI, PointerSpeed, SmartShift, ScrollWheel, ThumbWheel
- `logi/protocol/devices.proto` — Device info, battery, capabilities, interfaces
- `logi/protocol/profiles_v2.proto` — Profile management, assignments
- `logi/protocol/lps.proto` — Plugin system (Actions SDK)

## MX Master 3S Device Info

| Field | Value |
|-------|-------|
| Model ID | `2b034` |
| Product ID | `0xB034` |
| Vendor ID | `0x046D` |
| Device Type | MOUSE |
| Connection | BLE |
| Slot Prefix | `mx-master-3s-2b034` |
| DPI Range | 200-8000, step 50 |
| SmartShift | Yes |
| Programmable Buttons | c82, c83, c86, c195, c196 |
| Easy Switch | 3 channels |

## Open Questions

1. **TCP port 59869** — Agent also listens on TCP. Different protocol, purpose unknown.
2. **DPI per-level table** — `dpiLevel` in pointer_speed controls active level. Relationship
   between speed value and actual DPI is linear within the device's range.
