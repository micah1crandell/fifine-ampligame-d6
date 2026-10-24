"""Unit tests for the Bitfocus Companion Satellite Bridge."""

import base64
import io
import socket
import threading
import time
import unittest
from unittest.mock import MagicMock

from fifine.companion import (
    parse_satellite_line,
    decode_companion_bitmap,
    CompanionBridge,
)
from fifine.events import KeyEvent

try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False


class TestCompanionProtocol(unittest.TestCase):
    def test_parse_satellite_line(self):
        # 1. Standard KEY-STATE line
        cmd, args = parse_satellite_line("KEY-STATE DEVICEID=fifine-01 KEY=0 BITMAP=abc123== COLOR=#ff0000")
        self.assertEqual(cmd, "KEY-STATE")
        self.assertEqual(args["DEVICEID"], "fifine-01")
        self.assertEqual(args["KEY"], "0")
        self.assertEqual(args["BITMAP"], "abc123==")
        self.assertEqual(args["COLOR"], "#ff0000")

        # 2. BEGIN greeting
        cmd, args = parse_satellite_line("BEGIN CompanionVersion=3.4.0 ApiVersion=1.7.0")
        self.assertEqual(cmd, "BEGIN")
        self.assertEqual(args["CompanionVersion"], "3.4.0")
        self.assertEqual(args["ApiVersion"], "1.7.0")

        # 3. Quoted arguments
        cmd, args = parse_satellite_line('ADD-DEVICE DEVICEID=fifine-01 PRODUCT_NAME="Fifine AmpliGame D6" KEYS_TOTAL=15')
        self.assertEqual(cmd, "ADD-DEVICE")
        self.assertEqual(args["DEVICEID"], "fifine-01")
        self.assertEqual(args["PRODUCT_NAME"], "Fifine AmpliGame D6")
        self.assertEqual(args["KEYS_TOTAL"], "15")

        # 4. PING
        cmd, args = parse_satellite_line("PING 1718900000")
        self.assertEqual(cmd, "PING")
        self.assertEqual(args["_raw_payload"], "1718900000")

    def test_decode_raw_jpeg_fallback(self):
        # Fake minimal JPEG SOI marker
        raw_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 20 + b"\xff\xd9"
        b64 = base64.b64encode(raw_jpeg).decode("ascii")
        decoded = decode_companion_bitmap(b64, (100, 100))
        self.assertIsNotNone(decoded)
        self.assertTrue(decoded.startswith(b"\xff\xd8"))
        self.assertTrue(decoded.endswith(b"\xff\xd9"))

    def test_decode_png_with_sips(self):
        # Create a small 2x2 PNG using sips
        import tempfile, subprocess, os
        with tempfile.NamedTemporaryFile(suffix=".ppm", delete=False) as f:
            f.write(b"P6\n2 2\n255\n\xff\x00\x00\x00\xff\x00\x00\x00\xff\xff\xff\x00")
            ppm_path = f.name
        png_path = ppm_path + ".png"
        try:
            subprocess.run(["sips", "-s", "format", "png", ppm_path, "--out", png_path], check=True, capture_output=True)
            with open(png_path, "rb") as f:
                png_bytes = f.read()
            b64_str = base64.b64encode(png_bytes).decode("ascii")

            # Decode via decode_companion_bitmap
            decoded_jpeg = decode_companion_bitmap(b64_str, (100, 100))
            self.assertIsNotNone(decoded_jpeg)
            self.assertTrue(decoded_jpeg.startswith(b"\xff\xd8"))
            self.assertTrue(decoded_jpeg.endswith(b"\xff\xd9"))
        finally:
            for p in [ppm_path, png_path]:
                if os.path.exists(p):
                    os.unlink(p)

    def test_decode_companion_bitmap(self):
        if not HAS_PILLOW:
            self.skipTest("Pillow not installed")

        # Generate 100x100 PNG
        test_img = Image.new("RGB", (72, 72), color=(255, 0, 0))
        buf = io.BytesIO()
        test_img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")

        decoded = decode_companion_bitmap(b64, (100, 100))
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.size, (100, 100))


class TestCompanionBridgeMock(unittest.TestCase):
    def test_bridge_handshake_and_events(self):
        # 1. Setup mock socket pair
        sock_server, sock_client = socket.socketpair()

        mock_deck = MagicMock()
        mock_deck.is_connected = True

        bridge = CompanionBridge(
            deck=mock_deck,
            device_id="test-d6",
            product_name="Test Deck",
            ping_interval=1.0,
        )

        bridge._socket = sock_client
        bridge._is_connected_to_companion = True
        bridge._is_running = True

        # Test sending key press from deck
        bridge._handle_deck_press(1)  # Logical Key 1 -> Companion Key 0
        data = sock_server.recv(1024).decode("utf-8")
        self.assertIn("KEY-PRESS DEVICEID=test-d6 KEY=0 PRESSED=true", data)

        bridge._handle_deck_release(1)
        data = sock_server.recv(1024).decode("utf-8")
        self.assertIn("KEY-PRESS DEVICEID=test-d6 KEY=0 PRESSED=false", data)

        # Test bottom-right button (Key 15 -> Companion Key 14)
        bridge._handle_deck_press(15)
        data = sock_server.recv(1024).decode("utf-8")
        self.assertIn("KEY-PRESS DEVICEID=test-d6 KEY=14 PRESSED=true", data)

        # Test receiving BEGIN from server triggers ADD-DEVICE
        bridge._dispatch_companion_command("BEGIN CompanionVersion=3.4.0 ApiVersion=1.7.0")
        data = sock_server.recv(1024).decode("utf-8")
        self.assertIn("ADD-DEVICE DEVICEID=test-d6", data)
        self.assertIn('PRODUCT_NAME="Test Deck"', data)
        self.assertIn("KEYS_TOTAL=15", data)
        self.assertIn("KEYS_PER_ROW=5", data)

        # Test receiving KEY-STATE COLOR updates deck
        bridge._dispatch_companion_command("KEY-STATE DEVICEID=test-d6 KEY=2 COLOR=#00ff00")
        mock_deck.set_key_color.assert_called_with(3, "#00ff00", blocking=False)  # Companion Key 2 -> Logical Key 3

        # Test receiving BRIGHTNESS updates deck
        bridge._dispatch_companion_command("BRIGHTNESS DEVICEID=test-d6 VALUE=75")
        mock_deck.set_brightness.assert_called_with(75)

        # Test PING from server produces PONG
        bridge._dispatch_companion_command("PING 998877")
        data = sock_server.recv(1024).decode("utf-8")
        self.assertIn("PONG 998877", data)

        bridge.stop()
        sock_server.close()
        sock_client.close()


if __name__ == "__main__":
    unittest.main()
