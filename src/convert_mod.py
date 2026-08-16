from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from .asset_resolver import AUDIO_EXTENSIONS, IMAGE_EXTENSIONS, resolve_asset, resolve_voice_bank_files
except ImportError:  # pragma: no cover
    from src.asset_resolver import AUDIO_EXTENSIONS, IMAGE_EXTENSIONS, resolve_asset, resolve_voice_bank_files

try:
    from .animation_converter import convert_animations
except ImportError:  # pragma: no cover
    from src.animation_converter import convert_animations

try:
    from .background_converter import convert_backgrounds
except ImportError:  # pragma: no cover
    from src.background_converter import convert_backgrounds

try:
    from .effect_converter import convert_effects, check_assets as check_effect_assets
except ImportError:  # pragma: no cover
    from src.effect_converter import convert_effects, check_assets as check_effect_assets

try:
    from .legacy_parser import parse_legacy_chart, parse_legacy_meta
except ImportError:  # pragma: no cover
    from src.legacy_parser import parse_legacy_chart, parse_legacy_meta

try:
    from .note_generator import generate_notes
except ImportError:  # pragma: no cover
    from src.note_generator import generate_notes

try:
    from .release_writer import write_release_chart, write_release_keyframes
except ImportError:  # pragma: no cover
    from src.release_writer import write_release_chart, write_release_keyframes

try:
    from .sound_fx_converter import convert_sound_fx, check_assets as check_sfx_assets
except ImportError:  # pragma: no cover
    from src.sound_fx_converter import convert_sound_fx, check_assets as check_sfx_assets

try:
    from .sound_loop_converter import convert_sound_loops, check_assets as check_loop_assets
except ImportError:  # pragma: no cover
    from src.sound_loop_converter import convert_sound_loops, check_assets as check_loop_assets

try:
    from .timeline import build_changes, build_timeline
except ImportError:  # pragma: no cover
    from src.timeline import build_changes, build_timeline

try:
    from .voice_bank_converter import convert_voice_banks, check_assets as check_vb_assets
except ImportError:  # pragma: no cover
    from src.voice_bank_converter import convert_voice_banks, check_assets as check_vb_assets


RELEASE_SUBDIRS = ("audio", "config", "images")


def _sanitize_folder_name(name: str) -> str:
    name = (name or "Converted Legacy Mod").strip()
    for ch in '<>:"/\\|?*':
        name = name.replace(ch, "")
    return name or "Converted Legacy Mod"


def _first_case_insensitive_file(directory: str, filename: str) -> Optional[str]:
    if not os.path.isdir(directory):
        return None
    for entry in os.listdir(directory):
        if entry.lower() == filename.lower() and os.path.isfile(os.path.join(directory, entry)):
            return os.path.join(directory, entry)
    return None


def find_chart_in_mod(mod_dir: str) -> str:
    for relative in ("chart.cfg", os.path.join("config", "chart.cfg")):
        path = _first_case_insensitive_file(mod_dir, relative)
        if path:
            return path
    for root, _, files in os.walk(mod_dir):
        for filename in files:
            if filename.lower() == "chart.cfg":
                return os.path.join(root, filename)
    raise FileNotFoundError("chart.cfg not found in mod directory")


def find_thumb_in_mod(mod_dir: str, chart_path: Optional[str] = None) -> Optional[str]:
    chart_path = chart_path or find_chart_in_mod(mod_dir)
    for directory in (mod_dir, os.path.dirname(chart_path)):
        for filename in ("thumb.png", "thumb.jpg", "thumb.jpeg", "thumb.webp"):
            path = _first_case_insensitive_file(directory, filename)
            if path:
                return path
    for root, _, files in os.walk(mod_dir):
        for filename in files:
            stem, ext = os.path.splitext(filename)
            if stem.lower() == "thumb" and ext.lower() in IMAGE_EXTENSIONS:
                return os.path.join(root, filename)
    return None


