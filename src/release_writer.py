from __future__ import annotations

import json
import os
from typing import Any, Iterable, List, Optional

try:
    from .note_generator import Note
except ImportError:  # pragma: no cover
    from src.note_generator import Note



def _write_cfg(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("[main]\n\n")
        f.write("data=")
        f.write(json.dumps(data, indent=2, ensure_ascii=False))
        f.write("\n")


def _build_note_entry(n: Note) -> dict:
    entry = {
        "input_type": n.input_type,
        "note_modifier": n.note_modifier,
        "timestamp": round(n.timestamp, 8),
    }
    if bool(getattr(n, "trigger_voice", False)):
        entry["trigger_voice"] = True
    return entry


def write_release_chart(path: str, notes: List[Note], name: str = "Normal", icon: str = "icon1.png", rating: int = 0) -> None:
    data = {
        "charts": [{
            "icon": icon,
            "name": name,
            "notes": [
                _build_note_entry(n)
                for n in notes
            ],
            "rating": rating,
        }]
    }
    _write_cfg(path, data)


def write_release_keyframes(path: str, keyframes, effects=None, modifiers=None, shutter=None,
                            sound_loops=None, sound_oneshot=None, voice_banks=None, background=None,
                            transition_sounds=None) -> None:
    loops_payload = []
    for kf in keyframes or []:
        item = {
            "animations": {"normal": kf.animation},
            "sheet_data": kf.sheet_data,
            "timestamp": round(kf.timestamp, 8),
        }
        if getattr(kf, "looping", None) is not None:
            item["looping"] = bool(kf.looping)
        loops_payload.append(item)

    effect_payload = []
    for e in effects or []:
        item = {"path": e.effect, "timestamp": round(e.timestamp, 8)}
        if e.duration is None:
            raise ValueError(
                f"Effect '{e.effect}' at timestamp {e.timestamp:.8f} has no resolvable duration. "
                "Add an explicit duration to effect_overrides.json or provide a verified 6/24-frame sheet layout."
            )
        item["duration"] = round(float(e.duration), 6)
        if e.sheet_data is not None:
            item["sheet_data"] = e.sheet_data
        effect_payload.append(item)

    sound_loop_payload = []
    for l in (sound_loops or []):
        payload = {"timestamp": round(l.start_timestamp, 8)}
        if isinstance(l.sound, list):
            payload["path"] = list(l.sound)
        else:
            payload["path"] = l.sound
        sound_loop_payload.append(payload)

    sound_oneshot_payload = [
        {"path": s.filename, "timestamp": round(s.timestamp, 8)}
        for s in (sound_oneshot or [])
    ]
    # Release stores transition/climax one-shot audio in `sound_oneshot`.
    # `transition_sound` is a Legacy concept and must never be emitted in the
    # Release keyframes schema. Keep the argument for backwards compatibility
    # with callers, but merge it into the one-shot payload.
    transition_one_shot_payload = [
        {"path": s.filename, "timestamp": round(s.timestamp, 8)}
        if hasattr(s, "filename") else dict(s)
        for s in (transition_sounds or [])
    ]
    sound_oneshot_payload.extend(transition_one_shot_payload)
    sound_oneshot_payload.sort(key=lambda item: (item.get("timestamp", 0), item.get("path", "")))
    voice_payload = []
    for v in (voice_banks or []):
        item = {"timestamp": round(v.timestamp, 8)}
        payload = dict(v.data or {})
        if "voice_paths" in payload:
            item["voice_paths"] = list(payload["voice_paths"])
        elif "path" in payload:
            item["voice_paths"] = [payload["path"]]
        elif "name" in payload:
            item["voice_paths"] = [payload["name"]]
        else:
            item.update(payload)
        voice_payload.append(item)
    background_payload = [
        {
            "path": b.path,
            "timestamp": round(b.timestamp, 8),
            **({"static": b.static} if b.static is not None else {}),
        }
        for b in (background or [])
    ]

    _write_cfg(path, {
        "background": background_payload,
        "effects": effect_payload,
        "loops": loops_payload,
        "modifiers": modifiers or [],
        "shutter": shutter or [],
        "sound_loop": sound_loop_payload,
        "sound_oneshot": sound_oneshot_payload,
        "voice_bank": voice_payload,
    })


def write_release_effects(path: str, effects) -> None:
    _write_cfg(path, {"effects": [
        {
            "path": e.effect,
            "timestamp": round(e.timestamp, 8),
            "duration": round(float(e.duration), 6),
            **({"sheet_data": e.sheet_data} if e.sheet_data is not None else {}),
        }
        for e in effects
    ]})


def write_release_sound_fx(path: str, triggers) -> None:
    _write_cfg(path, {"sound_fx_triggers": [
        {"path": t.filename, "timestamp": round(t.timestamp, 8), "source": t.source}
        for t in triggers
    ]})


def write_release_sound_loops(path: str, loops) -> None:
    _write_cfg(path, {"sound_loops": [
        {"path": l.sound, "timestamp": round(l.start_timestamp, 8), "looping": bool(l.looping)}
        for l in loops
    ]})


def write_release_voice_banks(path: str, entries) -> None:
    _write_cfg(path, {"voice_banks": [
        {
            "timestamp": round(e.timestamp, 8),
            **({"voice_paths": list(e.data["voice_paths"])} if isinstance(e.data, dict) and "voice_paths" in e.data else {}),
            **({"path": e.data["path"]} if isinstance(e.data, dict) and "path" in e.data and "voice_paths" not in e.data else {}),
        }
        for e in entries
    ]})
