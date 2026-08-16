from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from asset_resolver import AUDIO_EXTENSIONS, resolve_asset, resolve_voice_bank_files
from models import Timeline


@dataclass
class VoiceBankEntry:
    frame: int
    timestamp: float
    data: Dict[str, Any]


@dataclass
class VoiceBankResult:
    entries: List[VoiceBankEntry] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def _iter_voice_banks(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, dict):
        return [value] if value else []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict) and item]
    return []


def _normalize(data: Any, assets_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if not isinstance(data, dict) or not data:
        return None

    out = dict(data)
    raw_paths = out.get("voice_paths")
    if isinstance(raw_paths, str):
        raw_paths = [raw_paths]
    if isinstance(raw_paths, (list, tuple)):
        paths = [str(x).strip() for x in raw_paths if str(x).strip()]
    else:
        paths = []

    if not paths and assets_dir:
        resolved = resolve_voice_bank_files(out, assets_dir)
        paths = [os.path.basename(path) for path in resolved]

    if not paths:
        raw_path = out.get("path")
        if isinstance(raw_path, str) and raw_path.strip():
            paths = [os.path.basename(raw_path)]

    if paths:
        out["voice_paths"] = paths
    else:
        return None

    # Release uses concrete voice paths. A Legacy bank name is an authoring
    # convenience and should never leak into the Release payload.
    out.pop("name", None)
    if "path" in out and "voice_paths" in out:
        out.pop("path", None)

    if "interval" in out:
        try:
            out["interval"] = int(out["interval"])
        except (TypeError, ValueError):
            out.pop("interval", None)

    return out


def convert_voice_banks(parsed: dict, timeline: Optional[Timeline] = None, assets_dir: Optional[str] = None) -> VoiceBankResult:
    timeline = timeline or Timeline(float(parsed["bpm"]), float(parsed["note_offset"]), parsed.get("last_beat"), [])
    res = VoiceBankResult()
    active_voice_bank = False

    initial = parsed.get("initial_data") or {}
    for bank in _iter_voice_banks(initial.get("voice_bank")):
        data = _normalize(bank, assets_dir)
        if data:
            res.entries.append(VoiceBankEntry(0, timeline.frame_to_timestamp(0), data))
            active_voice_bank = True
        elif assets_dir:
            res.warnings.append("Initial voice_bank is defined but none of its audio files could be resolved.")

    for frame, transition in sorted((parsed.get("transitions") or {}).items()):
        if not isinstance(transition, dict) or "voice_bank" not in transition:
            continue
        banks = _iter_voice_banks(transition.get("voice_bank"))
        # Empty bank data means "no bank for this state". Emit a clear only
        # when a bank was previously active; otherwise omit the no-op event.
        if transition.get("voice_bank") == {} or transition.get("voice_bank") == []:
            if active_voice_bank:
                res.entries.append(VoiceBankEntry(int(frame), timeline.frame_to_timestamp(int(frame)), {"voice_paths": []}))
                active_voice_bank = False
            continue
        wrote = False
        for bank in banks:
            data = _normalize(bank, assets_dir)
            if data:
                res.entries.append(VoiceBankEntry(int(frame), timeline.frame_to_timestamp(int(frame)), data))
                active_voice_bank = True
                wrote = True
            else:
                res.warnings.append(f"Voice bank at frame={frame} could not be resolved to audio files.")
        if not wrote:
            active_voice_bank = False

    last = parsed.get("last_transition") or {}
    if last.get("voice_bank"):
        # last_transition has the same semantic position as the other final
        # transition fields: last_beat. This is now handled consistently.
        last_frame = timeline.final_frame()
        if last_frame is not None:
            for bank in _iter_voice_banks(last.get("voice_bank")):
                data = _normalize(bank, assets_dir)
                if data:
                    res.entries.append(VoiceBankEntry(last_frame, timeline.frame_to_timestamp(last_frame), data))
                else:
                    res.warnings.append("last_transition voice_bank is present but could not be resolved to audio files.")

    # Remove exact duplicate events created by repeated declarations.
    unique: dict[tuple, VoiceBankEntry] = {}
    for entry in res.entries:
        payload_key = repr(sorted(entry.data.items()))
        unique[(entry.frame, payload_key)] = entry
    res.entries = sorted(unique.values(), key=lambda x: x.frame)

    if not res.entries:
        res.warnings.append("No voice_bank data found.")
    return res


def check_assets(result: VoiceBankResult, assets_dir: Optional[str]) -> None:
    if not assets_dir:
        result.warnings.append("No --assets-dir provided: skipping voice_bank asset checks.")
        return
    if not os.path.isdir(assets_dir):
        result.errors.append(f"--assets-dir '{assets_dir}' does not exist or is not a directory.")
        return
    checked: set[str] = set()
    for entry in result.entries:
        for name in entry.data.get("voice_paths", []):
            if name in checked:
                continue
            checked.add(name)
            if resolve_asset(name, assets_dir, asset_kind="voice") is None:
                result.warnings.append(f"Missing voice bank asset: {name}")
