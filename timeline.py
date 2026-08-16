from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from models import Timeline, TimelineEvent

# Legacy note_type -> Release input_type
LEGACY_NOTE_TYPE_TO_INPUT_TYPE = {
    0: None,
    1: 0,
    2: 1,
    3: 2,
}

SPAWN_INTERVAL = {
    0: 4,
    1: 2,
    2: 1,
}


@dataclass(frozen=True)
class Change:
    frame: int
    input_type: Optional[int]
    source: str


@dataclass(frozen=True)
class Collision:
    frame: int
    conflicting: List[Change]


def build_timeline(parsed: dict) -> Timeline:
    """Build the single canonical timeline used by every converter."""
    bpm = float(parsed["bpm"])
    note_offset = float(parsed["note_offset"])
    last_beat = parsed.get("last_beat")
    if isinstance(last_beat, (list, tuple)) and last_beat:
        last_beat = last_beat[0]
    if last_beat is not None:
        try:
            last_beat = int(last_beat)
        except (TypeError, ValueError):
            last_beat = None

    warnings: List[str] = []
    if last_beat is None:
        warnings.append("Legacy chart has no last_beat; converters will use the last known timeline frame as a fallback boundary.")

    # Build the Timeline first (no events yet) so every event's timestamp is
    # computed through Timeline.frame_to_timestamp() — the single, centralized
    # formula (per README section 2/5). Previously this loop recomputed
    # `frame * (30/bpm) - note_offset` inline, duplicating the formula AND
    # skipping the negative-timestamp clamp that frame_to_timestamp() applies,
    # which is what let a positive note_offset produce broken negative
    # timestamps for the earliest events.
    timeline = Timeline(bpm=bpm, note_offset=note_offset, last_beat=last_beat, events=[], warnings=warnings)

    events: List[TimelineEvent] = []
    initial = parsed.get("initial_data") or {}
    if initial:
        events.append(TimelineEvent(0, timeline.frame_to_timestamp(0), dict(initial), "initial_data"))

    for frame, data in sorted((parsed.get("transitions") or {}).items()):
        frame = int(frame)
        events.append(
            TimelineEvent(
                frame=frame,
                timestamp=timeline.frame_to_timestamp(frame),
                data=dict(data) if isinstance(data, dict) else {},
                source="transition",
            )
        )

    events.sort(key=lambda e: (e.frame, 0 if e.source == "initial_data" else 1))
    timeline.events = events
    return timeline


def build_changes(parsed: dict) -> Tuple[List[Change], List[Collision]]:
    """Build the Legacy note-state intervals without recalculating time."""
    explicit: List[Change] = []

    for frame in parsed.get("half_spawn", []):
        explicit.append(Change(int(frame), 0, "half_spawn"))
    for frame in parsed.get("quarter_spawn", []):
        explicit.append(Change(int(frame), 1, "quarter_spawn"))
    for frame in parsed.get("eighth_spawn", []):
        explicit.append(Change(int(frame), 2, "eighth_spawn"))
    for frame in parsed.get("no_spawn", []):
        explicit.append(Change(int(frame), None, "no_spawn"))

    by_frame: Dict[int, List[Change]] = {}
    for c in explicit:
        by_frame.setdefault(c.frame, []).append(c)

    collisions: List[Collision] = []
    changes: List[Change] = []
    for frame in sorted(by_frame):
        group = by_frame[frame]
        distinct = {c.input_type for c in group}
        if len(distinct) > 1:
            collisions.append(Collision(frame, list(group)))
            # Invalid Legacy charts can put multiple mutually-exclusive note
            # states on one frame. Preserve deterministic output, but keep the
            # collision as a hard conversion error at the orchestrator level.
            # The precedence is explicit instead of depending on input order:
            # no_spawn > eighth > quarter > half.
            precedence = {None: 4, 2: 3, 1: 2, 0: 1}
            chosen = max(group, key=lambda c: precedence[c.input_type])
            changes.append(chosen)
        else:
            changes.append(group[0])

    if 0 not in by_frame:
        initial_type = LEGACY_NOTE_TYPE_TO_INPUT_TYPE.get(int(parsed.get("note_type", 0)))
        changes.append(Change(0, initial_type, "initial_data"))

    changes.sort(key=lambda c: c.frame)
    return changes, collisions
