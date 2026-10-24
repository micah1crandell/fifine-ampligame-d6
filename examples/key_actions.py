#!/usr/bin/env python3
"""Example: Trigger custom Python actions, system commands, or hotkeys."""

import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fifine import FifineDeck, KeyEvent

def mute_system_audio():
    """Toggle macOS system mute."""
    script = 'set volume output muted not (output muted of (get volume settings))'
    subprocess.run(["osascript", "-e", script])

def trigger_key_1():
    print("Action for Key 1: Toggling System Mute...")
    mute_system_audio()

def trigger_key_2():
    print("Action for Key 2: Opening GitHub...")
    subprocess.run(["open", "https://github.com"])

def main():
    deck = FifineDeck()

    @deck.on_event
    def handle_event(ev: KeyEvent):
        if not ev.is_press:
            return

        if ev.key == 1:
            trigger_key_1()
        elif ev.key == 2:
            trigger_key_2()
        else:
            print(f"Key {ev.key} pressed (No action mapped yet).")

    print("Running Custom Action Runner on Fifine Deck directly over USB...")
    deck.start(blocking=True)

if __name__ == "__main__":
    main()
