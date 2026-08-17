import json
import os
from pathlib import Path

import pytest

from src.asset_resolver import resolve_asset, resolve_voice_bank_files
from src.animation_converter import convert_animations
from src.convert_mod import build_release_mod
from src.legacy_parser import parse_legacy_chart
from src.models import Timeline
from src.timeline import build_changes
from src.voice_bank_converter import convert_voice_banks

ROOT = os.path.dirname(os.path.dirname(__file__))


def test_asset_resolver_is_case_insensitive_and_blocks_parent_escape(tmp_path):
    (tmp_path / "Images").mkdir()
    asset = tmp_path / "Images" / "Idle.PNG"
    asset.write_bytes(b"ok")
    assert resolve_asset("idle.png", str(tmp_path), asset_kind="animation") == str(asset)
    assert resolve_asset("../secret.txt", str(tmp_path)) is None


def test_voice_bank_empty_transition_clears_without_inference(tmp_path):
    bank = tmp_path / "voice" / "open_moans_long"
    bank.mkdir(parents=True)
    (bank / "ahnn_1.ogg").write_bytes(b"1")
    (bank / "ahnn_2.ogg").write_bytes(b"2")
    parsed = {
        "bpm": 120,
        "note_offset": 0,
        "last_beat": 64,
        "initial_data": {"voice_bank": {"name": "open_moans_long", "interval": 8}},
        "transitions": {32: {"voice_bank": {}}},
    }
    result = convert_voice_banks(parsed, Timeline(120, 0, 64, []), str(tmp_path))
    assert result.entries[0].data["voice_paths"] == ["ahnn_1.ogg", "ahnn_2.ogg"]
    assert result.entries[-1].frame == 32
    assert result.entries[-1].data == {"voice_paths": []}


def test_voice_bank_name_resolver_returns_concrete_files(tmp_path):
    bank = tmp_path / "Voice" / "BankA"
    bank.mkdir(parents=True)
    (bank / "B.ogg").write_bytes(b"b")
    (bank / "A.wav").write_bytes(b"a")
    paths = resolve_voice_bank_files({"name": "banka"}, str(tmp_path))
    assert [Path(x).name for x in paths] == ["A.wav", "B.ogg"]


def test_last_transition_does_not_duplicate_same_animation_state():
    parsed = parse_legacy_chart(os.path.join(ROOT, "chart.cfg"))
    parsed["transitions"][parsed["last_beat"]] = dict(parsed["last_transition"])
    result = convert_animations(parsed, timeline=Timeline(parsed["bpm"], parsed["note_offset"], parsed["last_beat"], []), include_last_transition=True)
    matches = [x for x in result.keyframes if x.frame == parsed["last_beat"] and x.animation == parsed["last_transition"]["animation"]]
    assert len(matches) == 1


def test_note_collisions_have_explicit_precedence_and_are_reported():
    parsed = {
        "bpm": 120,
        "note_offset": 0,
        "last_beat": 16,
        "half_spawn": [0],
        "quarter_spawn": [0],
        "eighth_spawn": [0],
        "no_spawn": [0],
        "note_type": 0,
    }
    changes, collisions = build_changes(parsed)
    assert len(collisions) == 1
    assert changes[0].input_type is None


def test_release_build_copies_voice_bank_assets_and_reports_summary(tmp_path):
    mod = tmp_path / "Legacy"
    mod.mkdir()
    (mod / "voice" / "Bank").mkdir(parents=True)
    (mod / "voice" / "Bank" / "a.ogg").write_bytes(b"audio")
    (mod / "Idle.png").write_bytes(b"png")
    chart = '''
bpm = 120
note_offset = 0
half_spawn = [0]
quarter_spawn = []
eighth_spawn = []
no_spawn = [8]
last_beat = [8]
name = "Test"
song_path = "song.ogg"
initial_data = {"animation": "Idle.png", "note_type": 1, "voice_bank": {"name": "Bank", "interval": 2}}
transitions = {8: {"voice_bank": {}}}
last_transition = {}
'''
    (mod / "chart.cfg").write_text(chart, encoding="utf-8")
    (mod / "song.ogg").write_bytes(b"song")
    out = tmp_path / "Release"
    summary, issues = build_release_mod(str(mod), str(out), interactive_sheets=False)
    copied = out / "Test" / "audio" / "a.ogg"
    assert copied.is_file()
    assert summary["copied_assets_count"] >= 3
    assert not issues["errors"]


