#!/usr/bin/env python3
"""Test script: Push full custom 15-key display grid to Fifine D6."""

import sys
import time
import struct
import threading
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fifine.driver import FifineDriver
from fifine.display import (
    generate_key_tile,
    make_image_header,
    slice_image_chunks,
    make_brightness_packet,
    CMD_CONNECT,
    CMD_BLEF,
    CMD_MOD,
    CMD_DIS,
    CMD_CLE,
    CMD_STP,
    CMD_PIXMAPEND,
    PACKET_SIZE,
)

def main():
    print("Connecting to Fifine D6...")
    driver = FifineDriver()
    driver.start()

    time.sleep(0.5)
    if not driver.is_connected:
        print("Error: Fifine D6 not connected!")
        driver.stop()
        return

    fw = driver.get_firmware_version()
    print(f"Connected! Firmware: {fw}")

    # Helper to send single report
    def send(pkt, delay=0.005):
        driver.send_report(pkt, blocking=True)
        if delay > 0:
            time.sleep(delay)

    print("\n--- 1. Initializing Display Controller (CONNECT, BLEF, MOD, DIS, LIG, CLE, STP) ---")
    send(CMD_CONNECT, delay=0.01)
    send(CMD_BLEF, delay=0.01)
    send(CMD_MOD, delay=0.01)
    send(CMD_DIS, delay=0.01)
    send(make_brightness_packet(100), delay=0.01)
    send(CMD_CLE, delay=0.01)
    send(CMD_STP, delay=0.02)

    colors = [
        ("#ef4444", "RED"),     ("#f97316", "ORANGE"), ("#eab308", "YELLOW"), ("#22c55e", "GREEN"),  ("#06b6d4", "CYAN"),
        ("#3b82f6", "BLUE"),    ("#6366f1", "INDIGO"), ("#a855f7", "PURPLE"), ("#ec4899", "PINK"),   ("#14b8a6", "TEAL"),
        ("#84cc16", "LIME"),    ("#0ea5e9", "SKY"),    ("#8b5cf6", "VIOLET"), ("#f43f5e", "ROSE"),   ("#10b981", "EMERALD"),
    ]

    print("\n--- 2. Streaming All 15 LCD Keys ---")
    for key_id in range(1, 16):
        bg, name = colors[key_id - 1]
        print(f"  Rendering Key {key_id:2d}: {name} ({bg})...")
        jpeg = generate_key_tile(
            title=name,
            number=key_id,
            bg_color=bg,
            border_color="#ffffff",
            text_color="#ffffff",
            width=100,
            height=100
        )
        # Send BAT header
        send(make_image_header(key_id, len(jpeg)), delay=0.005)
        # Send Chunks
        for ch in slice_image_chunks(jpeg):
            send(ch, delay=0.005)
        # Commit Key
        send(CMD_STP, delay=0.005)

    print("\n--- 3. Master Framebuffer Commit (PIXMAPEND + STP) ---")
    send(CMD_PIXMAPEND, delay=0.01)
    send(CMD_STP, delay=0.02)

    print("\nDisplay update complete!")
    print("Keeping connection open for 3 seconds...")
    time.sleep(3.0)

    driver.stop()
    print("Done!")

if __name__ == "__main__":
    main()
