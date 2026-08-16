import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

LEGACY_ALIASES = {
    "background_converter": "src.background_converter",
    "animation_converter": "src.animation_converter",
    "asset_resolver": "src.asset_resolver",
    "comparator": "src.comparator",
    "converter": "src.converter",
    "convert_mod": "src.convert_mod",
    "debug": "src.debug",
    "effect_converter": "src.effect_converter",
    "generate_examples": "src.generate_examples",
    "legacy_parser": "src.legacy_parser",
    "mod_library": "src.mod_library",
    "models": "src.models",
    "note_generator": "src.note_generator",
    "release_writer": "src.release_writer",
    "sound_fx_converter": "src.sound_fx_converter",
    "sound_loop_converter": "src.sound_loop_converter",
    "timeline": "src.timeline",
    "tkinter_app": "src.tkinter_app",
    "validate_against_ground_truth": "src.validate_against_ground_truth",
    "voice_bank_converter": "src.voice_bank_converter",
}

for alias, target in LEGACY_ALIASES.items():
    try:
        module = importlib.import_module(target)
    except Exception:
        continue
    sys.modules[alias] = module
    if target.startswith("src."):
        sys.modules[target] = module
