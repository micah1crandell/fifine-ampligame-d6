"""Command-line interface for the Fifine AmpliGame Standalone USB Driver & LCD Engine."""

import argparse
import sys
import time
try:
    from .deck import FifineDeck
    from .events import KeyEvent
    from .companion import CompanionBridge
except ImportError:
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from fifine.deck import FifineDeck
    from fifine.events import KeyEvent
    from fifine.companion import CompanionBridge


def cmd_listen(args):
    """Listens to hardware button presses directly over USB while keeping LCD awake."""
    brightness = getattr(args, "brightness", 100)
    deck = FifineDeck(auto_wake=True, default_brightness=brightness)

    print("=" * 65)
    print("   FIFINE AMPLIGAME PURE USB DRIVER & LCD ENGINE (STANDALONE)")
    print("   Hardware target: Fifine D6 / D6-Pro (15 LCD Keys, 3x5 Grid)")
    print("   Status: Waking deck from cold standby & streaming display...")
    print("   Press Ctrl+C to exit.")
    print("=" * 65)

    @deck.on_event
    def on_event(ev: KeyEvent):
        state_icon = "\033[92m[PRESSED ]\033[0m" if ev.is_press else "\033[90m[RELEASED]\033[0m"
        key_color = "\033[96m" if ev.is_press else "\033[0m"
        print(
            f"[{time.strftime('%H:%M:%S')}] {state_icon} -> {key_color}KEY {ev.key:2d}\033[0m  (Row {ev.row}, Col {ev.col})",
            flush=True,
        )

    deck.start(blocking=True)


def cmd_info(args):
    """Queries and displays device status and MCU firmware version."""
    deck = FifineDeck(auto_wake=False)
    deck.start(blocking=False)
    time.sleep(0.1)

    if not deck.is_connected:
        print("[ERROR] Fifine Stream Deck not detected. Please ensure USB cable is connected.")
        deck.stop()
        return 1

    fw = deck.get_firmware_version()
    print("=" * 50)
    print("   FIFINE HARDWARE STATUS")
    print("=" * 50)
    print(f"  Device:     Fifine AmpliGame Stream Deck (D6/D6-Pro)")
    print(f"  Vendor ID:  0x3142 (Hotspotek / Fifine)")
    print(f"  Product ID: 0x0060 (StreamDock USB HID)")
    print(f"  Firmware:   {fw or 'Unknown'}")
    print(f"  Connected:  Yes")
    print("=" * 50)
    deck.stop()
    return 0


def cmd_brightness(args):
    """Sets the LCD backlight brightness (0..100)."""
    level = int(args.level)
    deck = FifineDeck(auto_wake=False)
    deck.start(blocking=False)
    time.sleep(0.1)
    if not deck.is_connected:
        print("[ERROR] Fifine Stream Deck not detected.")
        deck.stop()
        return 1

    deck.set_brightness(level)
    time.sleep(0.05)
    print(f"[OK] Backlight brightness set to {level}%.")
    deck.stop()
    return 0


def cmd_set_image(args):
    """Uploads an image to a specific key."""
    key_id = int(args.key)
    path = args.image_path
    deck = FifineDeck(auto_wake=False)
    deck.start(blocking=False)
    time.sleep(0.1)
    if not deck.is_connected:
        print("[ERROR] Fifine Stream Deck not detected.")
        deck.stop()
        return 1

    deck.set_key_image(key_id, path, blocking=True)
    print(f"[OK] Uploaded '{path}' to Key {key_id}.")
    deck.stop()
    return 0


def cmd_companion(args):
    """Bridges Fifine AmpliGame D6 to Bitfocus Companion as a 15-key surface."""
    host = getattr(args, "host", "127.0.0.1")
    port = getattr(args, "port", 16622)
    device_id = getattr(args, "device_id", "fifine-d6-01")
    brightness = getattr(args, "brightness", 100)
    zoom = getattr(args, "zoom", 1.18)
    size = getattr(args, "size", 100)

    print("=" * 65)
    print("   FIFINE AMPLIGAME -> BITFOCUS COMPANION SATELLITE BRIDGE")
    print("   Protocol: Companion Satellite TCP API")
    print(f"   Target:   {host}:{port} (Device ID: {device_id})")
    print(f"   Display:  15 LCD Keys, {size}x{size} native, zoom: {zoom}x")
    print("   Status:   Connecting... Press Ctrl+C to exit.")
    print("=" * 65)

    deck = FifineDeck(auto_wake=True, default_brightness=brightness)
    bridge = CompanionBridge(
        deck=deck,
        host=host,
        port=port,
        device_id=device_id,
        product_name="Fifine AmpliGame D6",
        bitmap_size=size,
        zoom=zoom,
    )

    bridge.start(blocking=True)


def cmd_clear(args):
    """Clears all LCD key displays to black."""
    deck = FifineDeck(auto_wake=False)
    deck.start(blocking=False)
    time.sleep(0.1)
    if not deck.is_connected:
        print("[ERROR] Fifine Stream Deck not detected.")
        deck.stop()
        return 1

    deck.clear()
    time.sleep(0.05)
    print("[OK] LCD Framebuffer cleared.")
    deck.stop()
    return 0


def main():
    parser = argparse.ArgumentParser(description="Fifine AmpliGame Standalone USB Driver & LCD Framebuffer CLI")
    subparsers = parser.add_subparsers(dest="command")

    # listen
    p_listen = subparsers.add_parser("listen", help="Wake deck, light up LCD, and listen for live button events")
    p_listen.add_argument("--brightness", "-b", type=int, default=100, help="LCD brightness level 0..100 (default: 100)")

    # info
    subparsers.add_parser("info", help="Query device status and MCU firmware version")

    # brightness
    p_bright = subparsers.add_parser("brightness", help="Set LCD backlight brightness (0..100)")
    p_bright.add_argument("level", type=int, help="Brightness percentage 0..100")

    # set-image
    p_img = subparsers.add_parser("set-image", help="Upload an image to a key")
    p_img.add_argument("key", type=int, help="Key ID 1..15")
    p_img.add_argument("image_path", help="Path to image file (PNG, JPG, BMP, etc.)")

    # clear
    subparsers.add_parser("clear", help="Clear all LCD keys to black")

    # companion
    p_comp = subparsers.add_parser("companion", help="Bridge Fifine D6 to Bitfocus Companion as a 15-key surface")
    p_comp.add_argument("--host", default="127.0.0.1", help="Bitfocus Companion host IP (default: 127.0.0.1)")
    p_comp.add_argument("--port", type=int, default=16622, help="Bitfocus Companion Satellite port (default: 16622)")
    p_comp.add_argument("--device-id", default="fifine-d6-01", help="Unique Device ID string (default: fifine-d6-01)")
    p_comp.add_argument("--brightness", "-b", type=int, default=100, help="Initial LCD brightness level 0..100 (default: 100)")
    p_comp.add_argument("--zoom", "-z", type=float, default=1.18, help="Scaling zoom factor to fill keycaps edge-to-edge (default: 1.18)")
    p_comp.add_argument("--size", "-s", type=int, default=100, help="Bitmap canvas size requested from Companion (default: 100)")

    args = parser.parse_args()

    if args.command == "listen" or not args.command:
        cmd_listen(args)
    elif args.command == "companion":
        cmd_companion(args)
    elif args.command == "info":
        sys.exit(cmd_info(args))
    elif args.command == "brightness":
        sys.exit(cmd_brightness(args))
    elif args.command == "set-image":
        sys.exit(cmd_set_image(args))
    elif args.command == "clear":
        sys.exit(cmd_clear(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
