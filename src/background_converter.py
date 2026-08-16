from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    from .models import Timeline
except ImportError:  # pragma: no cover
    from src.models import Timeline



@dataclass
class BackgroundKeyframe:
    frame: int
    timestamp: float
    path: str
    static: Optional[bool] = None
    source: str = "transition"


@dataclass
class BackgroundConversionResult:
    keyframes: List[BackgroundKeyframe] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def _parse_background(value: Any) -> Tuple[Optional[str], Optional[bool]]:
    if not value:
        return None, None
    if isinstance(value, str):
        return value, None
    if isinstance(value, (list, tuple)) and value:
        path = value[0] if isinstance(value[0], str) else None
        meta = value[1] if len(value) > 1 and isinstance(value[1], dict) else {}
        static = meta.get("static") if isinstance(meta, dict) else None
        return path, static if isinstance(static, bool) else None
    if isinstance(value, dict):
        path = value.get("path") or value.get("file")
        static = value.get("static")
        return path if isinstance(path, str) else None, static if isinstance(static, bool) else None
    return None, None


def convert_backgrounds(parsed: dict, timeline: Timeline) -> BackgroundConversionResult:
    res = BackgroundConversionResult()
    candidates: List[BackgroundKeyframe] = []

    initial = parsed.get("initial_data") or {}
    path, static = _parse_background(initial.get("background"))
    if path:
        candidates.append(BackgroundKeyframe(0, timeline.frame_to_timestamp(0), path, static, "initial_data"))

    for event in timeline.events:
        if event.source != "transition":
            continue
        path, static = _parse_background(event.data.get("background"))
        if path:
            candidates.append(BackgroundKeyframe(event.frame, event.timestamp, path, static, "transition"))

    last = parsed.get("last_transition") or {}
    last_path, last_static = _parse_background(last.get("background"))
    if last_path and parsed.get("last_beat") is not None:
        candidates.append(BackgroundKeyframe(int(parsed["last_beat"]), timeline.frame_to_timestamp(int(parsed["last_beat"])), last_path, last_static, "last_transition"))

    # Deduplicate consecutive identical states; preserve explicit static flag changes.
    for item in candidates:
        if res.keyframes and res.keyframes[-1].path == item.path and res.keyframes[-1].static == item.static:
            continue
        res.keyframes.append(item)

    if not res.keyframes:
        res.warnings.append("No background states found.")
    return res
