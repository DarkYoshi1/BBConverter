from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

try:
    from .convert_mod import find_chart_in_mod, find_meta_in_mod, find_thumb_in_mod
except ImportError:  # pragma: no cover
    from src.convert_mod import find_chart_in_mod, find_meta_in_mod, find_thumb_in_mod

try:
    from .legacy_parser import parse_legacy_chart, parse_legacy_meta
except ImportError:  # pragma: no cover
    from src.legacy_parser import parse_legacy_chart, parse_legacy_meta


APP_CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "BeatBangerConverter7"
SETTINGS_PATH = APP_CONFIG_DIR / "settings.json"


def load_settings(path: Path = SETTINGS_PATH) -> Dict[str, object]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}


def save_settings(data: Dict[str, object], path: Path = SETTINGS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temp, path)


def _direct_chart(path: Path) -> Optional[Path]:
    if not path.is_dir():
        return None
    for name in ("chart.cfg",):
        direct = path / name
        if direct.is_file():
            return direct
    # Legacy assets are sometimes stored under config/, but discovery must not
    # recurse through arbitrary nested mod folders because the library root can
    # contain many unrelated directories.
    config_dir = path / "config"
    if config_dir.is_dir():
        for entry in config_dir.iterdir():
            if entry.is_file() and entry.name.lower() == "chart.cfg":
                return entry
    return None


def _is_mod_directory(path: Path) -> bool:
    return _direct_chart(path) is not None


def _parse_mod_info(path: Path) -> Dict[str, object]:
    chart_path = find_chart_in_mod(str(path))
    chart = parse_legacy_chart(chart_path)
    meta_path = find_meta_in_mod(str(path))
    meta = parse_legacy_meta(meta_path) if meta_path else {}
    title = str(meta.get("mod_title") or chart.get("name") or path.name)
    artist = str(meta.get("mod_artist") or meta.get("song_artist") or "")
    song_title = str(meta.get("song_title") or "")
    thumb = find_thumb_in_mod(str(path), chart_path)
    return {
        "path": str(path.resolve()),
        "name": title,
        "artist": artist,
        "song_title": song_title,
        "thumb": thumb,
    }


def discover_mods(root: str) -> List[Dict[str, object]]:
    """Discover direct child Legacy mods under *root*.

    The selected folder is treated as a library, while each direct child
    containing a chart.cfg is treated as one Legacy mod. If the selected folder
    itself is a Legacy mod, it is returned as the sole result.
    """
    base = Path(root).expanduser().resolve()
    if not base.is_dir():
        return []

    if _is_mod_directory(base):
        candidates = [base]
    else:
        candidates = sorted((p for p in base.iterdir() if p.is_dir()), key=lambda p: p.name.lower())

    mods: List[Dict[str, object]] = []
    for candidate in candidates:
        if not _is_mod_directory(candidate):
            continue
        try:
            mods.append(_parse_mod_info(candidate))
        except (OSError, ValueError, UnicodeError, json.JSONDecodeError):
            # A malformed chart should not prevent the remaining library from
            # appearing. It can still be opened and diagnosed manually later.
            continue
    return mods
