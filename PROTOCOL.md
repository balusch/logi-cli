# Logi Options+ Agent Protocol - Reverse Engineering Notes

## Overview

The `logioptionsplus_agent` communicates with clients (GUI, CLI) via a Unix domain socket
using a custom framing protocol with JSON payloads.

**Status: Protocol fully working for read operations.**

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

Other sockets exist (`/tmp/<uuid>`) but they appear to be outbound connections from the agent, not client endpoints.

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

2. **Client responds** with: a JSON type announcement (no OPTIONS message needed):
   ```
   [LE total] [BE 4] "json" 
   ```

3. After this, the client can send JSON requests.

### Request Format (VERIFIED)

Each request is:
```
[LE total] [BE 4 "json"] [BE N json_payload]
```

JSON payload:
```json
{
  "msg_id": "1",
  "verb": "GET",
  "path": "/permissions",
  "payload": {}  // optional
}
```

### Response Format (VERIFIED)

Same framing. JSON payload:
```json
{
  "msgId": "1",
  "verb": "GET",
  "path": "/permissions",
  "origin": "backend",
  "result": {
    "code": "SUCCESS",
    "what": ""
  },
  "payload": {
    "@type": "type.googleapis.com/logi.protocol.app_permissions.Permissions",
    ...
  }
}
```

Note: Request uses `msg_id`, response uses `msgId` (camelCase).

### Verbs

| Verb | Description | Status |
|------|-------------|--------|
| GET | Read data | VERIFIED |
| SET | Write data | Not tested |
| SUBSCRIBE | Subscribe to broadcasts | Partially tested |
| BROADCAST | Server push events | Observed in traffic |
| REMOVE | Delete | Not tested |
| OPTIONS | Route discovery | Observed in handshake |
| UNSUBSCRIBE | Unsubscribe | Not tested |

### Result Codes

| Code | Meaning |
|------|---------|
| SUCCESS | OK |
| NO_SUCH_PATH | Path doesn't exist |
| INVALID_ARG | Bad argument or verb |
| INVALID_DEVICE | Device not found |
| NOT_READY | Service still loading |

## API Paths

### Verified Working (GET)

| Path | Payload Type | Description |
|------|-------------|-------------|
| `/permissions` | `app_permissions.Permissions` | App feature flags |
| `/configuration` | `application.Configuration` | App config (language, theme, etc.) |
| `/system/info` | `api.system_info` | OS info (Apple Silicon, etc.) |
| `/system/settings` | `SystemSettings` | System settings |
| `/scarif/info` | `scarif.Info` | Analytics info, app version |
| `/options/devices/list` | `devices_support.OptionsDevices` | Supported device catalog (empty) |
| `/logioptions/info` | `logioptions.LogiOptionsInfo` | Legacy Logi Options info |
| `/lps/endpoint/info` | `lps.Endpoint.Information` | LPS plugin service state |
| `/crash_reporting/status` | `crash_reporting.Status` | Crash reporting config |
| `/macos_security/bluetooth` | `PermissionState` | Bluetooth permission |
| `/star_rating/notification_pending` | `BoolValue` | Rating notification |
| `/device_recommendation_enabled` | `BoolValue` | Device recommendations |
| `/updates/status` | N/A | Update status |
| `/accounts/is_authenticated` | `List` | Auth status |
| `/macros/ai_prompt_builder/enabled` | `AiPromptBuilder` | AI feature flag |

### Observed in GUI Traffic (Not Yet Working via CLI)

| Path | Verb | Notes |
|------|------|-------|
| `/devices/list` | GET/SUBSCRIBE | Device list - returns empty or times out |
| `/devices/state/changed` | SUBSCRIBE | Device state changes |
| `/battery/state/changed` | SUBSCRIBE | Battery updates |
| `/unified_profiles/activities` | GET | Profile activities |
| `/mouse/global/swap` | GET | Mouse button swap |
| `/applications/all` | GET | Application list |
| `/lps/service_state` | GET | Full service state |

### GUI Subscription Paths

These are subscribed to by the GUI on startup:
- `/devices/state/changed`
- `/devices/options/device_arrival`
- `/devices/options/device_removal`
- `/devices/devio/device_removal`
- `/battery/state/changed`
- `/offer/revoke`, `/offer/retrieve`
- `/v2/profiles/device/assignment_sync_complete`
- `/star_rating/trigger`
- `/configuration`
- Various macros and LPS paths

### Device-Specific Paths (from binary strings)

Format: `/path/%s/action` where `%s` is a device ID.

