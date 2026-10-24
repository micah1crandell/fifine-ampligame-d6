#!/usr/bin/env python3
"""Minimal standalone example: Listen for Fifine Stream Deck button presses directly over USB."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fifine import FifineDeck

def main():
    deck = FifineDeck()

    @deck.on_press
    def handle_press(key: int):
        print(f"[PRESS] Button {key} PRESSED")

    @deck.on_release
    def handle_release(key: int):
        print(f"[RELEASE] Button {key} released")

    print("Listening for Fifine button presses directly over USB (Press Ctrl+C to quit)...")
    deck.start(blocking=True)

if __name__ == "__main__":
    main()
