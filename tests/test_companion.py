"""Unit tests for the Bitfocus Companion Satellite Bridge."""

import base64
import io
import socket
import threading
import time
import unittest
from unittest.mock import MagicMock

from PIL import Image

from fifine.companion import (
    parse_satellite_line,
    decode_companion_bitmap,
    CompanionBridge,
)
from fifine.display import clean_baseline_jpeg, convert_image_to_jpeg
from fifine.events import KeyEvent


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

    def assert_d6_jpeg(self, jpeg, expected_size):
        self.assertTrue(jpeg.startswith(b"\xff\xd8"))
        self.assertTrue(jpeg.endswith(b"\xff\xd9"))
        self.assertIn(b"JFIF\x00", jpeg[:20])
        self.assertIn(b"\xff\xc0", jpeg)
        self.assertNotIn(b"\xff\xc2", jpeg)
        self.assertNotIn(b"\xff\xdd", jpeg)
        self.assertFalse(
            any(bytes((0xFF, marker)) in jpeg for marker in range(0xD0, 0xD8))
        )
        with Image.open(io.BytesIO(jpeg)) as image:
            self.assertEqual(image.size, expected_size)

    def test_clean_baseline_jpeg_rejects_restart_markers(self):
        with self.assertRaisesRegex(ValueError, "restart markers"):
            clean_baseline_jpeg(b"\xff\xd8\xff\xd0\xff\xd9")

    def test_decode_jpeg_is_resized_and_reencoded_for_d6(self):
        image = Image.new("RGB", (72, 72), color=(255, 0, 0))
        source = io.BytesIO()
        image.save(source, format="JPEG")
        raw_jpeg = source.getvalue()
        b64 = base64.b64encode(raw_jpeg).decode("ascii")
        decoded = decode_companion_bitmap(b64, (100, 100))
        self.assert_d6_jpeg(decoded, (100, 100))

    def test_decode_png_for_d6(self):
        image = Image.new("RGB", (72, 72), color=(255, 0, 0))
        source = io.BytesIO()
        image.save(source, format="PNG")
        b64 = base64.b64encode(source.getvalue()).decode("ascii")

        decoded = decode_companion_bitmap(b64, (100, 100))
        self.assert_d6_jpeg(decoded, (100, 100))

    def test_companion_bitmap_is_rotated_180_degrees_once(self):
        image = Image.new("RGB", (100, 100))
        colors = {
            (0, 0): (255, 0, 0),
            (1, 0): (0, 255, 0),
            (0, 1): (0, 0, 255),
            (1, 1): (255, 255, 0),
        }
        for y in range(100):
            for x in range(100):
                image.putpixel((x, y), colors[(x // 50, y // 50)])

        source = io.BytesIO()
        image.save(source, format="PNG")
        bitmap = base64.b64encode(source.getvalue()).decode("ascii")
        decoded = decode_companion_bitmap(bitmap, (100, 100), zoom=1.0)
        converted = convert_image_to_jpeg(decoded, 100, 100)
        self.assert_d6_jpeg(converted, (100, 100))

        with Image.open(io.BytesIO(converted)) as output:
            top_left = output.getpixel((10, 10))
            top_right = output.getpixel((90, 10))
            bottom_left = output.getpixel((10, 90))
            bottom_right = output.getpixel((90, 90))

        self.assertGreater(top_left[0], 150)
        self.assertGreater(top_left[1], 150)
        self.assertGreater(top_right[2], 150)
        self.assertGreater(bottom_left[1], 150)
        self.assertGreater(bottom_right[0], 150)
        self.assertLess(bottom_right[1], 100)

    def test_convert_jpeg_is_resized_and_reencoded_for_d6(self):
        image = Image.new("RGB", (72, 72), color=(0, 255, 0))
        source = io.BytesIO()
        image.save(source, format="JPEG")

        converted = convert_image_to_jpeg(source.getvalue(), 100, 100)
        self.assert_d6_jpeg(converted, (100, 100))


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
