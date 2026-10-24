#!/usr/bin/env python3
"""Bitfocus Companion Satellite Bridge Example for Fifine AmpliGame D6.

Enables the Fifine AmpliGame Stream Deck to function as a native 15-key
control surface in Bitfocus Companion over TCP (port 16622).

Usage:
    python3 examples/companion_satellite.py [--host 127.0.0.1] [--port 16622]
"""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fifine import FifineDeck
from fifine.companion import CompanionBridge


def main():
    parser = argparse.ArgumentParser(description="Bridge Fifine D6 to Bitfocus Companion Satellite API")
    parser.add_argument("--host", default="127.0.0.1", help="Bitfocus Companion host IP (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=16622, help="Companion Satellite TCP port (default: 16622)")
    parser.add_argument("--device-id", default="fifine-d6-01", help="Device ID string (default: fifine-d6-01)")
    parser.add_argument("--brightness", "-b", type=int, default=100, help="Initial brightness 0..100 (default: 100)")
    parser.add_argument("--zoom", "-z", type=float, default=1.18, help="Scaling zoom factor to fill keycaps edge-to-edge (default: 1.18)")
    parser.add_argument("--size", "-s", type=int, default=100, help="Bitmap canvas size requested from Companion (default: 100)")
    args = parser.parse_args()

    print("=" * 65)
    print("   FIFINE AMPLIGAME -> BITFOCUS COMPANION SATELLITE BRIDGE")
    print(f"   Connecting to Companion at: {args.host}:{args.port}")
    print(f"   Device ID:                  {args.device_id}")
    print(f"   Display:                    15 Keys, {args.size}x{args.size} native, zoom: {args.zoom}x")
    print("   Press Ctrl+C to exit.")
    print("=" * 65)

    deck = FifineDeck(auto_wake=True, default_brightness=args.brightness)
    bridge = CompanionBridge(
        deck=deck,
        host=args.host,
        port=args.port,
        device_id=args.device_id,
        product_name="Fifine AmpliGame D6",
        bitmap_size=args.size,
        zoom=args.zoom,
    )

    try:
        bridge.start(blocking=True)
    except KeyboardInterrupt:
        print("\nExiting bridge...")
    finally:
        bridge.stop()


if __name__ == "__main__":
    main()