def find_meta_in_mod(mod_dir: str) -> Optional[str]:
    chart_path = find_chart_in_mod(mod_dir)
    return _first_case_insensitive_file(os.path.dirname(chart_path), "meta.cfg")


def _background_path(value):
    if isinstance(value, (list, tuple)) and value and isinstance(value[0], str):
        return value[0]
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        value = value.get("path") or value.get("file")
        return value if isinstance(value, str) else None
    return None


def _iter_state_dicts(parsed: dict):
    initial = parsed.get("initial_data") or {}
    if isinstance(initial, dict):
        yield initial
    for value in (parsed.get("transitions") or {}).values():
        if isinstance(value, dict):
            yield value
    last = parsed.get("last_transition") or {}
    if isinstance(last, dict):
        yield last


def _add_reference(refs: set[str], value) -> None:
    if isinstance(value, str) and value.strip():
        refs.add(value.strip())
    elif isinstance(value, (list, tuple)):
        for item in value:
            if isinstance(item, str) and item.strip():
                refs.add(item.strip())


def _voice_bank_references(value) -> list[str]:
    refs: list[str] = []
    banks = value if isinstance(value, list) else [value]
    for bank in banks:
        if not isinstance(bank, dict) or not bank:
            continue
        for key in ("name", "path"):
            if isinstance(bank.get(key), str) and bank[key].strip():
                refs.append(bank[key].strip())
        paths = bank.get("voice_paths")
        if isinstance(paths, str):
            paths = [paths]
        if isinstance(paths, (list, tuple)):
            refs.extend(str(p).strip() for p in paths if str(p).strip())
    return refs


def collect_referenced_assets(parsed: dict, assets_dir: Optional[str] = None) -> List[str]:
    """Return every source asset reference used by the chart, including voice banks.

    The list is reference-level, not filesystem-level. A voice-bank folder name is
    retained here while copy_assets() resolves its concrete member files.
    """
    refs: set[str] = set()
    for state in _iter_state_dicts(parsed):
        for key in ("animation", "effects", "sound_fx", "transition_sound", "climax_sound",
                    "sound_fx_trigger", "background"):
            _add_reference(refs, _background_path(state.get(key)) if key == "background" else state.get(key))
        refs.update(_voice_bank_references(state.get("voice_bank")))
    _add_reference(refs, parsed.get("song_path"))
    _add_reference(refs, parsed.get("game_over_sound"))
    return sorted(refs, key=str.lower)


def _asset_destination(name: str, scenario_root: str) -> str:
    lower = str(name).lower()
    subdir = "images" if lower.endswith(IMAGE_EXTENSIONS) else "audio" if lower.endswith(AUDIO_EXTENSIONS) else "audio"
    return os.path.join(scenario_root, subdir, os.path.basename(str(name)))


def _copy_resolved_asset(src: str, name: str, scenario_root: str, copied: list[str], destinations: dict[str, str], errors: list[str]) -> None:
    destination = _asset_destination(name, scenario_root)
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    key = os.path.normcase(os.path.basename(destination))
    if key in destinations:
        previous = destinations[key]
        if previous == os.path.abspath(src):
            return
        # Release stores these files flat. Two different source files with the
        # same basename cannot both be represented without changing references.
        old_hash = hashlib.sha256(Path(previous).read_bytes()).hexdigest()
        new_hash = hashlib.sha256(Path(src).read_bytes()).hexdigest()
        if old_hash != new_hash:
            errors.append(f"Asset basename collision for '{os.path.basename(destination)}': '{previous}' vs '{src}'.")
            return
        return
    shutil.copy2(src, destination)
    destinations[key] = os.path.abspath(src)
    copied.append(os.path.relpath(destination, scenario_root).replace(os.sep, "/"))


