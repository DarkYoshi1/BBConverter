from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    from .models import Timeline
except ImportError:  # pragma: no cover
    from src.models import Timeline

try:
    from .timeline import Change, SPAWN_INTERVAL
except ImportError:  # pragma: no cover
    from src.timeline import Change, SPAWN_INTERVAL



@dataclass
class Note:
    legacy_frame: int
    input_type: int
    timestamp: float
    note_modifier: int = 0
    trigger_voice: bool = False


def _as_int(value: Any, default: Optional[int]) -> Optional[int]:
    if value is None:
        return default
    if isinstance(value, (list, tuple)):
        if not value:
            return default
        value = value[0]
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _is_valid_voice_bank(bank: Any) -> bool:
    if not isinstance(bank, dict):
        return False
    if not bank:
        return False
    if not any(key in bank for key in ("voice_paths", "name", "path", "interval")):
        return False
    return True


def _voice_bank_state_at_frame(parsed: Dict[str, Any], frame: int) -> tuple[Optional[int], Optional[int]]:
    if not parsed:
        return None, None

    active_start: Optional[int] = None
    interval: Optional[int] = None

    initial = parsed.get("initial_data") or {}
    if isinstance(initial, dict):
        bank = initial.get("voice_bank")
        if isinstance(bank, list):
            for entry in bank:
                if _is_valid_voice_bank(entry):
                    active_start = 0
                    interval = _as_int(entry.get("interval"), None)
                    break
        elif _is_valid_voice_bank(bank):
            active_start = 0
            interval = _as_int(bank.get("interval"), None)

    for event_frame, event in sorted((parsed.get("transitions") or {}).items()):
        if int(event_frame) > frame:
            break
        if not isinstance(event, dict):
            continue
        bank = event.get("voice_bank")
        if isinstance(bank, list):
            valid = next((item for item in bank if _is_valid_voice_bank(item)), None)
            if valid is not None:
                active_start = int(event_frame)
                interval = _as_int(valid.get("interval"), None)
                continue
            active_start = None
            interval = None
        elif _is_valid_voice_bank(bank):
            active_start = int(event_frame)
            interval = _as_int(bank.get("interval"), None)
        else:
            active_start = None
            interval = None

    last = parsed.get("last_transition") or {}
    if isinstance(last, dict):
        last_bank = last.get("voice_bank")
        last_beat = _as_int(parsed.get("last_beat"), None)
        if last_beat is not None and frame >= last_beat:
            if isinstance(last_bank, list):
                last_valid = next((item for item in last_bank if _is_valid_voice_bank(item)), None)
                if last_valid is not None:
                    active_start = int(last_beat)
                    interval = _as_int(last_valid.get("interval"), None)
            elif _is_valid_voice_bank(last_bank):
                active_start = int(last_beat)
                interval = _as_int(last_bank.get("interval"), None)

    return active_start, interval


def _voice_bank_active_at_frame(parsed: Dict[str, Any], frame: int) -> bool:
    start_frame, interval = _voice_bank_state_at_frame(parsed, frame)
    if start_frame is None:
        return False
    if interval is None:
        return False
    if interval <= 0:
        return False
    return (frame - start_frame) % interval == 0


def generate_notes(changes: List[Change], timeline: Timeline, parsed: Optional[dict] = None) -> List[Note]:
    """Expand note states into explicit Release notes."""
    notes: List[Note] = []
    end_frame = timeline.final_frame()
    if end_frame is None:
        return notes

    parsed = parsed or {}

    for i, change in enumerate(changes):
        if change.input_type is None:
            continue
        next_boundary = changes[i + 1].frame if i + 1 < len(changes) else end_frame
        if next_boundary is None or next_boundary <= change.frame:
            continue
            continue

        interval = SPAWN_INTERVAL[change.input_type]
        frame = change.frame
        while frame < next_boundary and frame < end_frame:
            notes.append(
                Note(
                    legacy_frame=frame,
                    input_type=change.input_type,
                    timestamp=timeline.frame_to_timestamp(frame),
                    note_modifier=0,
                    trigger_voice=_voice_bank_active_at_frame(parsed, frame),
                )
            )
            frame += interval

    notes.sort(key=lambda n: (n.timestamp, n.legacy_frame, n.input_type))
    return notes
