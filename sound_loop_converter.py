from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, List, Optional

from models import Timeline


@dataclass
class SoundLoop:
    start_frame: int
    start_timestamp: float
    sound: Any
    looping: bool = True
    source: str = "initial_data"


@dataclass
class SoundLoopResult:
    loops: List[SoundLoop] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def _normalize_sound_value(value: Any) -> Optional[Any]:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        paths = [str(item).strip() for item in value if str(item).strip()]
        return paths if paths else None
    if isinstance(value, str):
        value = value.strip()
        return value if value else None
    return None


def convert_sound_loops(parsed: dict, timeline: Optional[Timeline] = None) -> SoundLoopResult:
    """Legacy sound_fx is explicitly the loop sound effect.

    The state continues until the next transition that changes sound_fx.
    Empty sound_fx does not generate an artificial stop entry; Release can
    represent the next active state as the boundary.
    """
    timeline = timeline or Timeline(float(parsed["bpm"]), float(parsed["note_offset"]), parsed.get("last_beat"), [])
    res = SoundLoopResult()
    states = []

    initial = parsed.get("initial_data") or {}
    sound = _normalize_sound_value(initial.get("sound_fx"))
    states.append((0, sound, "initial_data"))

    for frame, t in sorted((parsed.get("transitions") or {}).items()):
        if not isinstance(t, dict):
            continue
        # A transition without sound_fx means "no change" for this subsystem;
        # an explicit empty string means "stop the current loop".
        if "sound_fx" not in t:
            continue
        states.append((int(frame), _normalize_sound_value(t.get("sound_fx")), "transition"))

    last = parsed.get("last_transition") or {}
    if isinstance(last, dict) and "sound_fx" in last and timeline.final_frame() is not None:
        states.append((int(timeline.final_frame()), _normalize_sound_value(last.get("sound_fx")), "last_transition"))

    # Keep every change in the loop state, including explicit empty states,
    # because the Release writer needs a deterministic stop boundary.
    last_sound = object()
    for frame, sound, source in states:
        if sound == last_sound:
            continue
        if sound is not None:
            res.loops.append(SoundLoop(frame, timeline.frame_to_timestamp(frame), sound, True, source))
        last_sound = sound

    if states and states[-1][1] is None and res.loops:
        # The state is intentionally stopped by the empty Legacy value.
        res.warnings.append("Sound loop state contains an explicit stop; Release keyframes will include the state change boundary.")
    if not res.loops:
        res.warnings.append("No Legacy sound_fx loop states found.")
    return res


def check_assets(result: SoundLoopResult, assets_dir: Optional[str]) -> None:
    if not assets_dir:
        result.warnings.append("No --assets-dir provided: skipping sound loop asset checks.")
        return
    from asset_resolver import resolve_asset
    if not os.path.isdir(assets_dir):
        result.errors.append(f"--assets-dir '{assets_dir}' does not exist or is not a directory.")
        return
    for loop in result.loops:
        sounds = loop.sound if isinstance(loop.sound, list) else [loop.sound]
        missing = set()
        for sound in sounds:
            if resolve_asset(sound, assets_dir, asset_kind="sound") is None:
                missing.add(sound)
        for sound in sorted(missing, key=str.lower):
            message = f"Missing sound loop asset: {sound}"
            if message not in result.warnings:
                result.warnings.append(message)