def copy_assets(parsed: dict, src_root: str, scenario_root: str) -> Tuple[List[str], List[str], List[str]]:
    copied: list[str] = []
    missing: list[str] = []
    conflicts: list[str] = []
    destinations: dict[str, str] = {}

    direct_refs = collect_referenced_assets(parsed)
    states = list(_iter_state_dicts(parsed))

    for ref in direct_refs:
        # Voice-bank directory names are resolved below; skip them here if they
        # are not actual files.
        src = resolve_asset(ref, src_root)
        if src:
            _copy_resolved_asset(src, ref, scenario_root, copied, destinations, conflicts)
        elif not any(ref in _voice_bank_references(state.get("voice_bank")) for state in states):
            missing.append(ref)

    # Resolve every concrete voice-bank member file. Empty banks explicitly
    # clear voice state and are never inferred.
    seen_voice_files: set[str] = set()
    for state in states:
        value = state.get("voice_bank")
        files = resolve_voice_bank_files(value, src_root)
        referenced_member_names = set(_voice_bank_references(value))
        for src in files:
            src = os.path.abspath(src)
            key = os.path.normcase(src)
            if key in seen_voice_files:
                continue
            seen_voice_files.add(key)
            _copy_resolved_asset(src, os.path.basename(src), scenario_root, copied, destinations, conflicts)
        if value:
            # A non-empty bank must resolve at least one concrete audio file.
            normalized = [x for x in files if os.path.isfile(x)]
            if not normalized:
                missing.extend(sorted(referenced_member_names, key=str.lower))

    missing = sorted(set(missing), key=str.lower)
    conflicts = sorted(set(conflicts), key=str.lower)
    return sorted(set(copied), key=str.lower), missing, conflicts


def _write_text(path: str, text: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _write_minimal_png(path: str):
    import struct, zlib
    width = height = 1
    raw = b"\x00\x00\x00\x00"
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)


def _copy_thumb_or_placeholder(legacy_thumb: Optional[str], destination: str) -> None:
    """Preserve Legacy's real thumb.png; only fall back to 1x1 when absent."""
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    if legacy_thumb and os.path.isfile(legacy_thumb):
        shutil.copy2(legacy_thumb, destination)
        return
    _write_minimal_png(destination)


def _write_scenario_release_files(scenario_root: str, anim, mod_name: str, legacy_thumb: Optional[str] = None, effects=None):
    """Writes what a real scenario folder (e.g. 'Girl Slut') has OUTSIDE of
    config/: editor_cache.cfg and thumb.png. No chart.cfg, no
    autosaved_chart.cfg, no splash.png, no meta.cfg here — those either
    don't exist in the real layout or only live under config/."""
    from .animation_converter import resolve_sheet_data, SHEET_DATA_OVERRIDES

    # editor_cache.cfg: one sprite_sheet entry per unique animation and effect
    # asset actually used. Release indexes effect sprites here too, even though
    # they are one-shot keyframes rather than looping animations.
    # scale_multiplier is intentionally omitted: the real example always
    # includes it, but we don't have a confirmed rule for its value, and we
    # don't invent numbers.
    unique_animations = sorted({kf.animation for kf in anim.keyframes})
    effect_items = list(effects or [])
    unique_effects = sorted({e.effect for e in effect_items if getattr(e, "effect", None)})
    # Release's editor_cache indexes both normal animation sheets and one-shot
    # effect sheets. Effects are not loops, but the runtime still needs their
    # sprites registered here to resolve them from keyframes.cfg.
    cache_entries = [
        {"sprite_sheet": name, "sheet_data": resolve_sheet_data(name)}
        for name in unique_animations
    ]
    for name in unique_effects:
        # EffectConversionResult already carries the verified sheet layout; use
        # it when available instead of re-inferring it from the filename.
        effect_layout = next(
            (getattr(e, "sheet_data", None) for e in effect_items
             if getattr(e, "effect", None) == name and getattr(e, "sheet_data", None) is not None),
            None,
        )
        cache_entries.append({
            "sprite_sheet": name,
            "sheet_data": effect_layout or resolve_sheet_data(name),
        })
    _write_text(os.path.join(scenario_root, "editor_cache.cfg"),
                "[main]\n\ndata=" + json.dumps(cache_entries, indent=2, ensure_ascii=False) + "\n")

    _copy_thumb_or_placeholder(legacy_thumb, os.path.join(scenario_root, "thumb.png"))


