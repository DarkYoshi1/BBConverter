# Beat Banger Legacy → Release Converter

A local converter for transforming **Beat Banger Legacy mods** into the **Release mod layout** used by the game.

The project is designed around a conservative conversion philosophy: preserve information when its meaning is known, keep timing deterministic, resolve and copy referenced assets safely, and report information that cannot be verified instead of silently inventing data.

> **Current status:** **v1.0 stable release.** The recommended production entry point is `convert_mod.py`. `converter.py` is retained for the smaller/legacy conversion API and supporting workflows.

## v1.0

Version 1.0 is the first stable release of BBConverter.

The release provides the complete Legacy → Release conversion pipeline, including notes, animations, visual FX, backgrounds, audio, voice banks, metadata, asset handling, diagnostics, and the Legacy mod library GUI.

The project can be used directly from source or packaged as a standalone executable for distribution.

## Features

### Legacy → Release conversion

The converter can process and write:

* Notes and note state changes
* Animations and animation keyframes
* One-shot visual FX
* Background changes
* Sound loops
* One-shot audio
* Voice banks
* Metadata and Release configuration
* Referenced images and audio assets
* Conversion diagnostics

The Release writer generates the expected scenario structure, including `notes.cfg`, `keyframes.cfg`, `editor_cache.cfg`, metadata, settings, and asset directories.

### FX / sprite-sheet support

Legacy visual FX are treated as **one-shot sprite-sheet events**, not as looping animations.

An FX is written to `config/keyframes.cfg` under `effects` with:

```json
{
  "path": "hearts.png",
  "timestamp": 54.0,
  "duration": 0.5,
  "sheet_data": {
    "h": 3,
    "v": 2,
    "total": 6
  }
}
```

The FX image is also registered in `editor_cache.cfg`. This is important: merely copying the PNG into `images/` and referencing it from `keyframes.cfg` is not sufficient for the Release game to resolve and display the sprite sheet.

FX are **not** added to the animation `loops` list.

Because Legacy charts do not always store FX duration explicitly, `effect_overrides.json` contains verified overrides for known FX. Pattern-based overrides such as `impact_*.png` are supported.

Example:

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

Frame-specific durations are also supported:

```json
{
  "bra_rip.png": {
    "sheet_data": {
      "h": 3,
      "v": 2,
      "total": 6
    },
    "durations": {
      "54": 0.5,
      "110": 0.3
    }
  }
}
```

Known verified defaults currently include:

```text
6-frame FX   → 0.5 seconds
24-frame FX  → 4.0 seconds
```

These defaults are only used for recognized sheet layouts. Unknown layouts without a verified duration are reported instead of being assigned an arbitrary value.

### Audio mapping

Release does not use the Legacy `transition_sound` field as a separate output category.

The converter consolidates Legacy transition/climax one-shot sounds into Release `sound_oneshot`.

Conceptually:

```text
Legacy transition_sound ─┐
                         ├──> Release sound_oneshot
Legacy climax_sound ─────┘
```

Regular looping audio remains separate:

```text
Legacy sound_fx / loop data ──> Release sound_loop
```

The generated `keyframes.cfg` therefore does **not** emit a `transition_sound` section.

Example:

```json
"sound_oneshot": [
  {
    "path": "break.ogg",
    "timestamp": 7.5
  },
  {
    "path": "climax.ogg",
    "timestamp": 105.0
  }
]
```

The original timestamps are preserved.

### Voice banks

Voice banks support the Legacy representations handled by the parser, including:

* `name`
* `path`
* `voice_paths`
* Lists of voice-bank entries

An empty bank does **not** cause the converter to search the disk for arbitrary audio files.

If a voice bank was active and Legacy explicitly clears it, the Release output can contain:

```json
{
  "timestamp": 67.5,
  "voice_paths": []
}
```

Referenced voice files are copied to the Release `audio/` directory.

### Mod library GUI

The Tkinter GUI works as a small **Legacy mod library** rather than only as a conversion form.

Launch it with:

```bash
python tkinter_app.py --gui
```

or through the main conversion entry point:

