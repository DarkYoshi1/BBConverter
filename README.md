# Beat Banger Legacy → Release Converter

This project converts Legacy Beat Banger mods into the Release mod layout used by the game. The implementation is organized around a small root entry point and a dedicated `src/` package, while examples and runtime defaults live under the project root.

## Project layout

```text
converter/
├── README.md
├── main.py
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
├── .venv/
├── build/
├── .pytest_cache/
└── __pycache__/
```

The main logic lives under `src/`. The root-level `main.py` is the current CLI entry point and delegates to `src.convert_mod` and `src.tkinter_app`.

## Requirements

- Python 3.10+
- Tkinter for the GUI
- Pillow for sprite-sheet inspection and thumbnails
- pytest for running tests

Install dependencies:

```bash
python -m pip install Pillow pytest
```

On Arch Linux, Tkinter is usually provided by the `tk` package:

```bash
sudo pacman -S tk
```

## Usage

The input must be a Legacy mod folder containing `chart.cfg`. `meta.cfg` is optional.

### Basic conversion

```bash
python main.py /path/to/legacy_mod /path/to/output
```

If no output path is provided, a sibling folder with the `_Release` suffix is created:

```bash
python main.py /path/to/legacy_mod
```

### Separate assets directory

```bash
python main.py \
  /path/to/legacy_mod \
  /path/to/output \
  --assets-dir /path/to/assets
```

### Skip asset copying

```bash
python main.py \
  /path/to/legacy_mod \
  /path/to/output \
  --no-copy-assets
```

### Disable interactive effect sheet prompts

```bash
python main.py \
  /path/to/legacy_mod \
  /path/to/output \
  --no-interactive
```

### Omit `last_transition`

```bash
python main.py \
  /path/to/legacy_mod \
  /path/to/output \
  --no-last-transition
```

### Customize the scenario folder name

```bash
python main.py \
  /path/to/legacy_mod \
  /path/to/output \
  --scenario-name "Girl Brat"
```

### Open the GUI

```bash
python main.py --gui
```

## GUI / mod library

The Tkinter interface operates as a small mod library and conversion dashboard:

- choose a folder containing multiple Legacy mods
- persist the library path in user config
- discover mods automatically
- view conversion cards with thumbnails and metadata
- convert individual mods from the library view
- refresh the list and keep the UI responsive while conversion runs in the background

The library settings are stored under:

```text
~/.config/BeatBangerConverter7/settings.json
```

or:

```text
$XDG_CONFIG_HOME/BeatBangerConverter7/settings.json
```

when `XDG_CONFIG_HOME` is defined.

## What the converter handles

The current pipeline covers:

- notes and their state transitions
- animations and keyframes
- sprite-sheet visual effects
- backgrounds
- audio loops and one-shot events
- voice banks
- Release metadata and configuration files
- validation and safe copying of referenced assets

The generated Release output keeps the scenario folder structure expected by the game and flattens asset files into the corresponding `images/` and `audio/` directories.

## Timing model

The converter uses a shared timeline for notes, animations, effects, audio, backgrounds, and voice banks. The frame-to-time conversion follows the same rule across the pipeline:

```python
seconds_per_frame = 30 / BPM
timestamp = frame * seconds_per_frame - note_offset
```

Negative timestamps are clamped to `0.0` and recorded as warnings when needed. The generated `settings.cfg` intentionally keeps `song_offset` at `0.0` to avoid double-applying the Legacy offset.

## Diagnostics and validation

Each conversion produces a debug log such as:

```text
<output>_conversion_debug.txt
```

It includes details such as:

- BPM and note offset
- last beat and timeline data
- counts of notes and state changes
- colliding spawn states and warnings
- generated effects and loops
- copied vs. missing assets
- voice-bank resolution details
- summary of conversion issues

## Tests

Run the project test suite with:

```bash
pytest -q
```

The conversion helper script is also available:

```bash
python tests/run_converters_test.py
```

## Build notes

The project can be packaged with Nuitka for standalone execution.

Example for Linux:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U "Nuitka[app]" Pillow
python -m nuitka --mode=standalone --follow-imports --include-package=PIL --output-dir=build main.py
```

On Windows:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U "Nuitka[app]" Pillow
python -m nuitka --mode=standalone --follow-imports --include-package=PIL --output-dir=build main.py
```

## Development workflow

When adding support for a new Legacy property:

1. compare against a real mod and the corresponding Release format
2. implement the conversion in the relevant parser or converter
3. add a regression test covering the behavior
4. run the focused validation suite
5. verify the result on a real mod sample

## Known limitations

Some Release fields cannot be reconstructed exactly from Legacy data alone. In those cases the converter intentionally records the uncertainty instead of inventing unsupported values.

## License

See the repository for the applicable license information.