def _write_mod_root_files(output_mod: str, mod_name: str, legacy_thumb: Optional[str] = None):
    """Writes what lives at the TOP of a real mod folder (sibling to the
    scenario folder(s)): act.cfg and thumb.png. Legacy has no equivalent of
    act_description/act_id, so those are left empty rather than invented."""
    act_cfg = {
        "act_description": "",
        "act_id": "",
        "act_index": 0,
        "act_name": mod_name,
    }
    _write_text(os.path.join(output_mod, "act.cfg"),
                "[main]\n\ndata=" + json.dumps(act_cfg, indent=2, ensure_ascii=False) + "\n")
    _copy_thumb_or_placeholder(legacy_thumb, os.path.join(output_mod, "thumb.png"))


def _write_config_meta(config_root: str, parsed: dict, legacy_meta: dict, mod_name: str) -> List[str]:
    """Writes mod.cfg, meta.cfg, asset.cfg, settings.cfg using the schemas
    CONFIRMED by a real Release mod (ModRelease.zip). Fields with no Legacy
    source are left as empty string ("") — a safe, visibly-blank default —
    or omitted entirely for non-string fields (numbers/arrays), rather than
    invented. Returns a list of warnings about what was left blank."""
    warnings: List[str] = []
    scenario_root = os.path.dirname(config_root)

    # --- mod.cfg: creator/description/preview_timestamp/song_author/song_title ---
    # Confirmed source: Legacy's meta.cfg (mod_creator, song_artist, song_title).
    if not legacy_meta:
        warnings.append("No meta.cfg found next to chart.cfg: mod.cfg's creator/song_author/"
                         "song_title were left blank.")
    # Preserve original mod fields and include level_id for save stability.
    mod_cfg = {
        "creator": legacy_meta.get("mod_creator", ""),
        "description": "",  # no Legacy source for a description; left blank, not invented
        "song_author": legacy_meta.get("song_artist", ""),
        "song_title": legacy_meta.get("song_title") or parsed.get("name") or "",
        # level_id populated below and injected into meta_cfg/settings as well
        # to ensure Release can reliably identify the level for saves.
    }
    warnings.append("mod.cfg: 'preview_timestamp' omitted — Legacy has no equivalent "
                     "(it's a creative choice, a song-preview start time); set manually if desired.")
    if legacy_meta.get("mod_artist"):
        warnings.append(f"Legacy meta.cfg has 'mod_artist' = {legacy_meta['mod_artist']!r}, which has "
                         f"no confirmed field in Release's mod.cfg schema — not written anywhere.")
    _write_text(os.path.join(config_root, "mod.cfg"), "[main]\n\ndata=" + json.dumps(mod_cfg, indent=2, ensure_ascii=False) + "\n")

    # --- meta.cfg: character/color/level_id/level_index/level_name ---
    # Confirmed source: only level_name (from Legacy mod_title / chart name).
    # character, color, level_id have NO Legacy source at all.
    # Legacy has no level_id. Use a deterministic identifier derived from the
    # level name and song path so repeated conversions of the same source keep
    # the same Release identity.
    level_name = legacy_meta.get("mod_title") or mod_name
    raw = (str(level_name) + "\n" + str(parsed.get("song_path") or "")).encode("utf-8")
    level_id = hashlib.md5(raw).hexdigest()

    meta_cfg = {
        "character": "",
        "level_id": level_id,
        "level_index": 0,
        "level_name": level_name,
    }
    warnings.append("meta.cfg: 'character' has no Legacy equivalent and is left blank. 'color' is omitted because Legacy provides no verified Release value.")
    # Write a top-level scenario meta.cfg (some Release loaders expect a
    # meta.cfg alongside the scenario folder) first, then mirror it to
    # config/meta.cfg. Doing the top-level write first avoids any subtle
    # ordering issues on some filesystems.
    _write_text(os.path.join(scenario_root, "meta.cfg"), "[main]\n\ndata=" + json.dumps(meta_cfg, indent=2, ensure_ascii=False) + "\n")
    _write_text(os.path.join(config_root, "meta.cfg"), "[main]\n\ndata=" + json.dumps(meta_cfg, indent=2, ensure_ascii=False) + "\n")

    # --- asset.cfg: cutscene_song_path/final_audio/final_video/horny_mode_sound/song_path ---
    # Confirmed source: song_path (Legacy song_path). The real example always
    # has cutscene_song_path == song_path when there's no separate cutscene
    # track, and final_audio/final_video/horny_mode_sound empty when unused —
    # Legacy doesn't distinguish any of those three, so we default to that
    # observed "no cutscene / no special audio" pattern rather than inventing.
    song_path = parsed.get("song_path") or ""
    asset_cfg = {
        "cutscene_song_path": song_path,
        "final_audio": "",
        "final_video": "",
        "game_over_sound": parsed.get("game_over_sound") or "",
        "horny_mode_sound": "",
        "song_path": song_path,
    }
    _write_text(os.path.join(config_root, "asset.cfg"), "[main]\n\ndata=" + json.dumps(asset_cfg, indent=2, ensure_ascii=False) + "\n")

    # --- settings.cfg: background_type/note_offset/song_offset ---
    # background_type and song_offset have no Legacy equivalent found yet.
    # Release expects song_offset to exist. Legacy's note_offset is already
    # baked into every generated timestamp by Timeline, so writing the same
    # value again would shift the song twice. Keep the runtime song offset at
    # zero while preserving Legacy timing in the generated timestamps.
    # (Confirmed by test_song_offset_is_not_double_applied — do not add
    # note_offset back into this dict.)
    settings = {
        "song_offset": 0.0,
        "level_id": meta_cfg.get("level_id", ""),
    }
    warnings.append("settings.cfg: song_offset set to 0 because Legacy note_offset is already baked into chart/keyframe timestamps; this prevents double-offset playback.")
    for k in ("music_volume", "sfx_volume", "voice_volume", "loop_speed", "screen_flash", "post_song_delay", "bar_position"):
        if parsed.get(k) is not None:
            warnings.append(f"Legacy chart.cfg has {k}={parsed[k]!r}, but it does not appear in "
                             f"settings.cfg's confirmed schema — not written anywhere.")

    _write_text(os.path.join(config_root, "settings.cfg"), "[main]\n\ndata=" + json.dumps(settings, indent=2, ensure_ascii=False) + "\n")

    return warnings


