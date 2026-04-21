"""Tests for agent.py protocol framing (offline, no agent needed)."""

import struct
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestFraming:
    """Test the wire protocol framing format."""

    def test_le_prefix(self):
        """LE 4-byte prefix encodes total payload size."""
        total = 42
        header = struct.pack("<I", total)
        assert len(header) == 4
        assert struct.unpack("<I", header)[0] == total

    def test_be_frame(self):
        """BE 4-byte frame length + frame data."""
        data = b"json"
        frame = struct.pack(">I", len(data)) + data
        assert len(frame) == 8
        flen = struct.unpack(">I", frame[:4])[0]
        assert flen == 4
        assert frame[4:] == b"json"

    def test_full_packet(self):
        """Full packet: [LE total] [BE "json"] [BE json_data]."""
        msg = json.dumps({"msg_id": "1", "verb": "GET", "path": "/test"}).encode()
        json_frame = struct.pack(">I", 4) + b"json"
        data_frame = struct.pack(">I", len(msg)) + msg
        packet_payload = json_frame + data_frame
        packet = struct.pack("<I", len(packet_payload)) + packet_payload

        # Parse back
        total = struct.unpack("<I", packet[:4])[0]
        assert total == len(packet_payload)

        pos = 4
        # Frame 1: "json"
        flen = struct.unpack(">I", packet[pos:pos+4])[0]
        pos += 4
        assert packet[pos:pos+flen] == b"json"
        pos += flen

        # Frame 2: JSON data
        flen = struct.unpack(">I", packet[pos:pos+4])[0]
        pos += 4
        parsed = json.loads(packet[pos:pos+flen])
        assert parsed["verb"] == "GET"
        assert parsed["path"] == "/test"

    def test_request_response_key_difference(self):
        """Request uses msg_id, response uses msgId (camelCase)."""
        req = {"msg_id": "1", "verb": "GET", "path": "/test"}
        resp = {"msgId": "1", "verb": "GET", "path": "/test", "result": {"code": "SUCCESS"}}
        assert "msg_id" in req
        assert "msgId" in resp


class TestAgentHelpers:
    """Test agent module helper functions (no connection needed)."""

    def test_check_paths_exist(self):
        from agent import AGENT_SOCKET_GLOB, AGENT_APP_PATH, LAUNCH_AGENT_PLIST
        assert "/tmp/" in AGENT_SOCKET_GLOB
        assert "logioptionsplus" in AGENT_APP_PATH
        assert ".plist" in LAUNCH_AGENT_PLIST
