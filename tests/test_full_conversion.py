import os
import json
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

from legacy_parser import parse_legacy_chart
from models import Timeline
from timeline import build_timeline, build_changes
from note_generator import generate_notes
from animation_converter import convert_animations
from effect_converter import convert_effects
from sound_loop_converter import convert_sound_loops
from sound_fx_converter import convert_sound_fx
from background_converter import convert_backgrounds


def load_chart():
    return parse_legacy_chart(os.path.join(ROOT, "chart.cfg"))


def test_single_timeline_is_shared_everywhere():
    parsed = load_chart()
    tl = build_timeline(parsed)
    changes, _ = build_changes(parsed)
    notes = generate_notes(changes, tl)
    anim = convert_animations(parsed, timeline=tl)
    effects = convert_effects(parsed, timeline=tl)
    loops = convert_sound_loops(parsed, timeline=tl)
    audio = convert_sound_fx(parsed, timeline=tl)
    bg = convert_backgrounds(parsed, tl)

    frame = 192
    expected = tl.frame_to_timestamp(frame)
    note = next(n for n in notes if n.legacy_frame == 192)
    kf = next(k for k in anim.keyframes if k.frame == frame)
    fx = next(e for e in effects.keyframes if e.frame == frame) if any(e.frame == frame for e in effects.keyframes) else None
    loop = next(l for l in loops.loops if l.start_frame == 192)
    assert note.timestamp == expected
    assert kf.timestamp == expected
    assert fx is None or fx.timestamp == expected
    assert loop.start_timestamp == expected


def test_last_transition_is_end_of_level():
    parsed = load_chart()
    tl = build_timeline(parsed)
    anim = convert_animations(parsed, timeline=tl)
    effects = convert_effects(parsed, timeline=tl)
    audio = convert_sound_fx(parsed, timeline=tl)

    end_frame = parsed["last_beat"]
    assert any(k.frame == end_frame and k.animation == "Cum.png" for k in anim.keyframes)
    assert any(e.frame == end_frame and e.effect == "cum_fx.png" for e in effects.keyframes)
    assert any(s.frame == end_frame and s.filename == "sfx_next.ogg" for s in audio.transition_sounds)
    assert any(s.frame == end_frame and s.filename == "sfx_cum.ogg" for s in audio.climax_sounds)


def test_audio_systems_are_not_duplicated():
    parsed = load_chart()
    tl = build_timeline(parsed)
    loops = convert_sound_loops(parsed, timeline=tl)
    audio = convert_sound_fx(parsed, timeline=tl)
    loop_names = {x.sound for x in loops.loops}
    one_shots = {x.filename for x in audio.transition_sounds}
    assert "sfx_plap_dry.ogg" in loop_names
    assert "sfx_plap_dry.ogg" not in one_shots
    assert "sfx_next.ogg" in one_shots
    assert "sfx_cum.ogg" in {x.filename for x in audio.climax_sounds}


def test_backgrounds_preserve_static_metadata():
    parsed = load_chart()
    tl = build_timeline(parsed)
    bg = convert_backgrounds(parsed, tl)
    assert bg.keyframes
    first = bg.keyframes[0]
    assert first.path == "Bedroom.png"
    assert first.static is True


def test_effect_override_metadata_is_preserved_when_verified():
    parsed = load_chart()
    tl = build_timeline(parsed)
    fx = convert_effects(parsed, timeline=tl)
    hearts = next(x for x in fx.keyframes if x.effect == "hearts.png")
    assert hearts.duration == 0.5
    assert hearts.sheet_data == {"h": 3, "v": 2, "total": 6}
    assert not any("duration is not present" in w for w in fx.warnings)


def test_release_keyframes_match_example_schema_for_sfx_fx_and_voice_bank():
    from sound_loop_converter import SoundLoop
    from voice_bank_converter import VoiceBankEntry
    from release_writer import write_release_keyframes

    loops = [SoundLoop(0, 0.0, ["dryplap01.mp3", "dryplap02.mp3"], True, "initial_data")]
    voices = [VoiceBankEntry(30, 30.0, {"voice_paths": ["voice_a.mp3", "voice_b.mp3"]})]
    payload = {}

    write_release_keyframes(
        os.path.join(os.getcwd(), "tmp_keyframes_test.cfg"),
        [],
        effects=[],
        sound_loops=loops,
        sound_oneshot=[],
        voice_banks=voices,
        transition_sounds=[],
    )

    with open(os.path.join(os.getcwd(), "tmp_keyframes_test.cfg"), "r", encoding="utf-8") as f:
        payload = f.read()
    assert '"sound_loop"' in payload
    assert 'dryplap01.mp3' in payload and 'dryplap02.mp3' in payload
    assert '"voice_bank"' in payload
    assert 'voice_a.mp3' in payload and 'voice_b.mp3' in payload
    assert '"transition_sound"' not in payload
    os.remove(os.path.join(os.getcwd(), "tmp_keyframes_test.cfg"))


