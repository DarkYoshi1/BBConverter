from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

try:
    from .models import Timeline
except ImportError:  # pragma: no cover
    from src.models import Timeline



@dataclass
class SoundFXTrigger:
    frame: int
    timestamp: float
    filename: str
    source: str


@dataclass
class TransitionSound:
    frame: int
    timestamp: float
    filename: str
    source: str = "transition_sound"


@dataclass
class SoundFXResult:
    triggers: List[SoundFXTrigger] = field(default_factory=list)
    transition_sounds: List[TransitionSound] = field(default_factory=list)
    climax_sounds: List[SoundFXTrigger] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    unresolved_last_transition: List[dict] = field(default_factory=list)


def convert_sound_fx(parsed: dict, timeline: Optional[Timeline] = None) -> SoundFXResult:
    """Convert one-shot transition/climax audio.

    Legacy `sound_fx` is handled separately by sound_loop_converter. This
    converter therefore never duplicates it as a one-shot event.
    """
    timeline = timeline or Timeline(float(parsed["bpm"]), float(parsed["note_offset"]), parsed.get("last_beat"), [])
    res = SoundFXResult()

    for frame, transition in sorted((parsed.get("transitions") or {}).items()):
        if not isinstance(transition, dict):
            continue
        frame = int(frame)
        filename = transition.get("transition_sound")
        if isinstance(filename, str) and filename.strip():
            res.transition_sounds.append(
                TransitionSound(frame, timeline.frame_to_timestamp(frame), filename, "transition")
            )
        # Some Legacy charts use a generic sound_fx trigger field as a one-shot.
        trigger = transition.get("sound_fx_trigger")
        if isinstance(trigger, str) and trigger.strip():
            res.triggers.append(SoundFXTrigger(frame, timeline.frame_to_timestamp(frame), trigger, "sound_fx_trigger"))

    last = parsed.get("last_transition") or {}
    final_frame = timeline.final_frame()
    if final_frame is not None:
        filename = last.get("transition_sound")
        if isinstance(filename, str) and filename.strip():
            res.transition_sounds.append(
                TransitionSound(final_frame, timeline.frame_to_timestamp(final_frame), filename, "last_transition")
            )
        filename = last.get("climax_sound")
        if isinstance(filename, str) and filename.strip():
            res.climax_sounds.append(
                SoundFXTrigger(final_frame, timeline.frame_to_timestamp(final_frame), filename, "climax_sound")
            )
        trigger = last.get("sound_fx_trigger")
        if isinstance(trigger, str) and trigger.strip():
            res.triggers.append(SoundFXTrigger(final_frame, timeline.frame_to_timestamp(final_frame), trigger, "last_transition"))

    # Exact duplicates can happen when a chart repeats the same event object.
    unique = {}
    for item in [*res.transition_sounds, *res.climax_sounds, *res.triggers]:
        unique[(type(item).__name__, item.frame, item.filename, item.source)] = item
    res.transition_sounds = [x for x in unique.values() if isinstance(x, TransitionSound)]
    res.climax_sounds = [x for x in unique.values() if isinstance(x, SoundFXTrigger) and x.source == "climax_sound"]
    res.triggers = [x for x in unique.values() if isinstance(x, SoundFXTrigger) and x.source != "climax_sound"]
    res.transition_sounds.sort(key=lambda x: x.frame)
    res.climax_sounds.sort(key=lambda x: x.frame)
    res.triggers.sort(key=lambda x: x.frame)

    if not res.transition_sounds and not res.climax_sounds and not res.triggers:
        res.warnings.append("No one-shot transition/climax audio events found.")
    return res


def check_assets(result: SoundFXResult, assets_dir: Optional[str]) -> None:
    if not assets_dir:
        result.warnings.append("No --assets-dir provided: skipping sound asset checks.")
        return
    from .asset_resolver import resolve_asset
    if not os.path.isdir(assets_dir):
        result.errors.append(f"--assets-dir '{assets_dir}' does not exist or is not a directory.")
        return
    checked: set[str] = set()
    for trigger in [*result.triggers, *result.transition_sounds, *result.climax_sounds]:
        if trigger.filename in checked:
            continue
        checked.add(trigger.filename)
        if resolve_asset(trigger.filename, assets_dir, asset_kind="sound") is None:
            result.warnings.append(f"Missing sound asset: {trigger.filename}")
