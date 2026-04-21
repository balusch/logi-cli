"""
Logi Options+ agent IPC client.

Communicates with logioptionsplus_agent via Unix domain socket
using JSON-over-custom-framing protocol.
"""

import glob
import json
import os
import socket
import struct
import sys
import time

AGENT_SOCKET_GLOB = "/tmp/logitech_kiros_agent-*"
AGENT_APP_PATH = "/Library/Application Support/Logitech.localized/LogiOptionsPlus/logioptionsplus_agent.app"
LAUNCH_AGENT_PLIST = "/Library/LaunchAgents/com.logi.optionsplus.plist"


def check_agent_installed():
    """Check if Logi Options+ agent is installed and provide guidance if not."""
    if os.path.exists(AGENT_APP_PATH):
        return True

    print("Error: Logi Options+ is not installed.", file=sys.stderr)
    print("", file=sys.stderr)
    print("Install Logi Options+ from:", file=sys.stderr)
    print("  https://www.logitech.com/software/logi-options-plus.html", file=sys.stderr)
    print("", file=sys.stderr)
    print("Note: Only the agent is needed — you can close the GUI after install.", file=sys.stderr)
    print("The agent runs as a background daemon and starts automatically at boot.", file=sys.stderr)
    return False


def check_agent_running():
    """Check if the agent process is running and the socket exists."""
    socks = glob.glob(AGENT_SOCKET_GLOB)
    if socks:
        return True

    if not check_agent_installed():
        sys.exit(1)

    print("Error: logioptionsplus_agent is not running.", file=sys.stderr)
    print("", file=sys.stderr)
    print("Try:", file=sys.stderr)
    print(f"  launchctl load {LAUNCH_AGENT_PLIST}", file=sys.stderr)
    print("  # or restart your Mac", file=sys.stderr)
    sys.exit(1)


