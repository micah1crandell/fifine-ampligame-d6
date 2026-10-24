#!/usr/bin/env python3
"""Interactive Live Test for Fifine AmpliGame Stream Deck (D6 / D6-Pro).

Features:
- Initializes the LCD subsystem and powers on backlights.
- Renders 15 vibrant, labeled buttons across the entire deck grid.
- Streams live button press/release events with sub-10ms latency.
- Dynamically updates the pressed button LCD tile to provide instant visual feedback.
- Runs continuously with background heartbeat until Ctrl+C.
"""

import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fifine import FifineDeck, generate_key_tile

# 15 distinct high-contrast colors and labels for the 3x5 button grid
KEY_CONFIGS = [
    {"title": "MUTE",    "subtitle": "MIC",     "bg": "#ef4444", "active_bg": "#ffffff"},
    {"title": "DISCORD", "subtitle": "VOICE",   "bg": "#5865f2", "active_bg": "#ffffff"},
    {"title": "SPOTIFY", "subtitle": "PLAY",    "bg": "#1db954", "active_bg": "#ffffff"},
    {"title": "OBS",     "subtitle": "RECORD",  "bg": "#3b82f6", "active_bg": "#ffffff"},
    {"title": "STREAM",  "subtitle": "LIVE",    "bg": "#a855f7", "active_bg": "#ffffff"},

    {"title": "SCENE 1", "subtitle": "INTRO",   "bg": "#f97316", "active_bg": "#ffffff"},
    {"title": "SCENE 2", "subtitle": "GAME",    "bg": "#eab308", "active_bg": "#ffffff"},
    {"title": "SCENE 3", "subtitle": "BRB",     "bg": "#06b6d4", "active_bg": "#ffffff"},
    {"title": "CAMERA",  "subtitle": "TOGGLE",  "bg": "#ec4899", "active_bg": "#ffffff"},
    {"title": "LIGHTS",  "subtitle": "RGB",     "bg": "#14b8a6", "active_bg": "#ffffff"},

    {"title": "CLIP",    "subtitle": "30 SEC",  "bg": "#84cc16", "active_bg": "#ffffff"},
    {"title": "CHAT",    "subtitle": "SLOW",    "bg": "#0ea5e9", "active_bg": "#ffffff"},
    {"title": "EFFECT",  "subtitle": "SFX 1",   "bg": "#8b5cf6", "active_bg": "#ffffff"},
    {"title": "EFFECT",  "subtitle": "SFX 2",   "bg": "#f43f5e", "active_bg": "#ffffff"},
    {"title": "SETTINGS","subtitle": "PREFS",  "bg": "#10b981", "active_bg": "#ffffff"},
]

def render_tile(key_id: int, pressed: bool = False) -> bytes:
    cfg = KEY_CONFIGS[key_id - 1]
    if pressed:
        return generate_key_tile(
            title="PRESSED",
            subtitle=f"KEY {key_id}",
            number=key_id,
            bg_color=cfg["active_bg"],
            text_color="#000000",
            border_color="#ffcc00",
            width=100,
            height=100,
        )
    return generate_key_tile(
        title=cfg["title"],
        subtitle=cfg["subtitle"],
        number=key_id,
        bg_color=cfg["bg"],
        text_color="#ffffff",
        border_color="#ffffff",
        width=100,
        height=100,
    )

def main():
    print("=" * 60)
    print("   Fifine AmpliGame Stream Deck (D6) - Live Interactive Test")
    print("=" * 60)

    deck = FifineDeck(auto_wake=False, default_brightness=100)

    # Pre-render idle tiles for all 15 buttons
    idle_tiles = {key_id: render_tile(key_id, pressed=False) for key_id in range(1, 16)}

    @deck.on_press
    def handle_press(key: int):
        print(f"[EVENT] Button {key:2d} ({KEY_CONFIGS[key - 1]['title']}) PRESSED -> Updating LCD tile to active")
        try:
            deck.set_key_image(key, render_tile(key, pressed=True), blocking=False)
        except Exception as err:
            print(f"   Error updating tile: {err}", file=sys.stderr)

    @deck.on_release
    def handle_release(key: int):
        print(f"[EVENT] Button {key:2d} ({KEY_CONFIGS[key - 1]['title']}) released -> Restoring idle tile")
        try:
            deck.set_key_image(key, idle_tiles[key], blocking=False)
        except Exception as err:
            print(f"   Error restoring tile: {err}", file=sys.stderr)

    # Start the hardware driver
    deck.start(blocking=False)
    time.sleep(0.5)

    if not deck.is_connected:
        print("[ERROR] Fifine Stream Deck not detected. Please ensure USB is plugged in.")
        return

    fw = deck.get_firmware_version()
    print(f"[OK] Connected to Stream Deck (Firmware: {fw})")
    print("[INIT] Initializing display and uploading 15 custom tiles...")

    # Upload all 15 initial tiles and wake hardware
    deck.wake(initial_keys=idle_tiles, brightness=100)

    print("\n[READY] Display initialized. All 15 LCD keys are now active.")
    print("[INFO] Press any button on the physical deck to see live press events and screen updates.")
    print("       Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nStopping Fifine Deck...")
    finally:
        deck.stop()
        print("Done.")

if __name__ == "__main__":
    main()