```bash
python convert_mod.py --gui
```

The GUI provides:

* A `Choose folder` button for selecting the Legacy mod library root
* Persistent library-folder settings
* Automatic discovery of Legacy mods
* A 3-column grid of mod cards
* Mod thumbnails when available
* Mod title, artist, song information, and path
* A `Convert to Release` button on each mod
* `Refresh` for rescanning the library
* Background conversion so the interface does not need to block during conversion
* The same `build_release_mod()` conversion pipeline used by the CLI

The selected library root is stored at:

```text
~/.config/BeatBangerConverter7/settings.json
```

or, when `XDG_CONFIG_HOME` is set:

```text
$XDG_CONFIG_HOME/BeatBangerConverter7/settings.json
```

The library treats each **direct child directory** containing `chart.cfg` as a Legacy mod. This prevents unrelated nested folders from being accidentally interpreted as separate mods.

If the selected folder itself contains `chart.cfg`, it is treated as a single mod instead.

## Requirements

For running BBConverter from source:

* Python 3.10+
* Tkinter for the GUI
* Pillow for sprite-sheet inspection and thumbnails
* pytest for tests

Install Pillow:

```bash
python -m pip install Pillow
```

Install pytest:

```bash
python -m pip install pytest
```

On Arch Linux, Tkinter is normally provided by the `tk` package:

```bash
sudo pacman -S tk
```

### Standalone release

The v1.0 release can also be distributed as a compiled standalone executable.

End users running the compiled release do not need to install Python, Pillow, or pytest separately.

The Nuitka build instructions below are intended for developers who want to build the executable from source.

## Project structure

The project is organized into a source package, a configuration folder, and compatibility wrappers kept at the project root so existing scripts and imports continue to work.

```text
converter/
├── src/
│   ├── __init__.py
│   ├── animation_converter.py
│   ├── asset_resolver.py
│   ├── background_converter.py
│   ├── comparator.py
│   ├── converter.py
│   ├── convert_mod.py
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
│
├── config/
│   ├── chart.cfg
│   ├── effect_overrides.json
│   └── sheet_overrides.json
│
├── tests/
│   ├── run_converters_test.py
│   ├── test_animation_converter.py
│   ├── test_asset_checks.py
│   ├── test_full_conversion.py
│   ├── test_mod_library.py
│   ├── test_regressions.py
│   └── test_tkinter_gui.py
│
├── tools/
│   ├── batch_convert.py
│   └── generate_sheet_overrides.py
│
├── chart.cfg
├── effect_overrides.json
├── sheet_overrides.json
├── animation_converter.py
├── asset_resolver.py
├── background_converter.py
├── comparator.py
├── converter.py
├── convert_mod.py
├── debug.py
├── effect_converter.py
├── generate_examples.py
├── legacy_parser.py
├── mod_library.py
├── models.py
├── note_generator.py
├── release_writer.py
├── sound_fx_converter.py
├── sound_loop_converter.py
├── timeline.py
├── tkinter_app.py
├── validate_against_ground_truth.py
├── voice_bank_converter.py
├── README.md
└── .venv/
```

The root-level Python files are compatibility shims that re-export the real implementation from the `src/` package. Prefer importing from `src.*` in new code, while the root modules remain available for existing tooling and scripts.

## Basic CLI usage

The input must be a Legacy mod directory containing `chart.cfg`. `meta.cfg` is optional.

Convert a mod:

```bash
python convert_mod.py /path/to/legacy_mod /path/to/output
```

If no output path is provided, the converter creates a sibling directory with `_Release` appended:

```bash
python convert_mod.py /path/to/legacy_mod
```

### Use a separate asset directory

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

### Disable interactive FX sheet prompts

```bash
python convert_mod.py \
  /path/to/legacy_mod \
  /path/to/output \
  --no-interactive
```

### Omit `last_transition`

`last_transition` is included by default. To explicitly omit it:

```bash
python convert_mod.py \
  /path/to/legacy_mod \
  /path/to/output \
  --no-last-transition
```

### Set the Release scenario name

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

## Generated Release structure