def _write_conversion_debug(path: str, parsed: dict, timeline: Timeline, changes, collisions, notes,
                            results: dict, copied: List[str], missing_assets: List[str]):
    lines = [
        "BeatBangerConverter2 conversion diagnostics",
        "=" * 60,
        f"name={parsed.get('name')}",
        f"bpm={timeline.bpm}",
        f"note_offset={timeline.note_offset}",
        f"last_beat={timeline.last_beat}",
        f"seconds_per_frame={timeline.seconds_per_frame:.12f}",
        f"timeline_events={len(timeline.events)}",
        f"note_state_changes={len(changes)}",
        f"note_collisions={len(collisions)}",
        f"notes={len(notes)}",
        f"copied_assets={len(copied)}",
        f"missing_assets={len(missing_assets)}",
        "",
    ]
    for name, result in results.items():
        lines.append(f"[{name}]")
        for key in ("keyframes", "loops", "entries", "triggers"):
            value = getattr(result, key, None)
            if value is not None: lines.append(f"{key}={len(value)}")
        for warning in getattr(result, "warnings", []): lines.append("WARNING: " + warning)
        for error in getattr(result, "errors", []): lines.append("ERROR: " + error)
        lines.append("")
    if copied:
        lines.append("COPIED ASSETS")
        lines.extend("  " + x for x in copied)
    if missing_assets:
        lines.append("MISSING ASSETS")
        lines.extend("  " + x for x in missing_assets)
    _write_text(path, "\n".join(lines) + "\n")



