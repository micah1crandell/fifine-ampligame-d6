"""Fifine AmpliGame Stream Deck - Pure Standalone Python USB Driver & LCD Engine

Directly communicates with the 15-key Fifine AmpliGame / HotSpot StreamDock D6/D6-Pro
over USB with zero manufacturer software or background daemons required.
"""

from .deck import FifineDeck
from .events import KeyEvent
from .driver import FifineDriver
from .companion import CompanionBridge
from .display import (
    FifineDisplay,
    generate_key_tile,
    generate_solid_color_jpeg,
    convert_image_to_jpeg,
    rotate_buffer_180,
    clean_baseline_jpeg,
    DEFAULT_KEY_WIDTH,
    DEFAULT_KEY_HEIGHT,
    PACKET_SIZE,
    CMD_ULEND,
    CMD_STP,
    CMD_DIS,
    CMD_CONNECT,
    CMD_CLE,
    CMD_SLP,
    CMD_BLEF,
    CMD_MOD,
    CMD_PIXMAPEND,
    logical_to_hardware_slot,
)

__version__ = "2.1.0"
__all__ = [
    "FifineDeck",
    "KeyEvent",
    "FifineDriver",
    "FifineDisplay",
    "CompanionBridge",
    "generate_key_tile",
    "generate_solid_color_jpeg",
    "convert_image_to_jpeg",
    "rotate_buffer_180",
    "clean_baseline_jpeg",
    "logical_to_hardware_slot",
    "DEFAULT_KEY_WIDTH",
    "DEFAULT_KEY_HEIGHT",
    "PACKET_SIZE",
    "CMD_ULEND",
    "CMD_STP",
    "CMD_DIS",
    "CMD_CONNECT",
    "CMD_CLE",
    "CMD_SLP",
    "CMD_BLEF",
    "CMD_MOD",
    "CMD_PIXMAPEND",
]
