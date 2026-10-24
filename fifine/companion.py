"""Bitfocus Companion Satellite Bridge for the Fifine AmpliGame D6.

Enables the Fifine AmpliGame Stream Deck to operate as a native 15-key control surface
inside Bitfocus Companion using the official Companion Satellite protocol over TCP (port 16622).
"""

import base64
import io
import os
import re
import select
import socket
import subprocess
import sys
import tempfile
import threading
import time
from typing import Callable, Dict, Optional, Tuple, Any

from .deck import FifineDeck
from .events import KeyEvent
from .display import clean_baseline_jpeg, rotate_buffer_180, generate_solid_color_jpeg

try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False


DEFAULT_COMPANION_HOST = "127.0.0.1"
DEFAULT_COMPANION_PORT = 16622
DEFAULT_DEVICE_ID = "fifine-d6-01"
DEFAULT_PRODUCT_NAME = "Fifine AmpliGame D6"


def parse_satellite_line(line: str) -> Tuple[str, Dict[str, str]]:
    """Parses a line from the Companion Satellite protocol.

    Example:
        'KEY-STATE DEVICEID=fifine-01 KEY=0 BITMAP=abc== COLOR=#ff0000'
        -> ('KEY-STATE', {'DEVICEID': 'fifine-01', 'KEY': '0', 'BITMAP': 'abc==', 'COLOR': '#ff0000'})
    """
    line = line.strip()
    if not line:
        return "", {}

    parts = line.split(maxsplit=1)
    cmd = parts[0].upper()
    args: Dict[str, str] = {}

    if len(parts) > 1:
        args["_raw_payload"] = parts[1]
        matches = re.findall(r'(\w+)=(?:"([^"]*)"|([^\s]+))', parts[1])
        for k, v_quoted, v_unquoted in matches:
            args[k] = v_quoted if v_quoted else v_unquoted

    return cmd, args