def build_release_mod(input_mod: str, output_mod: str, assets_dir: Optional[str] = None,
                      include_last_transition: bool = True, copy_assets_flag: bool = True,
                      scenario_name: Optional[str] = None, interactive_sheets: bool = True):
    input_mod = os.path.abspath(input_mod)
    output_mod = os.path.abspath(output_mod)
    if not os.path.isdir(input_mod):
        raise NotADirectoryError(f"Input mod directory does not exist: {input_mod}")
    chart_path = find_chart_in_mod(input_mod)
    parsed = parse_legacy_chart(chart_path)
    timeline = build_timeline(parsed)
    assets_dir = os.path.abspath(assets_dir or input_mod)
    if not os.path.isdir(assets_dir):
        raise NotADirectoryError(f"Assets directory does not exist: {assets_dir}")

    legacy_thumb = find_thumb_in_mod(input_mod, chart_path)
    meta_path = find_meta_in_mod(input_mod)
    legacy_meta = parse_legacy_meta(meta_path) if meta_path else {}
    mod_name = legacy_meta.get("mod_title") or parsed.get("name") or os.path.basename(input_mod)
    scenario_root = os.path.join(output_mod, _sanitize_folder_name(scenario_name or mod_name))
    config_root = os.path.join(scenario_root, "config")
    for subdir in RELEASE_SUBDIRS:
        os.makedirs(os.path.join(scenario_root, subdir), exist_ok=True)

    root_meta = {
        "mod_title": legacy_meta.get("mod_title") or mod_name,
        "mod_creator": legacy_meta.get("mod_creator", ""),
        "mod_artist": legacy_meta.get("mod_artist", ""),
        "song_artist": legacy_meta.get("song_artist", ""),
        "song_title": legacy_meta.get("song_title", parsed.get("name") or ""),
        "length": legacy_meta.get("length", ""),
    }
    _write_text(os.path.join(output_mod, "meta.cfg"), "[main]\n\ndata=" + json.dumps(root_meta, indent=2, ensure_ascii=False) + "\n")

    changes, collisions = build_changes(parsed)
    notes = generate_notes(changes, timeline, parsed)
    anim = convert_animations(parsed, timeline=timeline, assets_dir=assets_dir, include_last_transition=include_last_transition)
    effects = convert_effects(parsed, timeline=timeline, assets_dir=assets_dir, interactive_sheets=interactive_sheets)
    loops = convert_sound_loops(parsed, timeline=timeline)
    audio = convert_sound_fx(parsed, timeline=timeline)
    backgrounds = convert_backgrounds(parsed, timeline)
    voice_banks = convert_voice_banks(parsed, timeline=timeline, assets_dir=assets_dir)

    check_effect_assets(effects, assets_dir)
    check_sfx_assets(audio, assets_dir)
    check_loop_assets(loops, assets_dir)
    check_vb_assets(voice_banks, assets_dir)
    anim_asset_result = []
    from .animation_converter import check_assets as check_animation_assets
    check_animation_assets(anim, assets_dir)

    copied: List[str] = []
    missing_assets: List[str] = []
    asset_conflicts: List[str] = []
    if copy_assets_flag:
        copied, missing_assets, asset_conflicts = copy_assets(parsed, assets_dir, scenario_root)
    else:
        missing_assets = collect_referenced_assets(parsed)

    write_release_chart(os.path.join(config_root, "notes.cfg"), notes, name="Normal", icon="icon1.png", rating=0)
    write_release_keyframes(
        os.path.join(config_root, "keyframes.cfg"),
        anim.keyframes,
        effects=effects.keyframes,
        modifiers=[{"bpm": parsed["bpm"], "timestamp": 0.0}],
        shutter=[],
        sound_loops=loops.loops,
        sound_oneshot=audio.triggers + audio.climax_sounds,
        voice_banks=voice_banks.entries,
        background=backgrounds.keyframes,
        transition_sounds=audio.transition_sounds,
    )

    meta_warnings = _write_config_meta(config_root, parsed, legacy_meta, mod_name)
    _write_scenario_release_files(scenario_root, anim, mod_name, legacy_thumb, effects=effects.keyframes)
    _write_mod_root_files(output_mod, mod_name, legacy_thumb)

    diagnostics = {"assets": collect_referenced_assets(parsed), "missing_assets": missing_assets, "asset_conflicts": asset_conflicts}
    debug_path = output_mod.rstrip(os.sep) + "_conversion_debug.txt"
    results = {
        "animations": anim,
        "effects": effects,
        "sound_loops": loops,
        "audio": audio,
        "background": backgrounds,
        "voice_banks": voice_banks,
    }
    _write_conversion_debug(debug_path, parsed, timeline, changes, collisions, notes, results, copied, missing_assets + asset_conflicts)

    warnings = list(timeline.warnings) + meta_warnings
    errors: List[str] = []
    for result in results.values():
        warnings.extend(getattr(result, "warnings", []))
        errors.extend(getattr(result, "errors", []))
    if collisions:
        errors.append(f"{len(collisions)} note timeline collision(s) were detected. The chosen precedence is only a diagnostic fallback; fix the Legacy chart before shipping the Release mod.")
    errors.extend(asset_conflicts)

    summary = {
        "output_root": output_mod,
        "scenario_root": scenario_root,
        "notes_written": os.path.join(config_root, "notes.cfg"),
        "keyframes_written": os.path.join(config_root, "keyframes.cfg"),
        "copied_assets_count": len(copied),
        "missing_assets_count": len(set(missing_assets)),
        "asset_conflicts_count": len(asset_conflicts),
        "notes_count": len(notes),
        "animation_keyframes": len(anim.keyframes),
        "effects": len(effects.keyframes),
        "sound_loops": len(loops.loops),
        "sound_oneshots": len(audio.triggers) + len(audio.climax_sounds) + len(audio.transition_sounds),
        "voice_banks": len(voice_banks.entries),
        "background_keyframes": len(backgrounds.keyframes),
        "warnings": len(warnings),
        "errors": len(errors),
        "debug": debug_path,
    }
    return summary, {"warnings": warnings, "errors": errors, "diagnostics": diagnostics}


