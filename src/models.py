from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class TimelineEvent:
    frame: int
    timestamp: float
    data: Dict[str, Any]
    source: str = "transition"


@dataclass
class Timeline:
    bpm: float
    note_offset: float
    last_beat: Optional[int]
    events: List[TimelineEvent] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def seconds_per_frame(self) -> float:
        return 30.0 / float(self.bpm)

    def frame_to_timestamp(self, frame: int) -> float:
        """Convert a Legacy frame to an absolute Release timestamp.

        A positive Legacy `note_offset` pulls early frames (frame 0, and
        anything before `note_offset` seconds into the song) into negative
        time. Release's engine does not expect negative timestamps in
        notes.cfg/keyframes.cfg — converted mods with them failed to run
        correctly. We clamp at 0.0 (the note/event simply fires at the very
        start of the level instead of "before" it) and record a warning so
        this is visible rather than silent.
        """
        raw = float(frame) * self.seconds_per_frame - float(self.note_offset)
        if raw < 0.0:
            msg = f"frame={frame}: computed timestamp {raw:.6f}s was negative (note_offset={self.note_offset}); clamped to 0.0."
            if msg not in self.warnings:
                self.warnings.append(msg)
            return 0.0
        return raw

    def timestamp_to_frame(self, timestamp: float) -> float:
        return (float(timestamp) + float(self.note_offset)) / self.seconds_per_frame

    def final_frame(self) -> Optional[int]:
        if self.last_beat is not None:
            return self.last_beat
        if self.events:
            return max(e.frame for e in self.events)
        return None
