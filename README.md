# Beat Banger Legacy → Release Converter

This project converts Beat Banger Legacy mods into the Release mod structure used by the game. The main principle is to keep only information that has a verifiable source, keep timing deterministic, and report ambiguous cases instead of inventing values without evidence.

The recommended entry point is `convert_mod.py`, although the project also includes a Tkinter-based graphical interface for browsing a Legacy mod library and converting mods from a library view.

## Current status

The project is aimed at a functional and conservative conversion workflow:

- reading `chart.cfg` and `meta.cfg`
- shared timeline calculation for notes, animations, effects, audio, and backgrounds
- generation of `notes.cfg`, `keyframes.cfg`, `editor_cache.cfg`, `meta.cfg`, `mod.cfg`, `settings.cfg`, and related files
- copying and validating image/audio assets
- GUI support for browsing and converting multiple mods from a folder
- detailed diagnostics with warnings, errors, and final summaries

## What it converts

The current pipeline covers:

- notes and note-state transitions
- animations and keyframes
- sprite-sheet visual effects
- backgrounds
- audio loops
- one-shot audio events
- voice banks
- Release metadata and config
- safe copying of referenced assets

The output is structured as a Release mod with a scenario folder and the expected configuration files.

## Requirements

You need Python 3.10 or newer.

Core dependencies:

- Python 3.10+
- Tkinter for the GUI
- Pillow for sprite-sheet inspection and thumbnails
- pytest for running tests

Recommended installation:

```bash
python -m pip install Pillow pytest
```

On Arch Linux, Tkinter is usually provided by the `tk` package:

```bash
sudo pacman -S tk
```

## Project structure

```text
converter/
├── README.md
├── main.py
├── convert_mod.py
├── tkinter_app.py
├── chart.cfg
├── effect_overrides.json
├── sheet_overrides.json
├── config/
│   ├── chart.cfg
│   ├── effect_overrides.json
│   └── sheet_overrides.json
├── src/
│   ├── __init__.py
│   ├── animation_converter.py
│   ├── asset_resolver.py
│   ├── background_converter.py
│   ├── comparator.py
│   ├── convert_mod.py
│   ├── converter.py
│   ├── debug.py
│   ├── effect_converter.py
│   ├── generate_examples.py
│   ├── legacy_parser.py
│   ├── mod_library.py
│   ├── models.py
│   ├── note_generator.py
│   ├── release_writer.py
│   ├── sound_fx_converter.py
│   ├── sound_loop_converter.py
│   ├── timeline.py
│   ├── tkinter_app.py
│   ├── validate_against_ground_truth.py
│   └── voice_bank_converter.py
├── tests/
│   ├── conftest.py
│   ├── run_converters_test.py
│   ├── test_animation_converter.py
│   ├── test_asset_checks.py
│   ├── test_full_conversion.py
│   ├── test_mod_library.py
│   ├── test_regressions.py
│   └── test_tkinter_gui.py
├── tools/
│   ├── batch_convert.py
│   └── generate_sheet_overrides.py
└── .venv/
```

Files in the project root are compatibility shims to preserve older scripts; the main implementation lives under `src/`.

## Command-line usage

The input must be a Legacy mod folder containing `chart.cfg`. `meta.cfg` is optional.

### Basic conversion

```bash
python convert_mod.py /path/to/legacy_mod /path/to/output
```

If no output path is provided, a sibling folder with the `_Release` suffix is created:

```bash
python convert_mod.py /path/to/legacy_mod
```

### Use a separate assets directory

```bash
python convert_mod.py \
  /path/to/legacy_mod \
  /path/to/output \
  --assets-dir /path/to/assets
```

### Do not copy assets

```bash
python convert_mod.py \
  /path/to/legacy_mod \
  /path/to/output \
  --no-copy-assets
```

### Disable interactive FX sprite-sheet prompts

```bash
python convert_mod.py \
  /path/to/legacy_mod \
  /path/to/output \
  --no-interactive
```

### Omit `last_transition`

```bash
python convert_mod.py \
  /path/to/legacy_mod \
  /path/to/output \
  --no-last-transition
```

### Customize the Release scenario name

```bash
python convert_mod.py \
  /path/to/legacy_mod \
  /path/to/output \
  --scenario-name "Girl Brat"
```

### Open the GUI from the main entry point

```bash
python convert_mod.py --gui
```

## Mod library GUI

The Tkinter GUI behaves like a small Legacy mod library rather than only a conversion form.

It can be launched with:

```bash
python tkinter_app.py --gui
```

or from the main entry point:

```bash
python convert_mod.py --gui
```

The interface allows:

- choosing a root folder containing Legacy mods
- saving the library path persistently
- automatically discovering mods
- showing cards with thumbnails, name, artist, song, and path
- converting each mod with a single click
- refreshing the library
- running conversion in the background without blocking the UI

The configuration path is stored in:

```text
~/.config/BeatBangerConverter7/settings.json
```

or in:

```text
$XDG_CONFIG_HOME/BeatBangerConverter7/settings.json
```