A converted mod has this general structure:

```text
<Release mod>/
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

Visual assets are flattened into `images/` and audio assets into `audio/`. The converter validates this flattening process so two different source files cannot silently overwrite one another.

## Timing model

Legacy uses internal frames. The converter uses one shared `Timeline` for notes, animations, effects, audio, voice banks, and backgrounds.

The canonical conversion is:

```text
seconds_per_frame = 30 / BPM

timestamp = frame * seconds_per_frame - note_offset
```

In code, conversions should go through:

```python
Timeline.frame_to_timestamp(frame)
```

Negative timestamps are clamped to `0.0` because Release should not receive negative event times. A warning is recorded whenever this happens.

The inverse conversion used by helper tools is:

```text
frame = (timestamp + note_offset) / seconds_per_frame
```

### `last_beat`

When present, `last_beat` defines the final timeline boundary. If it is absent, the final frame is derived from the last known event.

`last_transition` represents the closing state of the level and is placed on the final timeline frame when enabled.

## Notes

Legacy note spawn arrays represent intervals rather than independent visual positions:

```text
half_spawn    → interval 4
quarter_spawn → interval 2
eighth_spawn  → interval 1
```

The current input mapping is:

```text
Legacy note_type 0 → Release input_type 0
Legacy note_type 1 → Release input_type 1
Legacy note_type 2 → Release input_type 2
Legacy note_type 3 → Release input_type 3
```

`note_modifier` remains `0` because this Legacy format does not provide a confirmed equivalent for the Release modifier field.

### `no_spawn`

`no_spawn` terminates the active spawn state. It does not create a note by itself.

Conceptually:

```text
quarter_spawn = [10]
no_spawn      = [20]
```

creates notes beginning at frame 10 using the active interval until frame 20.

### Note-state collisions

If mutually exclusive spawn states occur on the same frame, the converter reports a conversion error instead of silently pretending the chart is unambiguous.

The deterministic fallback precedence is:

```text
no_spawn > eighth_spawn > quarter_spawn > half_spawn
```

A chart with these collisions should be corrected before distribution.

## Animations

Animations are collected from:

```text
initial_data.animation
transitions[*].animation
last_transition.animation
```

A Release animation keyframe has the general form:

```json
{
  "animations": {
    "normal": "Idle.png"
  },
  "sheet_data": {
    "h": 3,
    "v": 2,
    "total": 6
  },
  "timestamp": 0.1
}
```

The default known layout for normal animations is `3 × 2`, for a total of `6` sprites. Confirmed exceptions can be added to `sheet_overrides.json`.

Consecutive duplicate animation states are removed.

## Effects configuration

Effect overrides live in:

```text
effect_overrides.json
```

Each entry may contain:

* `sheet_data`
* `duration`
* `durations`
* Comments for maintainers

For example:

```json
{
  "Impact_Fx.png": {
    "sheet_data": {
      "h": 3,
      "v": 2,
      "total": 6
    },
    "duration": 0.5
  }
}
```

Pattern keys such as `impact_*.png` are supported.

If the same FX needs different playback durations at different frames, use `durations`:

```json
{
  "bra_rip.png": {
    "durations": {
      "54": 0.5,
      "110": 0.3
    }
  }
}
```

The converter accepts interactive sheet inspection when Pillow is available. Use `--no-interactive` for automated conversion.

## Sound loops

Looping sound events are written separately from one-shot audio.

The converter distinguishes between:

```text
property absent             → keep the current loop state
property explicitly empty   → stop/clear the loop
```

This distinction prevents a missing Legacy property from accidentally stopping a loop.

`last_transition` audio is processed as well.

## Backgrounds

Backgrounds can be read from:

```text
initial_data.background
transitions[*].background
last_transition.background
```

Supported representations include simple paths, list-based data, and object-based data with fields such as `path` and `static`.

Consecutive identical background states are deduplicated.

## Asset resolution and safety

Asset resolution is centralized in `asset_resolver.py`.

The resolver:

* Checks common paths first
* Supports basename fallback searches
* Performs case-insensitive matching
* Works with mods created on case-insensitive filesystems and converted on Linux
* Rejects `../` references that escape the asset root
* Avoids silently choosing arbitrary files when the reference is ambiguous

Common supported formats include:

```text
Images: .png .jpg .jpeg .webp
Audio:  .ogg .wav .mp3 .flac
```

### Asset flattening

Release assets are stored as:

```text
images/
audio/
```

If two different source files would produce the same basename, the converter checks their contents.

* Identical files may safely reuse the existing copy.
* Different files produce an asset conflict.
* Existing files are never silently overwritten by a different source file.

Conversion summaries include:

```text
copied_assets_count
missing_assets_count
asset_conflicts_count
```

## Metadata and IDs

When available, Legacy `meta.cfg` can provide information such as:

```text
mod_title
mod_creator / mod_artist
song_artist
song_title
length
```

The converter only maps fields with a verified Release correspondence. Unsupported fields are not invented.

### Deterministic `level_id`

Legacy does not provide the exact Release `level_id` used by the current Release structure handled by this project.

The converter therefore generates a deterministic MD5 based on:

```text
level_name + newline + song_path
```

Converting the same level/song combination repeatedly produces the same generated ID.

## Settings and note offset

Legacy `note_offset` is already incorporated into generated timestamps.

Therefore the generated Release `settings.cfg` uses:

```json
"song_offset": 0.0
```

This prevents applying the same offset twice.

Other Legacy settings are not automatically written into unverified Release fields. When a value has no confirmed destination, the converter reports a warning rather than inventing a schema.

## Diagnostics

A conversion creates a debug report named similar to:

```text
<output>_conversion_debug.txt
```

Diagnostics can include:

* BPM
* `note_offset`
* `last_beat`
* seconds per frame
* note state changes
* note collisions
* note counts
* FX counts
* audio counts
* voice-bank counts
* copied assets
* missing assets
* asset conflicts
* warnings
* errors

The conversion pipeline also returns structured summary/issue information to the GUI and CLI.

If a conversion fails, the GUI should expose the actual exception/diagnostic instead of reducing it to an unhelpful generic message.

## Batch conversion

To convert multiple Legacy mods below a root folder:

```bash
python tools/batch_convert.py /path/to/library /path/to/output
```

Available options include:

```text
--no-copy-assets
--no-last-transition
```

The batch tool uses the active Python interpreter rather than assuming a particular Python executable name.

## `converter.py` compatibility API

`converter.py` is retained for older/smaller workflows and exposes helpers such as:

```python
convert_notes(parsed)
convert(...)
validate_notes(...)
validate_keyframes(...)
```

For a complete Legacy → Release mod conversion, use:

```text
convert_mod.py
```

because it coordinates parsing, timeline conversion, effects, audio, voice banks, backgrounds, assets, metadata, Release structure, and diagnostics.

## Comparing against a known Release mod

`comparator.py` and `validate_against_ground_truth.py` are available for comparing generated Release data against known-good Release mods.

This is especially important when Legacy does not explicitly encode a property and the Release format requires information that must be verified from real reference mods.

Unit tests validate structure and internal consistency, but a real Legacy/Release comparison remains the strongest way to confirm semantic compatibility.

## Testing

Run the full test suite with:

```bash
pytest -q
```

Current suite status:

```text
30 passed
```

The tests cover, among other things:

* Shared timeline conversion
* Notes and note-state transitions
* `no_spawn`
* `last_transition`
* Animation conversion
* FX sheet data and durations
* FX registration in `editor_cache.cfg`
* One-shot audio mapping
* Absence of Release `transition_sound`
* Sound loops
* Voice-bank parsing and asset copying
* Background conversion
* Metadata and deterministic IDs
* Case-insensitive asset resolution
* Path traversal protection
* Asset collision detection
* Mod-library discovery
* GUI/library behavior
* Full conversion paths

Run the converter-focused helper tests with:

```bash
python tests/run_converters_test.py
```

## Building standalone executables with Nuitka

The project can be packaged as native executables for Linux and Windows.

Nuitka is **not a cross-compiler** for this workflow. Build the Linux executable on Linux and the Windows executable on Windows.

The v1.0 release is already compiled. These instructions are provided for developers who want to reproduce or modify the build.

### Linux

On Arch Linux, install the required system tools:

```bash
sudo pacman -S gcc patchelf tk
```

Create/activate a virtual environment and install the Python build dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U "Nuitka[app]" Pillow
```

