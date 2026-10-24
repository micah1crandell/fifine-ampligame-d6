#!/usr/bin/env python3
"""Run Fifine Stream Deck with custom layout from config.json.

Renders custom title, subtitle, and color on each LCD button.
Supports dynamic grid selection and interactive press visual feedback.
"""

import json
import sys
import os
import subprocess
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fifine import FifineDeck, KeyEvent, generate_key_tile, convert_image_to_jpeg

CONFIG_PATH = Path(__file__).parent.parent / "config.json"

def execute_action(action: dict):
    """Executes mapped action from config."""
    atype = action.get("type")
    if atype == "shell":
        cmd = action.get("command")
        if cmd:
            print(f"  [Exec Shell]: {cmd}")
            subprocess.Popen(cmd, shell=True)
    elif atype == "media":
        media = action.get("media")
        print(f"  [Exec Media]: {media}")
        if media == "mute":
            subprocess.run(["osascript", "-e", "set volume output muted not (output muted of (get volume settings))"])
        elif media == "vol_up":
            subprocess.run(["osascript", "-e", "set volume output volume ((output volume of (get volume settings)) + 6)"])
        elif media == "vol_down":
            subprocess.run(["osascript", "-e", "set volume output volume ((output volume of (get volume settings)) - 6)"])
        elif media == "play_pause":
            subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 49']) # space or media key
    elif atype == "hotkey":
        key = action.get("key")
        print(f"  [Exec Hotkey]: {key}")

def main():
    if not CONFIG_PATH.is_file():
        print(f"Error: {CONFIG_PATH} not found.")
        return

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    grid_name = sys.argv[1] if len(sys.argv) > 1 else cfg.get("active_grid", "Roku Remote")
    grids = cfg.get("grids", {})
    if grid_name not in grids:
        print(f"Grid '{grid_name}' not found. Available grids: {list(grids.keys())}")
        return

    grid = grids[grid_name]
    buttons_cfg = grid.get("buttons", {})
    print(f"Loading Grid: '{grid_name}' ({len(buttons_cfg)} buttons configured)")

    normal_tiles = {}
    pressed_tiles = {}
    actions = {}

    for key_id in range(1, 16):
        btn = buttons_cfg.get(str(key_id), {})
        title = btn.get("title")
        subtitle = btn.get("subtitle")
        color = btn.get("color", "#1e293b")
        img_path = btn.get("image")
        actions[key_id] = btn.get("action")

        if img_path and os.path.exists(img_path):
            normal_tiles[key_id] = convert_image_to_jpeg(img_path)
        else:
            normal_tiles[key_id] = generate_key_tile(
                title=title,
                subtitle=subtitle,
                number=key_id if not title else None,
                bg_color=color,
                border_color="#38bdf8" if title else "#334155",
                text_color="#ffffff",
                width=100,
                height=100,
            )

        pressed_tiles[key_id] = generate_key_tile(
            title=title or f"KEY {key_id}",
            subtitle="ACTIVE",
            bg_color="#ffffff",
            border_color="#ffffff",
            text_color="#000000",
            width=100,
            height=100,
        )

    deck = FifineDeck(auto_wake=False, default_brightness=100)

    @deck.on_event
    def handle_event(ev: KeyEvent):
        if ev.is_press:
            print(f"[PRESS] Button {ev.key} pressed: {buttons_cfg.get(str(ev.key), {}).get('title', 'Unknown')}")
            deck.set_key_image(ev.key, pressed_tiles.get(ev.key, normal_tiles.get(ev.key)))
            act = actions.get(ev.key)
            if act:
                execute_action(act)
        elif ev.is_release:
            deck.set_key_image(ev.key, normal_tiles.get(ev.key))

    print("Connecting and waking hardware LCD display...")
    deck.start(blocking=False)
    time.sleep(0.5)

    if not deck.is_connected:
        print("[ERROR] Fifine Stream Deck not found.")
        deck.stop()
        return

    # Wake with full custom tiles
    deck.wake(initial_keys=normal_tiles, brightness=100)
    print("=" * 60)
    print(f"  GRID '{grid_name.upper()}' LOADED ACROSS ALL 15 LCD KEYS!")
    print("  Custom displays are active on physical buttons.")
    print("  Press buttons on the deck to test actions (Ctrl+C to quit)...")
    print("=" * 60)

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        deck.stop()
        print("Done.")

if __name__ == "__main__":
    main()
