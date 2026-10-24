#!/usr/bin/env python3
"""LCD Framebuffer Engine Demo for Fifine AmpliGame Stream Deck (D6/D6-Pro).

Demonstrates:
- Cold-boot master display initialization
- Custom styled tiles (colors, text, numbers)
- Dynamic key updates on button presses (interactive visual feedback)
- Backlight brightness control
"""

import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fifine import FifineDeck, KeyEvent, generate_key_tile


def main():
    print("Initializing Fifine Stream Deck with custom LCD Framebuffer...")
    deck = FifineDeck(auto_wake=True, default_brightness=100)

    # Define color themes for different keys
    key_themes = {
        1: ("MUTE", "Audio", "#ef4444", "#991b1b"),
        2: ("PLAY", "Media", "#3b82f6", "#1d4ed8"),
        3: ("VOL+", "System", "#64748b", "#334155"),
        4: ("VOL-", "System", "#64748b", "#334155"),
        5: ("SLEEP", "Power", "#f97316", "#c2410c"),
        6: ("OBS", "Stream", "#8b5cf6", "#6d28d9"),
        7: ("MIC", "Input", "#06b6d4", "#0e7490"),
        8: ("STAR", "Action", "#eab308", "#a16207"),
        9: ("CHAT", "App", "#10b981", "#047857"),
        10: ("CLIP", "Rec", "#ec4899", "#be185d"),
        11: ("CAM", "Video", "#14b8a6", "#0f766e"),
        12: ("BROWSER", "Web", "#6366f1", "#4338ca"),
        13: ("TERM", "Shell", "#0284c7", "#0369a1"),
        14: ("DISCORD", "Voice", "#5865f2", "#4752c4"),
        15: ("LOCK", "Sec", "#64748b", "#334155"),
    }

    # Pre-render tiles for normal and pressed states
    normal_tiles = {}
    pressed_tiles = {}

    for k, (title, sub, bg, bdr) in key_themes.items():
        normal_tiles[k] = generate_key_tile(
            title=title,
            subtitle=sub,
            bg_color=bg,
            border_color=bdr,
            text_color="#ffffff",
        )
        pressed_tiles[k] = generate_key_tile(
            title=title,
            subtitle="ACTIVE",
            bg_color="#ffffff",
            border_color="#ffffff",
            text_color="#000000",
        )
        deck.set_key_image(k, normal_tiles[k])

    # Interactive key press feedback
    @deck.on_event
    def on_event(ev: KeyEvent):
        if ev.is_press:
            print(f"[PRESS] Button {ev.key} pressed. Highlighting key LCD...")
            deck.set_key_image(ev.key, pressed_tiles.get(ev.key, normal_tiles.get(ev.key)))
        elif ev.is_release:
            print(f"   Button {ev.key} released. Restoring LCD tile.")
            deck.set_key_image(ev.key, normal_tiles.get(ev.key))

    print("\n" + "=" * 60)
    print("  FIFINE LCD FRAMEBUFFER ENGINE ACTIVE")
    print("  Tiles uploaded across all 15 LCD keys.")
    print("  Press buttons on the hardware to see interactive LCD updates!")
    print("  Press Ctrl+C to exit.")
    print("=" * 60 + "\n")

    deck.start(blocking=True)


if __name__ == "__main__":
    main()