Check Nuitka:

```bash
python -m nuitka --version
```

First build `standalone`:

```bash
python -m nuitka \
  --mode=standalone \
  --follow-imports \
  --include-package=PIL \
  --output-dir=build \
  tkinter_app.py
```

Test the generated application before using onefile mode:

```bash
./build/tkinter_app.dist/tkinter_app.bin
```

After standalone has been verified, build a single executable:

```bash
python -m nuitka \
  --mode=onefile \
  --follow-imports \
  --include-package=PIL \
  --output-dir=build \
  --output-filename=BeatBangerConverter \
  tkinter_app.py
```

The resulting Linux executable is:

```text
build/BeatBangerConverter
```

### Windows

Build the Windows executable on Windows. Install Python and a C/C++ toolchain such as Visual Studio Build Tools with the C++ workload.

Create the environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U "Nuitka[app]" Pillow
```

Test standalone first:

```powershell
python -m nuitka `
  --mode=standalone `
  --follow-imports `
  --include-package=PIL `
  --output-dir=build `
  tkinter_app.py
```

Run:

```powershell
.\build\tkinter_app.dist\tkinter_app.exe
```

Then build onefile:

```powershell
python -m nuitka `
  --mode=onefile `
  --follow-imports `
  --include-package=PIL `
  --output-dir=build `
  --output-filename=BeatBangerConverter.exe `
  tkinter_app.py
```

