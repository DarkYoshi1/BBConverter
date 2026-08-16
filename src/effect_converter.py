from __future__ import annotations

import fnmatch
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")

try:
    from .models import Timeline
except ImportError:  # pragma: no cover
    from src.models import Timeline



@dataclass
class EffectKey:
    frame: int
    timestamp: float
    effect: str
    duration: Optional[float] = None
    sheet_data: Optional[dict] = None
    source: str = "transition"


@dataclass
class EffectConversionResult:
    keyframes: List[EffectKey] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    unresolved_last_transition: Optional[dict] = None


_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_OVERRIDES_PATH = os.path.join(_PROJECT_ROOT, "config", "effect_overrides.json")
if not os.path.isfile(_OVERRIDES_PATH):
    _OVERRIDES_PATH = os.path.join(_PROJECT_ROOT, "effect_overrides.json")


def _load_overrides() -> Dict[str, dict]:
    try:
        with open(_OVERRIDES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def _save_sheet_override(name: str, sheet_data: dict) -> None:
    """Persist a user-confirmed sprite count so future conversions (of this
    mod or any other one reusing the same effect asset) don't ask again."""
    try:
        current = _load_overrides()
        entry = dict(current.get(name) or {})
        entry["sheet_data"] = sheet_data
        current[name] = entry
        with open(_OVERRIDES_PATH, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, ensure_ascii=False)
        active = _active_overrides()
        active[name] = entry
        if active is not OVERRIDES:
            OVERRIDES[name] = entry
    except Exception:
        # Best-effort: if we can't persist it, the conversion still
        # succeeds with the answer already given for this run.
        pass


OVERRIDES = _load_overrides()


def _active_overrides() -> Dict[str, dict]:
    """Use the currently active override table, including the legacy module alias."""
    module = sys.modules.get("effect_converter")
    if module is not None and module is not sys.modules.get(__name__):
        legacy_overrides = getattr(module, "OVERRIDES", None)
        if isinstance(legacy_overrides, dict):
            return legacy_overrides
    return OVERRIDES


def _get_effect_override(name: str) -> dict:
    """Return the most specific exact/pattern override for an effect asset."""
    override_store = _active_overrides()
    direct = override_store.get(name)
    if isinstance(direct, dict):
        return direct
    lowered = str(name).lower()
    candidates = []
    for pattern, value in override_store.items():
        if not isinstance(value, dict) or not any(ch in pattern for ch in "*?["):
            continue
        if fnmatch.fnmatch(lowered, pattern.lower()):
            specificity = sum(ch not in "*?[" for ch in pattern)
            candidates.append((specificity, pattern, value))
    if candidates:
        candidates.sort(key=lambda item: (-item[0], item[1].lower()))
        return candidates[0][2]
    return {}


def _open_sprite_for_preview(path: str) -> None:
    """Best-effort preview of a sprite sheet before asking for its frame count."""
    try:
        from PIL import Image
        from PIL import ImageShow
        image = Image.open(path)
        image.load()
        # Keep previews responsive while still showing the full sheet.
        max_side = 1200
        scale = min(1.0, max_side / max(image.width, image.height))
        if scale < 1.0:
            preview = image.copy()
            preview.thumbnail((max_side, max_side))
        else:
            preview = image
        ImageShow.show(preview, title=f"Beat Banger SFX sprite: {path}")
        return
    except Exception:
        pass

    # Fallback for systems where PIL has no registered image viewer.
    import subprocess
    import sys
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


def _infer_sheet_grid(width: int, height: int, total: int) -> tuple[int, int]:
    """Infer columns/rows from image aspect ratio and a user-supplied frame count."""
    if total <= 0:
        raise ValueError("Sprite count must be greater than zero")
    aspect = width / height if height else 1.0
    candidates = []
    for cols in range(1, int(total ** 0.5) + 1):
        if total % cols:
            continue
        rows = total // cols
        for c, r in ((cols, rows), (rows, cols)):
            grid_aspect = c / r
            candidates.append((abs(grid_aspect - aspect), abs(c - r), -c, c, r))
    if not candidates:
        return total, 1
    candidates.sort()
    _, _, _, columns, rows = candidates[0]
    return columns, rows


def _ask_sheet_data(asset_path: str, cache: Dict[str, dict]) -> Optional[dict]:
    """Preview an image effect and interactively ask for its sprite count."""
    normalized = os.path.abspath(asset_path)
    if normalized in cache:
        return cache[normalized]

    try:
        from PIL import Image
        with Image.open(normalized) as image:
            width, height = image.size
    except Exception as exc:
        print(f"Can't open the spritesheet '{asset_path}': {exc}")
        return None

    _open_sprite_for_preview(normalized)
    print(f"\nSFX sprite: {normalized}")
    print(f"Dimensiones: {width}x{height}")
    while True:
        try:
            raw = input("How many sprites does this SFX have? ").strip()
        except EOFError:
            return None
        try:
            total = int(raw)
            if total < 1:
                raise ValueError
            columns, rows = _infer_sheet_grid(width, height, total)
            data = {"h": columns, "v": rows, "total": total}
            print(f"Using spritesheet: {columns}x{rows} ({total} sprites)")
            cache[normalized] = data
            _save_sheet_override(os.path.basename(normalized), data)
            return data
        except ValueError:
            print("Introduce a number higher than 0.")


def _effect_info(name: str, frame: int, assets_dir: Optional[str], interactive_sheets: bool, sheet_cache: Dict[str, dict]):
    override = _get_effect_override(name)
    duration = override.get("duration")
    frame_durations = override.get("durations")
    if isinstance(frame_durations, dict):
        duration = frame_durations.get(str(frame), frame_durations.get(frame, duration))
    if duration is not None:
        try:
            duration = float(duration)
            if duration <= 0:
                duration = None
        except (TypeError, ValueError):
            duration = None

    sheet_data = override.get("sheet_data")
    if isinstance(sheet_data, dict):
        sheet_data = dict(sheet_data)
    elif interactive_sheets and str(name).lower().endswith(IMAGE_EXTENSIONS) and assets_dir:
        asset_path = os.path.join(assets_dir, name)
        if not os.path.isfile(asset_path):
            from .asset_resolver import resolve_asset
            asset_path = resolve_asset(name, assets_dir, asset_kind="effect") or ""
        if asset_path and os.path.isfile(asset_path):
            sheet_data = _ask_sheet_data(asset_path, sheet_cache)

    # Verified defaults from the Release reference mods we inspected. These
    # are only used when the exact effect has no explicit duration override.
    # Unknown sheet layouts are still left unresolved rather than assigning an
    # arbitrary duration.
    if duration is None and isinstance(sheet_data, dict):
        try:
            total = int(sheet_data.get("total", 0))
        except (TypeError, ValueError):
            total = 0
        if total == 6:
            duration = 0.5
        elif total == 24:
            duration = 4.0

    return duration, sheet_data


def convert_effects(parsed: dict, timeline: Optional[Timeline] = None, assets_dir: Optional[str] = None, interactive_sheets: bool = True) -> EffectConversionResult:
    timeline = timeline or Timeline(float(parsed["bpm"]), float(parsed["note_offset"]), parsed.get("last_beat"), [])
    res = EffectConversionResult()
    candidates = []
    sheet_cache: Dict[str, dict] = {}

    init = parsed.get("initial_data") or {}
    if init.get("effects"):
        res.warnings.append("Legacy initial_data.effects is present; treating it as an event at frame 0.")
        candidates.append((0, init["effects"], "initial_data"))

    for frame, t in sorted((parsed.get("transitions") or {}).items()):
        if isinstance(t, dict) and t.get("effects"):
            candidates.append((int(frame), t["effects"], "transition"))

    last = parsed.get("last_transition") or {}
    if last.get("effects") and parsed.get("last_beat") is not None:
        candidates.append((int(parsed["last_beat"]), last["effects"], "last_transition"))

    seen = set()
    warned_duration: set[str] = set()
    warned_sheet: set[str] = set()
    for frame, effect, source in candidates:
        key = (frame, str(effect))
        if key in seen:
            continue
        seen.add(key)
        duration, sheet_data = _effect_info(effect, frame, assets_dir, interactive_sheets, sheet_cache)
        if duration is None and str(effect) not in warned_duration:
            warned_duration.add(str(effect))
            res.warnings.append(
                f"Effect '{effect}' at frame {frame}: no verified duration. Add 'duration' or a frame-specific 'durations' entry to effect_overrides.json."
            )
        if sheet_data is None and str(effect) not in warned_sheet:
            warned_sheet.add(str(effect))
            res.warnings.append(
                f"Effect '{effect}': sheet_data is not verified. Add it to effect_overrides.json rather than assuming a layout."
            )
        res.keyframes.append(
            EffectKey(frame, timeline.frame_to_timestamp(frame), effect, duration, sheet_data, source=source)
        )

    return res


def check_assets(result: EffectConversionResult, assets_dir: Optional[str]) -> None:
    if not assets_dir:
        result.warnings.append("No --assets-dir provided: skipping effect asset checks.")
        return
    from .asset_resolver import resolve_asset
    if not os.path.isdir(assets_dir):
        result.errors.append(f"--assets-dir '{assets_dir}' does not exist or is not a directory.")
        return
    missing = {k.effect for k in result.keyframes if resolve_asset(k.effect, assets_dir, asset_kind="effect") is None}
    result.warnings.extend(f"Missing effect asset: {name}" for name in sorted(missing, key=str.lower))