def test_cli_defaults_include_last_transition():
    import convert_mod
    parser = convert_mod.build_arg_parser()
    args = parser.parse_args(["input"])
    assert args.no_last_transition is False



def test_last_transition_animation_asset_is_checked(tmp_path):
    parsed = {
        "bpm": 120, "note_offset": 0, "last_beat": 32,
        "initial_data": {"animation": "Idle.png"},
        "transitions": {},
        "last_transition": {"animation": "Final.png"},
    }
    result = convert_animations(parsed, timeline=Timeline(120, 0, 32, []), assets_dir=str(tmp_path), include_last_transition=True)
    assert "Final.png" in result.missing_assets


def test_asset_basename_collision_is_reported(tmp_path):
    mod = tmp_path / "Legacy"
    mod.mkdir()
    (mod / "A").mkdir()
    (mod / "B").mkdir()
    (mod / "A" / "same.png").write_bytes(b"a")
    (mod / "B" / "same.png").write_bytes(b"b")
    (mod / "chart.cfg").write_text('''
bpm = 120
note_offset = 0
half_spawn = [0]
quarter_spawn = []
eighth_spawn = []
no_spawn = [8]
last_beat = [8]
name = "Collision"
initial_data = {"animation": "A/same.png", "note_type": 1}
transitions = {8: {"animation": "B/same.png"}}
last_transition = {}
''', encoding="utf-8")
    out = tmp_path / "Release"
    summary, issues = build_release_mod(str(mod), str(out), interactive_sheets=False)
    assert summary["asset_conflicts_count"] == 1
    assert any("Asset basename collision" in e for e in issues["errors"])


def test_release_metadata_places_creator_in_act_cfg_and_post_song_delay_in_settings(tmp_path):
    mod = tmp_path / "Legacy"
    mod.mkdir()
    (mod / "meta.cfg").write_text('''
[meta]
mod_title = "Title"
mod_creator = "Mod Creator"
mod_artist = "Ignored Artist"
song_artist = "Song Creator"
song_title = "Song Title"
''', encoding="utf-8")
    (mod / "chart.cfg").write_text('''
bpm = 120
note_offset = 0
half_spawn = [0]
quarter_spawn = []
eighth_spawn = []
no_spawn = [8]
last_beat = [8]
name = "Legacy Test"
song_path = "song.ogg"
post_song_delay = 5
initial_data = {"animation": "Idle.png", "note_type": 1}
transitions = {}
last_transition = {}
''', encoding="utf-8")
    (mod / "song.ogg").write_bytes(b"song")
    (mod / "Idle.png").write_bytes(b"png")

    out = tmp_path / "Release"
    build_release_mod(str(mod), str(out), interactive_sheets=False)

    def read_cfg(path):
        text = path.read_text(encoding="utf-8")
        payload = text.split("data=", 1)[1].strip()
        return json.loads(payload)

    scenario = out / "Title"
    mod_cfg = read_cfg(scenario / "config" / "mod.cfg")
    assert "creator" not in mod_cfg
    assert mod_cfg["song_creator"] == "Song Creator"
    assert mod_cfg["song_title"] == "Song Title"

    act_cfg = read_cfg(out / "act.cfg")
    assert act_cfg["author"] == "Mod Creator"
    assert "BBConverter" in act_cfg["act_description"]
    assert "https://github.com/DarkYoshi1/BBConverter" in act_cfg["act_description"]

    settings_cfg = read_cfg(scenario / "config" / "settings.cfg")
    assert settings_cfg["post_song_delay"] == 5