class LogiAgent:
    """Client for the logioptionsplus_agent Unix socket protocol."""

    SUBSCRIBE_PATHS = [
        "/devices/state/changed",
        "/battery/state/changed",
        "/devices/options/device_arrival",
        "/devices/options/device_removal",
    ]

    def __init__(self):
        check_agent_running()
        self.sock = None
        self.msg_id = 0
        self._connect()

    def _connect(self):
        """Connect to agent socket and perform handshake."""
        socks = glob.glob(AGENT_SOCKET_GLOB)
        if not socks:
            check_agent_running()  # will sys.exit

        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass

        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(socks[0])
        self.sock.settimeout(5)

        # Read and discard server handshake
        header = self._recv_exact(4)
        total = struct.unpack("<I", header)[0]
        self._recv_exact(total)

        # Subscribe to required channels for device access
        for p in self.SUBSCRIBE_PATHS:
            self._send("SUBSCRIBE", p)
        time.sleep(0.3)
        # Drain subscribe acks
        self.sock.settimeout(0.5)
        try:
            while True:
                self.sock.recv(65536)
        except socket.timeout:
            pass

    def _recv_exact(self, n):
        data = b""
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("Connection closed")
            data += chunk
        return data

    def _send(self, verb, path, payload=None):
        self.msg_id += 1
        msg = {"msg_id": str(self.msg_id), "verb": verb, "path": path}
        if payload:
            msg["payload"] = payload
        data = json.dumps(msg).encode()
        packet = struct.pack(">I", 4) + b"json" + struct.pack(">I", len(data)) + data
        self.sock.send(struct.pack("<I", len(packet)) + packet)

    def call(self, verb, path, payload=None, _retried=False):
        """Send a request and return the JSON response, or None on timeout."""
        try:
            self._send(verb, path, payload)
            self.sock.settimeout(5)
            header = self._recv_exact(4)
            total = struct.unpack("<I", header)[0]
            rdata = self._recv_exact(total)
            fpos = 0
            while fpos + 4 <= len(rdata):
                flen = struct.unpack(">I", rdata[fpos : fpos + 4])[0]
                fpos += 4
                frame = rdata[fpos : fpos + flen]
                fpos += flen
                if frame != b"json":
                    return json.loads(frame)
        except socket.timeout:
            return None
        except (ConnectionError, BrokenPipeError, OSError):
            if not _retried:
                self._connect()
                return self.call(verb, path, payload, _retried=True)
            return None

    def recv_message(self, timeout=None):
        """Read one message from the socket. Returns parsed JSON or None on timeout."""
        if timeout is not None:
            self.sock.settimeout(timeout)
        try:
            header = self._recv_exact(4)
            total = struct.unpack("<I", header)[0]
            rdata = self._recv_exact(total)
            fpos = 0
            while fpos + 4 <= len(rdata):
                flen = struct.unpack(">I", rdata[fpos : fpos + 4])[0]
                fpos += 4
                frame = rdata[fpos : fpos + flen]
                fpos += flen
                if frame != b"json":
                    return json.loads(frame)
        except socket.timeout:
            return None

    def close(self):
        self.sock.close()

    # --- High-level helpers ---

    def get_ok(self, path, payload=None):
        """GET a path and return payload dict if SUCCESS, else None."""
        r = self.call("GET", path, payload)
        if r and r.get("result", {}).get("code") == "SUCCESS":
            return r.get("payload", {})
        return None

    def set_ok(self, path, payload):
        """SET a path and return True if SUCCESS."""
        r = self.call("SET", path, payload)
        if r and r.get("result", {}).get("code") == "SUCCESS":
            return True
        if r:
            what = r.get("result", {}).get("what", "")
            code = r.get("result", {}).get("code", "?")
            print(f"Error: {code} - {what}", file=sys.stderr)
        else:
            print("Error: no response from agent", file=sys.stderr)
        return False

    def get_devices(self):
        r = self.call("GET", "/devices/list")
        if r and r.get("result", {}).get("code") == "SUCCESS":
            return r.get("payload", {}).get("deviceInfos", [])
        return []

    def find_mouse(self):
        for dev in self.get_devices():
            if dev.get("deviceType") == "MOUSE":
                return dev
        return None

    def require_mouse(self):
        """Find mouse or exit with error."""
        mouse = self.find_mouse()
        if not mouse:
            print("Error: No mouse connected.", file=sys.stderr)
            self.close()
            sys.exit(1)
        return mouse

    def get_profiles(self):
        r = self.call("GET", "/v2/profiles")
        if r and r.get("result", {}).get("code") == "SUCCESS":
            return r.get("payload", {}).get("profiles", [])
        return []

    def get_default_profile(self):
        for p in self.get_profiles():
            if "application_id" not in p.get("applicationId", ""):
                return p
        return None

    def find_profile(self, name):
        """Find a profile by name or ID. Supports short names like 'safari', 'chrome'."""
        name_lower = name.lower()
        for p in self.get_profiles():
            pid = p.get("id", "")
            app_id = p.get("applicationId", "")
            if pid == name or app_id == name:
                return p
            if name_lower in app_id.lower():
                return p
        return None

    def require_profile(self, name=None):
        """Find profile by name or default. Exit on failure."""
        if name:
            profile = self.find_profile(name)
            if not profile:
                print(f"Error: profile '{name}' not found", file=sys.stderr)
                print("Use 'logi profiles' to list available profiles.", file=sys.stderr)
                self.close()
                sys.exit(1)
        else:
            profile = self.get_default_profile()
            if not profile:
                print("Error: could not determine default profile", file=sys.stderr)
                self.close()
                sys.exit(1)
        return profile

    def get_profile_assignments(self, profile_id, device_id, tags=None):
        payload = {
            "profileId": profile_id,
            "appId": profile_id,
            "deviceId": device_id,
        }
        if tags:
            payload["tags"] = tags
        r = self.call("GET", "/v2/profiles/slice/preview", payload)
        if r and r.get("result", {}).get("code") == "SUCCESS":
            return r.get("payload", {}).get("assignments", [])
        return []