def test_voice_bank_name_resolves_real_files_from_legacy_voice_folder(tmp_path):
    from models import Timeline
    from voice_bank_converter import convert_voice_banks

    bank_dir = tmp_path / "voice" / "open_moans_long"
    bank_dir.mkdir(parents=True)
    (bank_dir / "ahnn_1.ogg").write_bytes(b"x")
    (bank_dir / "ahnn_2.ogg").write_bytes(b"y")

    parsed = {
        "bpm": 120,
        "note_offset": 0,
        "last_beat": 128,
        "initial_data": {"voice_bank": {}},
        "transitions": {
            32: {"voice_bank": {"name": "open_moans_long", "interval": 8}}
        },
    }

    res = convert_voice_banks(parsed, timeline=Timeline(120, 0, 128, []), assets_dir=str(tmp_path))
    assert len(res.entries) == 1
    assert res.entries[0].data["voice_paths"] == ["ahnn_1.ogg", "ahnn_2.ogg"]
    assert "name" not in res.entries[0].data


def test_generate_notes_sets_trigger_voice_using_voice_bank_interval():
    parsed = {
        "bpm": 120,
        "note_offset": 0,
        "last_beat": 64,
        "note_type": 1,
        "initial_data": {"voice_bank": {}},
        "quarter_spawn": [0, 16, 32, 40, 48, 56],
        "transitions": {
            32: {"voice_bank": {"name": "open_moans_long", "interval": 8}},
            64: {"voice_bank": {}}
        },
    }
    tl = Timeline(120, 0, 64, [])
    changes, _ = build_changes(parsed)
    notes = generate_notes(changes, tl, parsed)

    assert any(n.legacy_frame == 0 and n.trigger_voice is False for n in notes)
    assert any(n.legacy_frame == 16 and n.trigger_voice is False for n in notes)
    assert any(n.legacy_frame == 32 and n.trigger_voice is True for n in notes)
    assert any(n.legacy_frame == 40 and n.trigger_voice is True for n in notes)
    assert any(n.legacy_frame == 48 and n.trigger_voice is True for n in notes)
    assert any(n.legacy_frame == 56 and n.trigger_voice is True for n in notes)
    assert not any(n.trigger_voice for n in notes if n.legacy_frame < 32)
    assert not any(n.trigger_voice for n in notes if n.legacy_frame >= 64)


def test_effect_duration_can_be_overridden_per_frame():
    import effect_converter

    original = dict(effect_converter.OVERRIDES)
    try:
        effect_converter.OVERRIDES.clear()
        effect_converter.OVERRIDES.update({
            "hearts.png": {
                "sheet_data": {"h": 3, "v": 2, "total": 6},
                "duration": 0.5,
                "durations": {"10": 0.3},
            }
        })
        parsed = {
            "bpm": 120,
            "note_offset": 0,
            "last_beat": 32,
            "initial_data": {},
            "transitions": {10: {"effects": "hearts.png"}, 20: {"effects": "hearts.png"}},
        }
        from models import Timeline
        from effect_converter import convert_effects
        fx = convert_effects(parsed, timeline=Timeline(120, 0, 32, []), interactive_sheets=False)
        by_frame = {e.frame: e.duration for e in fx.keyframes}
        assert by_frame[10] == 0.3
        assert by_frame[20] == 0.5
    finally:
        effect_converter.OVERRIDES.clear()
        effect_converter.OVERRIDES.update(original)


def test_release_effects_require_and_emit_duration_without_invented_fields():
    from effect_converter import EffectKey
    from release_writer import write_release_keyframes

    path = os.path.join(os.getcwd(), "tmp_effect_keyframes_test.cfg")
    write_release_keyframes(
        path, [],
        effects=[EffectKey(10, 1.25, "hearts.png", 0.5, {"h": 3, "v": 2, "total": 6})],
    )
    with open(path, "r", encoding="utf-8") as f:
        payload = f.read()
    assert '"duration": 0.5' in payload
    assert '"scale_multiplier"' not in payload
    os.remove(path)