The Windows executable will be:

```text
build/BeatBangerConverter.exe
```

### Why build standalone first?

`standalone` makes missing modules and data files easier to diagnose. Once it works correctly, `onefile` can be used for distribution.

Pillow is explicitly included because the converter uses PIL for image/sprite-sheet operations and dynamically loaded Pillow components may otherwise be omitted from a compiled application.

The user's mod-library settings are intentionally kept outside the executable under the user's configuration directory. They must remain writable and persistent between runs.

## Recommended development workflow

When adding support for another Legacy field:

```text
Legacy reference mod
        ↓
Inspect actual chart.cfg / assets
        ↓
Compare with a known-good Release mod
        ↓
Implement parser/converter change
        ↓
Add regression test
        ↓
Run full pytest suite
        ↓
Run a real Legacy → Release conversion
        ↓
Test the generated mod in Beat Banger
```

Do not infer a Release field solely from its name. When the Legacy format and Release format differ, use real working mods to establish the mapping.

## Current limitations

Some Release information cannot be reconstructed perfectly from Legacy alone.

Examples include:

* FX durations that are not represented in Legacy
* Release-only metadata without a Legacy equivalent
* Creative/editor settings that have no confirmed Release destination
* Unknown sprite-sheet layouts
* Missing or ambiguous source assets

The converter intentionally reports these cases instead of silently fabricating data.

A conversion with zero errors means the converter did not find a structural contradiction that prevented generation. It does **not** prove that every visual/audio detail is semantically identical to an original Release mod. Testing the generated mod in-game remains necessary.

## Conversion pipeline

The main pipeline is:

```text
Legacy mod
    ↓
legacy_parser.py
    ↓
Timeline
    ↓
notes / animations / effects / audio / voice banks / backgrounds
    ↓
asset resolution + validation
    ↓
asset copying
    ↓
Release writers
    ↓
notes.cfg + keyframes.cfg + editor_cache.cfg + metadata + settings
    ↓
diagnostics
    ↓
Release mod
```

The goal is a reproducible and auditable Legacy → Release conversion process rather than a converter that silently guesses when the source data is ambiguous.

## License

See the repository for the applicable license information.

## Credits

BBConverter is an independent community tool created to make the transition from Beat Banger Legacy mods to Release mods easier.