- `/devices/%s/info` - Device info
- `/devices/%s/list` - Device list  
- `/battery/%s/state` - Battery state
- `/mouse/%s/info` - Mouse info
- `/mouse/%s/pointer_speed` - Pointer speed
- `/mouse/%s/dpi_shift` - DPI shift
- `/smartshift/%s/params` - SmartShift settings
- `/scrollwheel/%s/params` - Scroll wheel settings
- `/mouse_settings/configure` - Configure mouse settings
- `/mouse_scroll_wheel_settings/configure` - Configure scroll
- `/mouse_thumb_wheel_settings/configure` - Configure thumb wheel

## Device Info

### From settings.db

The device configuration is stored in `~/Library/Application Support/LogiOptionsPlus/settings.db`
as a JSON blob in the `data` table.

Key structure:
- `ever_connected_devices.devices[]` - List of known devices
- `battery/<slot_prefix>/warning_notification` - Battery info
- `easy_switch.devices[]` - Easy Switch channel info
- `profile-<uuid>` - Button assignment profiles
- `profile-application_id_*` - Per-app profiles

### MX Master 3S Device Info

- **Model ID**: `2b034`
- **Product ID**: `0xB034`
- **Vendor ID**: `0x046D`
- **Device Type**: `MOUSE`
- **Connection**: BLE
- **Firmware**: `RBM22.00_0003`
- **Agent Device ID**: `dev00000005` / `dev00000017`
- **Slot Prefix**: `mx-master-3s-2b034`

### Button IDs (MX Master 3S)

| Slot Suffix | Button |
|-------------|--------|
| c82 | Middle button |
| c83 | Back |
| c86 | Forward |
| c195 | Gesture button |
| c196 | Mode shift (scroll wheel) |

## Extracted Protobuf Definitions

83 `.proto` files extracted from the agent binary using `protodump`.
Located in `extracted_protos/`.

Key files:
- `logi/common_protocol/message.proto` - Wire format wrapper
- `logi/protocol/mouse.proto` - Mouse settings (DPI, SmartShift, scroll, etc.)
- `logi/protocol/devices.proto` - Device info, capabilities, battery
- `logi/protocol/lps.proto` - Plugin system
- `logi/protocol/profiles_v2.proto` - Profile management

## Device-Specific Paths (VERIFIED)

After subscribing to required channels, device-specific paths work with device IDs
like `dev00000000`:

| Path | Verb | Payload Type | Description |
|------|------|-------------|-------------|
| `/devices/list` | GET | `devices.Device.Info.List` | List all devices |
| `/battery/{id}/state` | GET | `wireless.Battery` | Battery %, charging, level |
| `/mouse/{id}/pointer_speed` | GET/SET | `mouse.PointerSpeed` | Pointer speed |
| `/mouse/{id}/info` | GET | `mouse.Info` | DPI range, capabilities |
| `/smartshift/{id}/params` | GET/SET | `mouse.SmartShiftSettings` | SmartShift mode/sensitivity |
| `/scrollwheel/{id}/params` | GET/SET | `mouse.ScrollWheelSettings` | Scroll speed/direction |

**Important**: Device-specific paths require prior SUBSCRIBE to `/devices/state/changed` etc.
Without subscriptions, `/devices/list` returns empty or times out.

## Button Remapping (VERIFIED)

Path: `SET /v2/assignment`

Payload format:
```json
{
  "profileId": "<profile-uuid>",
  "assignment": {
    "card": { "id": "card_global_presets_osx_back", "attribute": "MACRO_PLAYBACK", "readOnly": true, ... },
    "cardId": "card_global_presets_osx_back",
    "slotId": "mx-master-3s-2b034_c83",
    "tags": ["UI_PAGE_BUTTONS"]
  }
}
```

The profile ID can be discovered from settings.db `profile_keys` array.
Card templates (with macro definitions) are found in existing profile assignments.

### Available Actions (macOS)

back, forward, middle-click, mission-control, launchpad, smart-zoom, undo, redo,
copy, paste, cut, screenshot, emoji, search, desktop, close-tab, do-not-disturb,
lookup, switch-apps, dictation, and more.

Full card IDs follow pattern: `card_global_presets_osx_<action>`

## Open Questions

1. **TCP port 59869** - The agent also listens on TCP but doesn't respond to the
   same protocol. May use a different protocol or be for a different purpose.

2. **Custom keystroke mapping** - Arbitrary key combos (not just presets) likely
   require a custom card with `macro.keystroke` definition including HID codes.
