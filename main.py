from __future__ import annotations

import argparse
import os

from src.convert_mod import build_release_mod
from src.tkinter_app import launch_gui


def main():
    parser = argparse.ArgumentParser(description="Beat Banger Legacy -> Release converter")
    parser.add_argument("--gui", action="store_true", help="Open the Tkinter library GUI")
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
