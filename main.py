from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

from src.convert_mod import build_release_mod
from src.pyside_app import launch_gui


def ensure_config_dir():
    """Ensure a `config` directory exists next to the executable.

    If missing, create it and populate default files from the
    `src.defaults` package bundled with the application.
    """
    try:
        invoked = Path(sys.argv[0]).resolve()
        tempdir = Path(tempfile.gettempdir()).resolve()
        # When Nuitka/onefile runs, the program is extracted into a temporary
        # directory; placing `config/` next to that temp binary is undesirable.
        # Prefer the current working directory in that case so the config ends
        # up where the user executed the original executable.
        if tempdir in invoked.parents:
            base_dir = Path.cwd()
        else:
            base_dir = invoked.parent
    except Exception:
        base_dir = Path.cwd()

    cfg_dir = base_dir / "config"
    if not cfg_dir.exists():
        try:
            cfg_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            return

    names = ["chart.cfg", "effect_overrides.json", "sheet_overrides.json"]
    for name in names:
        target = cfg_dir / name
        if target.exists():
            continue
        # Try importlib.resources first (works when packaged)
        try:
            try:
                from importlib import resources

                data = resources.read_binary("src.defaults", name)
            except Exception:
                # Fallback to pkgutil
                from pkgutil import get_data

                data = get_data("src.defaults", name)

            if data:
                with open(target, "wb") as f:
                    f.write(data)
                continue
        except Exception:
            pass

        # As a final fallback, copy from a repo-local `config/` if present (useful during development)
        try:
            repo_src = Path(__file__).resolve().parent / "config" / name
            if repo_src.exists():
                import shutil

                shutil.copy(repo_src, target)
        except Exception:
            pass

    # If the effect converter already imported earlier, refresh its overrides
    # so it will see any newly-created config/effect_overrides.json file.
    try:
        import importlib
        ec = importlib.import_module("src.effect_converter")
        if hasattr(ec, "reload_overrides"):
            ec.reload_overrides()
    except Exception:
        pass



def main():
    ensure_config_dir()
    parser = argparse.ArgumentParser(description="Beat Banger Legacy -> Release converter")
    parser.add_argument("--gui", action="store_true", help="Open the PySide6 library GUI")
    parser.add_argument("input_mod", nargs="?", default="", help="Path to the Legacy mod folder")
    parser.add_argument("output_mod", nargs="?", default=None, help="Destination Release mod folder")
    parser.add_argument("--assets-dir", default=None, help="Assets directory. Defaults to input_mod.")
    parser.add_argument("--no-copy-assets", action="store_true", help="Do not copy referenced assets")
    parser.add_argument("--no-interactive", action="store_true", help="Skip interactive effect sheet prompts")
    parser.add_argument("--no-last-transition", action="store_true", help="Omit the final last_transition")
    parser.add_argument("--scenario-name", default=None, help="Optional scenario folder name")
    args = parser.parse_args()

    if args.gui:
        launch_gui()
        return 0

    if not args.input_mod:
        raise SystemExit("You must provide an input mod directory or use --gui to open the graphical interface.")

    input_mod = os.path.abspath(args.input_mod)
    output_mod = args.output_mod or (input_mod.rstrip(os.sep) + "_Release")
    summary, issues = build_release_mod(
        input_mod,
        output_mod,
        assets_dir=args.assets_dir,
        include_last_transition=not args.no_last_transition,
        copy_assets_flag=not args.no_copy_assets,
        scenario_name=args.scenario_name,
        interactive_sheets=not args.no_interactive,
    )
    print({"summary": summary, "issues": issues})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