when `XDG_CONFIG_HOME` is defined.

## Generated Release output structure

The converter generates a structure like this:

```text
<mod_release>/
├── act.cfg
├── meta.cfg
├── thumb.png
└── <scenario>/
    ├── editor_cache.cfg
    ├── meta.cfg
    ├── thumb.png
    ├── audio/
    ├── images/
    └── config/
        ├── asset.cfg
        ├── keyframes.cfg
        ├── meta.cfg
        ├── mod.cfg
        ├── notes.cfg
        └── settings.cfg
```

Assets are flattened automatically into `images/` and `audio/`, and the converter validates that no name collisions occur silently.

## Timing model

The project uses a shared `Timeline` for notes, animations, effects, audio, backgrounds, and voice banks.

Frame-to-timestamp conversion is centralized as:

```python
seconds_per_frame = 30 / BPM
timestamp = frame * seconds_per_frame - note_offset
```

The project converts through the Timeline to keep behavior consistent. Negative timestamps are clamped to `0.0`, with a warning recorded when this happens.

Legacy `note_offset` is already folded into the generated timestamps, and the output `settings.cfg` uses:

```json
"song_offset": 0.0
```

to avoid applying the offset twice.

## Notes and spawn states

The converter handles `half_spawn`, `quarter_spawn`, `eighth_spawn`, and `no_spawn` with deterministic precedence when collisions occur:

```text
no_spawn > eighth_spawn > quarter_spawn > half_spawn
```

If the chart contains mutually incompatible states on the same frame, conversion records an error instead of assuming an arbitrary interpretation.

## Animations and FX

Animations are collected from:

- `initial_data.animation`
- `transitions[*].animation`
- `last_transition.animation`

Legacy visual effects are treated as one-shot sprite-sheet events rather than loops.

The system uses `effect_overrides.json` to define known layouts and durations and supports patterns such as:

```json
{
  "impact_*.png": {
    "sheet_data": {
      "h": 3,
      "v": 2,
      "total": 6
    },
    "duration": 0.5
  }
}
```

Frame-specific durations are also supported when an effect behaves differently depending on when it is triggered.

## Audio, voice banks, and backgrounds

The converter distinguishes between:

- `sound_fx` / loops
- `transition_sound` / `climax_sound` converted to `sound_oneshot`
- voice banks with real file resolution and path handling
- backgrounds represented as simple paths, lists, or objects

The system tries to preserve the semantics of the Legacy chart without inventing Release fields that do not have a confirmed mapping.

## Asset resolution and safety

The project centralizes asset resolution in `src/asset_resolver.py`.

Resolution behavior:

- checks common paths first
- supports basename fallback lookup
- compares case-insensitively
- works with mods created on case-insensitive filesystems and converted on Linux
- rejects `../` references that escape the asset root
- avoids arbitrary decisions when the reference is ambiguous

The final asset copy step validates:

- file-name conflicts
- missing files
- identical duplicates that may be reused
- different files with the same name that trigger an error instead of being silently overwritten

## Diagnostics

Each conversion generates a debug log similar to:

```text
<output>_conversion_debug.txt
```

It includes useful information such as:

- BPM
- `note_offset`
- `last_beat`
- seconds per frame
- note counts
- note-state changes
- collisions
- generated FX
- loops and one-shots
- voice banks
- copied and missing assets
- warnings and errors

The CLI and GUI both receive structured summary data from this process.

## Tests

The project includes conversion and validation tests. To run the full suite:

```bash
pytest -q
```

There is also a conversion helper suite:

```bash
python tests/run_converters_test.py
```

## Standalone build with Nuitka

The project can be packaged as native executables.

Example for Linux:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U "Nuitka[app]" Pillow
python -m nuitka --mode=standalone --follow-imports --include-package=PIL --output-dir=build tkinter_app.py
```

On Windows:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U "Nuitka[app]" Pillow
python -m nuitka --mode=standalone --follow-imports --include-package=PIL --output-dir=build tkinter_app.py
```

The goal is to prepare a self-contained binary, though the main development flow remains source-based Python execution.

## Recommended development workflow

When adding support for another Legacy property:

1. compare with a real Legacy mod
2. verify the corresponding format in a Release mod reference
3. implement the conversion in the parser or converter
4. add a regression test
5. run the relevant suite
6. convert a real mod and verify the result

## Known limitations

Not everything in Release can be reconstructed exactly from Legacy alone. For example:

- effect durations with no clear representation in Legacy
- Release metadata with no confirmed equivalent
- creative settings that do not have a validated destination
- unknown sprite-sheet layouts
- missing or ambiguous assets

When this happens, the converter reports the case instead of inventing a result.

## License

See the repository for the applicable license information.

## Credits

Beat Banger Legacy → Release Converter is an independent project created to make the transition from Beat Banger Legacy mods to the Release format easier.

Consulta el repositorio para ver la licencia aplicable.

## Créditos

Beat Banger Legacy → Release Converter es una herramienta independiente para facilitar la transición desde mods legacy al formato Release del juego.