def decode_companion_bitmap(
    b64_payload: str,
    target_size: Tuple[int, int] = (100, 100),
    zoom: float = 1.18,
) -> Optional[bytes]:
    """Decodes a base64 bitmap payload from Companion into pure baseline JPEG bytes with 180° rotation and edge-to-edge scaling."""
    if not b64_payload or not b64_payload.strip():
        return None

    try:
        raw = base64.b64decode(b64_payload.strip())
    except Exception as e:
        print(f"[decode_companion_bitmap Error] Invalid base64: {e}", file=sys.stderr)
        return None

    # 1. If already JPEG
    if raw.startswith(b"\xff\xd8"):
        return clean_baseline_jpeg(raw)

    # Calculate filter string: crop outer margin if zoom > 1.0, scale to target_size, flip 180°
    if zoom > 1.0:
        vf_filter = f"crop=in_w/{zoom:.2f}:in_h/{zoom:.2f},scale={target_size[0]}:{target_size[1]},hflip,vflip"
    else:
        vf_filter = f"scale={target_size[0]}:{target_size[1]},hflip,vflip"

    # 2. Try ffmpeg directly (pure baseline JPEG without restart markers, fast in-memory pipe)
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i", "pipe:0",
                "-vf", vf_filter,
                "-vframes", "1",
                "-q:v", "2",
                "-f", "image2",
                "pipe:1"
            ],
            input=raw,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        if proc.stdout and proc.stdout.startswith(b"\xff\xd8"):
            return clean_baseline_jpeg(proc.stdout)
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pass

    # 3. Try Pillow if available
    if HAS_PILLOW:
        try:
            img = Image.open(io.BytesIO(raw)).convert("RGB")
            if zoom > 1.0:
                cw = int(img.width / zoom)
                ch = int(img.height / zoom)
                left = (img.width - cw) // 2
                top = (img.height - ch) // 2
                img = img.crop((left, top, left + cw, top + ch))
            if img.size != target_size:
                img = img.resize(target_size, Image.Resampling.LANCZOS)
            rotated = rotate_buffer_180(bytearray(img.tobytes()), target_size[0], target_size[1])
            rot_img = Image.frombytes("RGB", target_size, bytes(rotated))
            buf = io.BytesIO()
            rot_img.save(buf, format="JPEG", quality=90)
            return clean_baseline_jpeg(buf.getvalue())
        except Exception:
            pass

    # 4. Native macOS sips converter (converts to uncompressed BMP, then routes through rgb_buffer_to_jpeg)
    is_png = raw.startswith(b"\x89PNG")
    is_webp = len(raw) > 12 and raw[0:4] == b"RIFF" and raw[8:12] == b"WEBP"

    if is_png or is_webp:
        suffix = ".png" if is_png else ".webp"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f_in:
            f_in.write(raw)
            in_name = f_in.name
        out_bmp = in_name + ".bmp"
        try:
            subprocess.run(
                ["sips", "-s", "format", "bmp", "-z", str(target_size[1]), str(target_size[0]), in_name, "--out", out_bmp],
                check=True,
                capture_output=True,
            )
            with open(out_bmp, "rb") as f_out:
                bmp_data = f_out.read()
            if len(bmp_data) >= 54 + target_size[0] * target_size[1] * 3:
                raw_bgr = bmp_data[54:]
                row_stride = ((target_size[0] * 3 + 3) // 4) * 4
                rgb_pixels = bytearray(target_size[0] * target_size[1] * 3)
                for y in range(target_size[1]):
                    src_y = target_size[1] - 1 - y  # BMP is bottom-to-top
                    src_offset = src_y * row_stride
                    dst_offset = y * target_size[0] * 3
                    for x in range(target_size[0]):
                        b = raw_bgr[src_offset + x * 3]
                        g = raw_bgr[src_offset + x * 3 + 1]
                        r = raw_bgr[src_offset + x * 3 + 2]
                        rgb_pixels[dst_offset + x * 3] = r
                        rgb_pixels[dst_offset + x * 3 + 1] = g
                        rgb_pixels[dst_offset + x * 3 + 2] = b
                from .display import rgb_buffer_to_jpeg
                return rgb_buffer_to_jpeg(bytes(rgb_pixels), target_size[0], target_size[1])
        except Exception as e:
            print(f"[CompanionBridge sips BMP error]: {e}", file=sys.stderr)
        finally:
            if os.path.exists(in_name):
                os.unlink(in_name)
            if os.path.exists(out_bmp):
                os.unlink(out_bmp)

    # 5. Raw RGB or RGBA buffer (e.g. 72x72x3 or 72x72x4 or 100x100x3)
    for w, h, ch in [(72, 72, 3), (72, 72, 4), (100, 100, 3), (100, 100, 4)]:
        if len(raw) == w * h * ch:
            if ch == 4:
                rgb_bytes = bytearray(w * h * 3)
                for src_idx in range(w * h):
                    rgb_bytes[src_idx * 3 : src_idx * 3 + 3] = raw[src_idx * 4 : src_idx * 4 + 3]
            else:
                rgb_bytes = raw

            from .display import rgb_buffer_to_jpeg
            return rgb_buffer_to_jpeg(bytes(rgb_bytes), w, h)

    return None


class CompanionBridge:
    """Bridges Fifine AmpliGame Stream Deck to Bitfocus Companion via the Satellite API.

    Example:
        deck = FifineDeck()
        bridge = CompanionBridge(deck=deck, host="127.0.0.1", port=16622)
        bridge.start(blocking=True)
    """

    def __init__(
        self,
        deck: Optional[FifineDeck] = None,
        host: str = DEFAULT_COMPANION_HOST,
        port: int = DEFAULT_COMPANION_PORT,
        device_id: str = DEFAULT_DEVICE_ID,
        product_name: str = DEFAULT_PRODUCT_NAME,
        bitmap_size: int = 100,
        zoom: float = 1.18,
        reconnect_interval: float = 3.0,
        ping_interval: float = 2.0,
        on_status_change: Optional[Callable[[str], None]] = None,
    ):
        self.host = host
        self.port = port
        self.device_id = device_id
        self.product_name = product_name
        self.bitmap_size = bitmap_size
        self.zoom = zoom
        self.reconnect_interval = reconnect_interval
        self.ping_interval = ping_interval
        self.on_status_change = on_status_change

        self._deck_owned = deck is None
        self.deck = deck if deck is not None else FifineDeck()

        self._is_running = False
        self._is_connected_to_companion = False
        self._socket: Optional[socket.socket] = None
        self._send_lock = threading.Lock()

        self._thread: Optional[threading.Thread] = None
        self._ping_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @property
    def is_connected_to_companion(self) -> bool:
        """Returns True if the TCP connection to Companion is currently active."""
        return self._is_connected_to_companion

    def _log_status(self, message: str):
        print(f"[CompanionBridge] {message}", flush=True)
        if self.on_status_change:
            try:
                self.on_status_change(message)
            except Exception:
                pass

    def start(self, blocking: bool = False):
        """Starts the bridge and connects to Bitfocus Companion."""
        if self._is_running:
            return

        self._is_running = True
        self._stop_event.clear()

        # 1. Wire deck button callbacks
        self.deck.on_press(self._handle_deck_press)
        self.deck.on_release(self._handle_deck_release)

        # 2. Start hardware deck driver
        if not self.deck.is_connected:
            self.deck.start(blocking=False)

        # 3. Spawn background TCP manager
        self._thread = threading.Thread(
            target=self._connection_loop,
            daemon=True,
            name="CompanionSatelliteBridge"
        )
        self._thread.start()

        self._log_status(f"Bridge started. Connecting to Bitfocus Companion at {self.host}:{self.port}...")

        if blocking:
            try:
                while not self._stop_event.wait(0.5):
                    pass
            except KeyboardInterrupt:
                self._log_status("Stopping on user interruption...")
            finally:
                self.stop()

    def stop(self):
        """Cleanly unregisters the surface and disconnects from Companion."""
        if not self._is_running:
            return

        self._is_running = False
        self._stop_event.set()

        # Send REMOVE-DEVICE to Companion
        if self._is_connected_to_companion:
            self._send_line(f"REMOVE-DEVICE DEVICEID={self.device_id}")

        self._close_socket()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)

        if self._deck_owned:
            self.deck.stop()

        self._log_status("Bridge stopped.")

    def _handle_deck_press(self, logical_key: int):
        """Called when a physical key on the Fifine D6 is pressed."""
        companion_key = logical_key - 1
        if 0 <= companion_key <= 14:
            self._send_line(f"KEY-PRESS DEVICEID={self.device_id} KEY={companion_key} PRESSED=true")

    def _handle_deck_release(self, logical_key: int):
        """Called when a physical key on the Fifine D6 is released."""
        companion_key = logical_key - 1
        if 0 <= companion_key <= 14:
            self._send_line(f"KEY-PRESS DEVICEID={self.device_id} KEY={companion_key} PRESSED=false")

    def _send_line(self, line: str) -> bool:
        """Thread-safe socket write with carriage return and newline."""
        with self._send_lock:
            if not self._socket or not self._is_connected_to_companion:
                return False
            try:
                payload = (line.strip() + "\n").encode("utf-8")
                self._socket.sendall(payload)
                return True
            except Exception as e:
                self._log_status(f"Socket send failed: {e}")
                self._is_connected_to_companion = False
                return False

    def _connection_loop(self):
        """Main connection and auto-reconnect worker."""
        while not self._stop_event.is_set():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                sock.settimeout(5.0)

                sock.connect((self.host, self.port))
                sock.settimeout(None)

                self._socket = sock
                self._is_connected_to_companion = True
                self._log_status(f"Connected to Bitfocus Companion at {self.host}:{self.port}")

                # Start periodic ping watchdog
                self._start_ping_thread()

                # Process incoming lines
                self._read_lines(sock)

            except (socket.error, ConnectionRefusedError, OSError) as e:
                self._is_connected_to_companion = False
                if not self._stop_event.is_set():
                    self._log_status(
                        f"Cannot reach Companion at {self.host}:{self.port} ({e}). Retrying in {self.reconnect_interval}s..."
                    )
                    self._stop_event.wait(self.reconnect_interval)
            finally:
                self._close_socket()

    def _start_ping_thread(self):
        """Starts periodic ping thread to keep Satellite connection alive."""
        def ping_worker():
            while self._is_connected_to_companion and not self._stop_event.is_set():
                ts = int(time.time() * 1000)
                if not self._send_line(f"PING {ts}"):
                    break
                self._stop_event.wait(self.ping_interval)

        self._ping_thread = threading.Thread(
            target=ping_worker,
            daemon=True,
            name="CompanionPingWorker"
        )
        self._ping_thread.start()

    def _close_socket(self):
        self._is_connected_to_companion = False
        with self._send_lock:
            if self._socket:
                try:
                    self._socket.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                try:
                    self._socket.close()
                except Exception:
                    pass
                self._socket = None

    def _read_lines(self, sock: socket.socket):
        """Reads newline-delimited lines from Companion socket."""
        buffer = ""
        while not self._stop_event.is_set() and self._is_connected_to_companion:
            # Non-blocking poll
            rlist, _, _ = select.select([sock], [], [], 0.5)
            if not rlist:
                continue

            try:
                chunk = sock.recv(4096)
                if not chunk:
                    self._log_status("Companion server closed connection.")
                    break
                buffer += chunk.decode("utf-8", errors="replace")

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip("\r").strip()
                    if line:
                        self._dispatch_companion_command(line)

            except Exception as e:
                if not self._stop_event.is_set():
                    self._log_status(f"Error reading from Companion socket: {e}")
                break

    def _dispatch_companion_command(self, line: str):
        """Dispatches commands received from Companion."""
        cmd, args = parse_satellite_line(line)
        if not cmd:
            return

        if cmd == "BEGIN":
            # Handshake greeting from Companion
            api_ver = args.get("ApiVersion", "unknown")
            comp_ver = args.get("CompanionVersion", "unknown")
            self._log_status(f"Companion Handshake: Version {comp_ver}, API {api_ver}")

            # Clear deck from cold-boot numbers to black
            self.deck.clear()

            # Register device: 15 keys, 5 per row (3 rows), request native PNG bitmaps
            reg_cmd = (
                f'ADD-DEVICE DEVICEID={self.device_id} '
                f'PRODUCT_NAME="{self.product_name}" '
                f'KEYS_TOTAL=15 KEYS_PER_ROW=5 BITMAPS={self.bitmap_size} BITMAP_FORMAT=png'
            )
            self._send_line(reg_cmd)
            self._log_status(f"Registered 15-key surface: '{self.product_name}' (ID: {self.device_id}, size: {self.bitmap_size}x{self.bitmap_size}, zoom: {self.zoom}x)")

        elif cmd == "CAPS":
            # Server capability declaration
            pass

        elif cmd == "ADD-DEVICE":
            # Server confirmation: ADD-DEVICE OK
            status = args.get("_raw_payload", "").strip()
            if "OK" in status:
                self._log_status("Surface registration confirmed by Bitfocus Companion.")

        elif cmd in ("KEY-STATE", "SUB-STATE"):
            dev_id = args.get("DEVICEID")
            if dev_id and dev_id != self.device_id:
                return

            key_str = args.get("KEY")
            control_id = args.get("CONTROLID")

            if key_str is not None:
                try:
                    comp_key = int(key_str)
                except ValueError:
                    return
            elif control_id is not None:
                try:
                    if "/" in control_id:
                        row, col = map(int, control_id.split("/", 1))
                        comp_key = row * 5 + col
                    else:
                        comp_key = int(control_id)
                except ValueError:
                    return
            else:
                return

            logical_key = comp_key + 1
            if not (1 <= logical_key <= 15):
                return

            # Check for image bitmap
            bitmap_payload = args.get("BITMAP")
            if bitmap_payload:
                img = decode_companion_bitmap(bitmap_payload, (100, 100), zoom=self.zoom)
                if img is not None:
                    try:
                        self.deck.set_key_image(logical_key, img, blocking=False)
                        print(f"[CompanionBridge] Display -> Key {logical_key} (Slot {comp_key}) updated from Companion", flush=True)
                    except Exception as e:
                        print(f"[CompanionBridge] Failed to set key {logical_key} image: {e}", file=sys.stderr)
            elif "COLOR" in args:
                color = args["COLOR"]
                try:
                    self.deck.set_key_color(logical_key, color, blocking=False)
                    print(f"[CompanionBridge] Color -> Key {logical_key} set to {color}", flush=True)
                except Exception as e:
                    print(f"[CompanionBridge] Failed to set key {logical_key} color: {e}", file=sys.stderr)
            else:
                # Blank / cleared button
                try:
                    self.deck.set_key_color(logical_key, (0, 0, 0), blocking=False)
                except Exception:
                    pass

        elif cmd == "BRIGHTNESS":
            dev_id = args.get("DEVICEID")
            if dev_id and dev_id != self.device_id:
                return
            val_str = args.get("VALUE")
            if val_str:
                try:
                    val = max(0, min(100, int(val_str)))
                    self.deck.set_brightness(val)
                except ValueError:
                    pass

        elif cmd == "PING":
            # Echo back pong
            payload = args.get("_raw_payload", "").strip()
            self._send_line(f"PONG {payload}")

        elif cmd == "PONG":
            # Heartbeat confirmed
            pass
