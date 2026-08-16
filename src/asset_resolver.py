from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

AUDIO_EXTENSIONS = (".ogg", ".wav", ".mp3", ".flac")
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
COMMON_ROOTS = (
    "", "assets", "images", "textures", "anims", "animations", "sprites",
    "fx", "effects", "audio", "sounds", "sfx", "songs", "voice", "video",
)


@dataclass(frozen=True)
class ResolvedAsset:
    reference: str
    path: str
    kind: Optional[str] = None


def normalize_reference(name: str) -> str:
    return os.path.normpath(str(name).replace("\\", os.sep).replace("/", os.sep))


def _case_insensitive_path(root: str, relative: str) -> Optional[str]:
    current = os.path.abspath(root)
    relative = relative.replace("\\", os.sep).replace("/", os.sep)
    for part in Path(relative).parts:
        if part in ("", "."):
            continue
        if not os.path.isdir(current):
            return None
        try:
            entries = os.listdir(current)
        except OSError:
            return None
        match = next((entry for entry in entries if entry.lower() == part.lower()), None)
        if match is None:
            return None
        current = os.path.join(current, match)
    return current if os.path.isfile(current) else None


def iter_asset_candidates(root: str, name: str) -> Iterable[str]:
    if not name:
        return
    root_abs = os.path.abspath(root)
    norm = normalize_reference(name)
    # References must stay inside the supplied asset root. A malformed Legacy
    # chart should never be able to make the converter read arbitrary files
    # through ../ traversal.
    joined = os.path.abspath(os.path.join(root_abs, norm))
    try:
        if os.path.commonpath((root_abs, joined)) != root_abs:
            return
    except ValueError:
        return
    seen: set[str] = set()

    def emit(candidate: str):
        candidate = os.path.normpath(candidate)
        key = os.path.normcase(os.path.abspath(candidate))
        if key not in seen:
            seen.add(key)
            return candidate
        return None

    # Exact candidates first.
    for base in COMMON_ROOTS:
        candidate = os.path.join(root, base, norm) if base else os.path.join(root, norm)
        result = emit(candidate)
        if result:
            yield result

        # Case-insensitive component-by-component lookup for Linux/macOS.
        relative = os.path.join(base, norm) if base else norm
        ci = _case_insensitive_path(root, relative)
        if ci:
            result = emit(ci)
            if result:
                yield result

    basename = os.path.basename(norm)
    if not basename:
        return

    # Exact basename fallback, then case-insensitive basename fallback.
    exact = []
    insensitive = []
    basename_lower = basename.lower()
    for walk_root, _, files in os.walk(root):
        for filename in files:
            if filename == basename:
                exact.append(os.path.join(walk_root, filename))
            elif filename.lower() == basename_lower:
                insensitive.append(os.path.join(walk_root, filename))
    for candidate in sorted(exact):
        result = emit(candidate)
        if result:
            yield result
    for candidate in sorted(insensitive):
        result = emit(candidate)
        if result:
            yield result


def resolve_asset(name: str, root: str, asset_kind: Optional[str] = None) -> Optional[str]:
    if not name or not root or not os.path.isdir(root):
        return None
    for candidate in iter_asset_candidates(root, name):
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return None


def resolve_assets(names: Sequence[str], root: str, asset_kind: Optional[str] = None) -> dict[str, ResolvedAsset]:
    result: dict[str, ResolvedAsset] = {}
    for name in names:
        if not isinstance(name, str) or not name:
            continue
        path = resolve_asset(name, root, asset_kind=asset_kind)
        if path:
            result[name] = ResolvedAsset(name, path, asset_kind)
    return result


def _path_inside_root(path: str, root: str) -> bool:
    try:
        return os.path.commonpath((os.path.abspath(root), os.path.abspath(path))) == os.path.abspath(root)
    except ValueError:
        return False


def resolve_voice_bank_files(value, root: Optional[str]) -> list[str]:
    """Resolve a Legacy voice_bank value to concrete source files.

    Empty banks are deliberately treated as "no bank". We never infer an
    arbitrary bank from the assets directory because that can activate the
    wrong voices in an otherwise valid chart.
    """
    if not root or not os.path.isdir(root) or not value:
        return []

    values = value if isinstance(value, list) else [value]
    resolved: list[str] = []

    for item in values:
        if not isinstance(item, dict):
            continue
        voice_paths = item.get("voice_paths")
        if isinstance(voice_paths, str):
            voice_paths = [voice_paths]
        if isinstance(voice_paths, (list, tuple)):
            for ref in voice_paths:
                if not isinstance(ref, str) or not ref.strip():
                    continue
                path = resolve_asset(ref, root, asset_kind="voice")
                if path:
                    resolved.append(path)
            if resolved:
                continue

        raw_path = item.get("path")
        if isinstance(raw_path, str) and raw_path.strip():
            path = resolve_asset(raw_path, root, asset_kind="voice")
            if path:
                resolved.append(path)

        name = item.get("name")
        if isinstance(name, str) and name.strip():
            normalized = normalize_reference(name)
            folder_candidates = [
                os.path.join(root, "voice", normalized),
                os.path.join(root, "audio", "voice", normalized),
                os.path.join(root, normalized),
                os.path.join(root, "audio", normalized),
            ]
            folder_candidates = [p for p in folder_candidates if _path_inside_root(p, root)]
            folder: Optional[str] = None
            for candidate in folder_candidates:
                if os.path.isdir(candidate):
                    folder = candidate
                    break
            if folder is None:
                # Search for a directory whose path component matches the bank name.
                bank_name = os.path.basename(normalized).lower()
                for walk_root, dirs, _ in os.walk(root):
                    match = next((d for d in dirs if d.lower() == bank_name), None)
                    if match:
                        folder = os.path.join(walk_root, match)
                        break
            if folder:
                for entry in sorted(os.listdir(folder), key=str.lower):
                    full = os.path.join(folder, entry)
                    if os.path.isfile(full) and entry.lower().endswith(AUDIO_EXTENSIONS):
                        resolved.append(full)

    # Stable, duplicate-free order.
    unique: dict[str, str] = {}
    for path in resolved:
        key = os.path.normcase(os.path.abspath(path))
        unique[key] = os.path.abspath(path)
    return list(unique.values())
