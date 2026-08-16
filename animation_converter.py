from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from models import Timeline

DEFAULT_SHEET_H = 3
DEFAULT_SHEET_V = 2
DEFAULT_SHEET_TOTAL = 6
SHEET_DATA_OVERRIDES: Dict[str, dict] = {}

_OVERRIDES_PATH = os.path.join(os.path.dirname(__file__), "sheet_overrides.json")
try:
    with open(_OVERRIDES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        SHEET_DATA_OVERRIDES.update(data)
except FileNotFoundError:
    pass
except Exception:
    pass


def resolve_sheet_data(animation: str) -> dict:
    override = SHEET_DATA_OVERRIDES.get(animation)
    if override is not None:
        return dict(override)
    return {"h": DEFAULT_SHEET_H, "v": DEFAULT_SHEET_V, "total": DEFAULT_SHEET_TOTAL}


@dataclass
class AnimationChange:
    frame: int
    animation: str
    source: str
    looping: Optional[bool] = None


@dataclass
class Keyframe:
    frame: int
    timestamp: float
    animation: str
    sheet_data: dict
    looping: Optional[bool] = None


@dataclass
class AnimationConversionResult:
    keyframes: List[Keyframe] = field(default_factory=list)
    changes: List[AnimationChange] = field(default_factory=list)
    skipped_duplicates: List[AnimationChange] = field(default_factory=list)
    collisions: List[dict] = field(default_factory=list)
    missing_assets: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    last_transition_info: Optional[dict] = None


def _build_raw_changes(parsed: dict) -> Dict[int, List[AnimationChange]]:
    by_frame: Dict[int, List[AnimationChange]] = {}
    initial = parsed.get("initial_data") or {}
    animation = initial.get("animation")
    if animation:
        by_frame.setdefault(0, []).append(AnimationChange(0, animation, "initial_data", initial.get("looping")))

    for frame, t in sorted((parsed.get("transitions") or {}).items()):
        if not isinstance(t, dict):
            continue
        animation = t.get("animation")
        if animation:
            by_frame.setdefault(int(frame), []).append(
                AnimationChange(int(frame), animation, "transition", t.get("looping"))
            )
    return by_frame


def build_animation_changes(parsed: dict) -> AnimationConversionResult:
    res = AnimationConversionResult()
    active: Optional[str] = None
    active_looping: Optional[bool] = None
    for frame, group in sorted(_build_raw_changes(parsed).items()):
        # A transition at the same frame overrides initial_data only if it is the only state source.
        chosen = group[0]
        if len({g.animation for g in group}) > 1:
            res.collisions.append({"frame": frame, "conflicting": group})
            res.warnings.append(
                f"frame={frame}: conflicting animation states; using {chosen.source}->{chosen.animation} as deterministic placeholder."
            )
        if chosen.animation == active and chosen.looping == active_looping:
            res.skipped_duplicates.append(chosen)
            continue
        res.changes.append(chosen)
        active = chosen.animation
        active_looping = chosen.looping

    if not res.changes:
        res.errors.append("No animation changes found.")

    return res


def generate_keyframes(result: AnimationConversionResult, timeline: Timeline) -> None:
    for change in result.changes:
        result.keyframes.append(
            Keyframe(
                frame=change.frame,
                timestamp=timeline.frame_to_timestamp(change.frame),
                animation=change.animation,
                sheet_data=resolve_sheet_data(change.animation),
                looping=change.looping,
            )
        )


def check_assets(result: AnimationConversionResult, assets_dir: Optional[str]) -> None:
    if not assets_dir:
        result.warnings.append("No --assets-dir provided: skipping animation asset checks.")
        return
    from asset_resolver import resolve_asset
    if not os.path.isdir(assets_dir):
        result.errors.append(f"--assets-dir '{assets_dir}' does not exist or is not a directory.")
        return
    missing: set[str] = set()
    for kf in result.keyframes:
        if resolve_asset(kf.animation, assets_dir, asset_kind="animation") is None:
            missing.add(kf.animation)
    result.missing_assets = sorted(missing, key=str.lower)
    result.warnings.extend(f"Missing animation asset: {name}" for name in result.missing_assets)


def convert_animations(parsed: dict, timeline: Optional[Timeline] = None, assets_dir: Optional[str] = None,
                       include_last_transition: bool = True) -> AnimationConversionResult:
    timeline = timeline or Timeline(float(parsed["bpm"]), float(parsed["note_offset"]), parsed.get("last_beat"), [])
    res = build_animation_changes(parsed)
    generate_keyframes(res, timeline)

    last = parsed.get("last_transition") or {}
    if last.get("animation"):
        final_frame = timeline.final_frame()
        res.last_transition_info = {
            "animation": last.get("animation"),
            "looping": last.get("looping"),
            "frame": final_frame,
            "timestamp": timeline.frame_to_timestamp(final_frame) if final_frame is not None else None,
        }
    if include_last_transition and last.get("animation") and timeline.final_frame() is not None:
        frame = int(timeline.final_frame())
        # Legacy defines last_transition as the end-of-level transition.
        candidate = Keyframe(frame, timeline.frame_to_timestamp(frame), last["animation"], resolve_sheet_data(last["animation"]), last.get("looping"))
        duplicate = any(k.frame == candidate.frame and k.animation == candidate.animation and k.looping == candidate.looping for k in res.keyframes)
        if not duplicate:
            res.keyframes.append(candidate)
    check_assets(res, assets_dir)
    return res