def test_release_effects_reject_missing_duration():
    from effect_converter import EffectKey
    from release_writer import write_release_keyframes

    path = os.path.join(os.getcwd(), "tmp_effect_keyframes_invalid.cfg")
    try:
        write_release_keyframes(
            path, [],
            effects=[EffectKey(10, 1.25, "hearts.png", None, {"h": 3, "v": 2, "total": 6})],
        )
    except ValueError as exc:
        assert "no resolvable duration" in str(exc)
    else:
        raise AssertionError("Missing effect duration should fail conversion")
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_editor_cache_registers_effect_spritesheets(tmp_path):
    from types import SimpleNamespace
    from convert_mod import _write_scenario_release_files

    scenario = tmp_path / "scenario"
    anim = SimpleNamespace(keyframes=[SimpleNamespace(animation="Idle.png")])
    effects = [
        SimpleNamespace(effect="hearts.png", sheet_data={"h": 3, "v": 2, "total": 6}),
        SimpleNamespace(effect="Impact_Fx.png", sheet_data={"h": 3, "v": 2, "total": 6}),
        SimpleNamespace(effect="cum_fx.png", sheet_data={"h": 6, "v": 4, "total": 24}),
    ]

    _write_scenario_release_files(str(scenario), anim, "Test", effects=effects)
    cache = (scenario / "editor_cache.cfg").read_text(encoding="utf-8")
    assert '"sprite_sheet": "Idle.png"' in cache
    assert '"sprite_sheet": "hearts.png"' in cache
    assert '"sprite_sheet": "Impact_Fx.png"' in cache
    assert '"sprite_sheet": "cum_fx.png"' in cache


def test_transition_sounds_are_written_as_sound_oneshot_only(tmp_path):
    from release_writer import write_release_keyframes
    from sound_fx_converter import TransitionSound

    out = tmp_path / "keyframes.cfg"
    write_release_keyframes(
        str(out),
        [],
        effects=[],
        sound_loops=[],
        sound_oneshot=[],
        voice_banks=[],
        transition_sounds=[TransitionSound(42, 5.25, "climax.ogg")],
    )
    text = out.read_text(encoding="utf-8")
    assert '"sound_oneshot"' in text
    assert '"path": "climax.ogg"' in text
    assert '"timestamp": 5.25' in text
    assert '"transition_sound"' not in text



def test_effect_pattern_override_resolves_impact_variants(monkeypatch):
    import effect_converter
    from models import Timeline

    old = effect_converter.OVERRIDES
    try:
        effect_converter.OVERRIDES = {
            "impact_*.png": {
                "sheet_data": {"h": 3, "v": 2, "total": 6},
                "duration": 0.5,
            }
        }
        parsed = {
            "bpm": 120,
            "note_offset": 0,
            "last_beat": 16,
            "initial_data": {},
            "transitions": {4: {"effects": "impact_1.png"}},
            "last_transition": {},
        }
        result = effect_converter.convert_effects(
            parsed, Timeline(120, 0, 16, []), assets_dir=None, interactive_sheets=False
        )
        assert result.keyframes[0].duration == 0.5
        assert result.keyframes[0].sheet_data == {"h": 3, "v": 2, "total": 6}
        assert not result.errors
    finally:
        effect_converter.OVERRIDES = old


def test_unknown_effect_without_override_remains_unresolved():
    import effect_converter
    from models import Timeline

    old = effect_converter.OVERRIDES
    try:
        effect_converter.OVERRIDES = {}
        result = effect_converter.convert_effects(
            {
                "bpm": 120,
                "note_offset": 0,
                "last_beat": 16,
                "initial_data": {},
                "transitions": {4: {"effects": "odd_fx.png"}},
                "last_transition": {},
            },
            Timeline(120, 0, 16, []),
            assets_dir=None,
            interactive_sheets=False,
        )
        assert result.keyframes[0].duration is None
    finally:
        effect_converter.OVERRIDES = old


def test_transition_sounds_are_merged_into_sound_oneshot(tmp_path):
    from release_writer import write_release_keyframes
    from sound_fx_converter import SoundFXTrigger, TransitionSound

    out = tmp_path / "keyframes.cfg"
    write_release_keyframes(
        str(out),
        [], [], [], [], [],
        sound_oneshot=[SoundFXTrigger(5, 5.0, "climax.ogg", "climax_sound")],
        voice_banks=[],
        transition_sounds=[TransitionSound(2, 2.0, "break.ogg", "transition")],
    )
    text = out.read_text(encoding="utf-8")
    assert '"sound_oneshot"' in text
    assert '"path": "climax.ogg"' in text
    assert '"path": "break.ogg"' in text
    assert '"transition_sound"' not in text