def build_arg_parser():
    p = argparse.ArgumentParser(description="Convert a Beat Banger Legacy mod folder to the Release mod layout")
    p.add_argument("--gui", action="store_true", help="Open the Tkinter graphical interface instead of the command-line flow")
    p.add_argument("input_mod", nargs="?", default="", help="Path to the Legacy mod folder (containing chart.cfg)")
    p.add_argument("output_mod", nargs="?", default=None, help="Where to write the Release mod. Defaults to '<input_mod>_Release'.")
    p.add_argument("--assets-dir", default=None, help="Directory containing Legacy assets. Defaults to input_mod.")
    p.add_argument("--no-copy-assets", action="store_true", help="Do not copy referenced assets into the Release mod.")
    p.add_argument("--no-interactive", action="store_true", help="Do not prompt for unknown effect sprite-sheet layouts.")
    p.add_argument("--no-last-transition", action="store_true", help="Omit the Legacy last_transition state at the final timeline frame.")
    p.add_argument("--scenario-name", default=None, help="Name for the single Release scenario folder.")
    return p


if __name__ == "__main__":
    args = build_arg_parser().parse_args()
    if args.gui:
        from .tkinter_app import launch_gui
        launch_gui()
    else:
        if not args.input_mod:
            raise SystemExit("You must provide an input mod directory or use --gui to open the graphical interface.")
        input_mod = os.path.abspath(args.input_mod)
        output_mod = args.output_mod or (input_mod.rstrip(os.sep) + "_Release")
        summary, issues = build_release_mod(
            input_mod, output_mod, assets_dir=args.assets_dir,
            include_last_transition=not args.no_last_transition,
            copy_assets_flag=not args.no_copy_assets,
            scenario_name=args.scenario_name,
            interactive_sheets=not args.no_interactive,
        )
        print(json.dumps({"summary": summary, "issues": issues}, indent=2, ensure_ascii=False))
