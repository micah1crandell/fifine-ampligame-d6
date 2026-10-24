from dataclasses import dataclass
from typing import Optional
import time

@dataclass
class KeyEvent:
    """Represents a button press or release event on the Fifine AmpliGame deck."""
    key: int               # Button number (1..15, left-to-right, top-to-bottom)
    state: str             # "down" (pressed) or "up" (released)
    row: int               # Grid row index (0..2)
    col: int               # Grid column index (0..4)
    timestamp: float = 0.0 # Unix timestamp of event
    raw_context: Optional[str] = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()

    @property
    def is_press(self) -> bool:
        return self.state == "down"

    @property
    def is_release(self) -> bool:
        return self.state == "up"

    def __str__(self) -> str:
        arrow = "▼" if self.is_press else "▲"
        return f"[Key {self.key:2d}] {arrow} {self.state.upper():4s} (Row {self.row}, Col {self.col})"
