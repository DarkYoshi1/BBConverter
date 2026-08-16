from pathlib import Path

from src.mod_library import discover_mods, load_settings, save_settings


def test_settings_round_trip(tmp_path):
    path = tmp_path / "settings.json"
    save_settings({"legacy_library": "/tmp/legacy-mods"}, path)
    assert load_settings(path)["legacy_library"] == "/tmp/legacy-mods"


def test_discover_mods_direct_children(tmp_path):
    root = tmp_path / "mods"
    root.mkdir()
    valid = root / "My Mod"
    valid.mkdir()
    (valid / "chart.cfg").write_text(
        'bpm = 120\nnote_offset = 0\nhalf_spawn = []\nquarter_spawn = []\neighth_spawn = []\nno_spawn = []\n'
        'initial_data = {"note_type": 0}\ntransitions = {}\nlast_beat = [10]\nname = "My Mod"\n',
        encoding="utf-8",
    )
    (valid / "meta.cfg").write_text('[META]\nmod_title = "Display Name"\n', encoding="utf-8")
    nested = root / "nested"
    nested.mkdir()
    (nested / "NotScanned" / "chart.cfg").parent.mkdir()
    (nested / "NotScanned" / "chart.cfg").write_text("", encoding="utf-8")

    mods = discover_mods(str(root))
    assert [m["name"] for m in mods] == ["Display Name"]
    assert Path(mods[0]["path"]) == valid.resolve()
