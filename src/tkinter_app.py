from __future__ import annotations

import argparse
import os
import threading
import traceback
from typing import Optional


def build_arg_parser():
    p = argparse.ArgumentParser(description="Beat Banger Legacy -> Release conversion GUI")
    p.add_argument("--gui", action="store_true", help="Launch the Tkinter conversion interface")
    p.add_argument("input_mod", nargs="?", default="",
                   help="Path to the Legacy mod folder (containing chart.cfg)")
    p.add_argument("output_mod", nargs="?", default=None,
                   help="Where to write the Release mod. Defaults to '<input_mod>_Release' next to the input.")
    p.add_argument("--assets-dir", default=None,
                   help="Only needed if Legacy assets live outside input_mod. Defaults to input_mod.")
    p.add_argument("--no-copy-assets", action="store_true")
    p.add_argument("--no-interactive", action="store_true",
                   help="Don't prompt for effect sprite sheet layout (falls back to overrides/warnings only)")
    p.add_argument("--no-last-transition", action="store_true",
                   help="Omit last_transition from the final timeline frame")
    p.add_argument("--scenario-name", default=None,
                   help="Name for the single scenario folder (defaults to the Legacy chart's 'name' field)")
    return p


def _default_output_for(input_mod: str) -> str:
    if not input_mod:
        return ""
    input_mod = os.path.abspath(input_mod)
    return input_mod.rstrip(os.sep) + "_Release"


def _run_conversion_worker(app, input_mod: str, output_mod: str, assets_dir: Optional[str],
                          no_copy_assets: bool, no_interactive: bool,
                          include_last_transition: bool, scenario_name: Optional[str],
                          on_done=None):
    try:
        from .convert_mod import build_release_mod

        output_mod = output_mod or _default_output_for(input_mod)
        summary, issues = build_release_mod(
            input_mod,
            output_mod,
            assets_dir=assets_dir,
            include_last_transition=include_last_transition,
            copy_assets_flag=not no_copy_assets,
            scenario_name=scenario_name,
            interactive_sheets=not no_interactive,
        )

        def finish():
            app.log_box.insert("end", "\n=== Conversion completed ===\n")
            app.log_box.insert("end", "Summary:\n" + str(summary) + "\n")
            app.log_box.insert("end", "Warnings/errors:\n" + str(issues) + "\n")
            app.log_box.see("end")
            if on_done:
                on_done()

        app.after(0, finish)
    except Exception as exc:
        error_text = traceback.format_exc()
        error_summary = f"{type(exc).__name__}: {exc}"

        def fail():
            app.log_box.insert("end", "\n=== Conversion failed ===\n")
            app.log_box.insert("end", error_summary + "\n\n")
            app.log_box.insert("end", error_text + "\n")
            app.log_box.see("end")
            try:
                app.convert_button.config(state="normal")
            except Exception:
                pass
            if on_done:
                on_done()
        app.after(0, fail)


def launch_gui():
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError as exc:  # pragma: no cover - environment-specific
        raise RuntimeError("Tkinter is not available in this Python installation") from exc

    from .mod_library import discover_mods, load_settings, save_settings

    root = tk.Tk()
    root.title("Beat Banger Legacy → Release Converter")
    root.geometry("1050x720")
    root.minsize(850, 560)

    settings = load_settings()
    saved_root = str(settings.get("legacy_library") or "")

    tk_vars = {
        "library_root": tk.StringVar(value=saved_root),
        "assets_dir": tk.StringVar(),
        "scenario_name": tk.StringVar(),
        "no_copy_assets": tk.BooleanVar(value=False),
        "no_interactive": tk.BooleanVar(value=False),
        "include_last_transition": tk.BooleanVar(value=True),
        "status": tk.StringVar(value="Select a Legacy mods folder."),
    }

    selected_photo_refs = []

    outer = ttk.Frame(root, padding=12)
    outer.pack(fill="both", expand=True)
    outer.columnconfigure(0, weight=1)
    outer.rowconfigure(2, weight=1)
    outer.rowconfigure(3, weight=1)

    header = ttk.Frame(outer)
    header.grid(row=0, column=0, sticky="ew")
    header.columnconfigure(1, weight=1)

    ttk.Label(header, text="Legacy mods folder").grid(row=0, column=0, padx=(0, 8), pady=4, sticky="w")
    library_entry = ttk.Entry(header, textvariable=tk_vars["library_root"])
    library_entry.grid(row=0, column=1, padx=4, pady=4, sticky="ew")

    def refresh_mods():
        root_path = tk_vars["library_root"].get().strip()
        if not root_path:
            messagebox.showerror("Missing folder", "Select the folder that contains your Legacy mods first.")
            return
        if not os.path.isdir(root_path):
            messagebox.showerror("Invalid folder", "The selected Legacy mods folder does not exist.")
            return
        settings["legacy_library"] = os.path.abspath(root_path)
        try:
            save_settings(settings)
        except OSError as exc:
            messagebox.showwarning("Settings", f"Could not save the selected folder:\n{exc}")

        mods = discover_mods(root_path)
        render_mod_grid(mods)
        tk_vars["status"].set(f"Found {len(mods)} Legacy mod(s) in {os.path.abspath(root_path)}")

    def choose_library():
        path = filedialog.askdirectory(title="Select Legacy mods folder")
        if path:
            tk_vars["library_root"].set(path)
            refresh_mods()

    ttk.Button(header, text="Choose folder", command=choose_library).grid(row=0, column=2, padx=4, pady=4)
    ttk.Button(header, text="Refresh", command=refresh_mods).grid(row=0, column=3, padx=4, pady=4)

    options = ttk.LabelFrame(outer, text="Conversion options", padding=8)
    options.grid(row=1, column=0, sticky="ew", pady=(8, 8))
    ttk.Checkbutton(options, text="Skip copying assets", variable=tk_vars["no_copy_assets"]).pack(side="left", padx=(0, 14))
    ttk.Checkbutton(options, text="Skip interactive sheet prompts", variable=tk_vars["no_interactive"]).pack(side="left", padx=(0, 14))
    ttk.Checkbutton(options, text="Include final last_transition", variable=tk_vars["include_last_transition"]).pack(side="left")

    grid_frame = ttk.LabelFrame(outer, text="Legacy mods", padding=8)
    grid_frame.grid(row=2, column=0, sticky="nsew")
    grid_frame.columnconfigure(0, weight=1)
    grid_frame.rowconfigure(0, weight=1)

    canvas = tk.Canvas(grid_frame, highlightthickness=0)
    scrollbar = ttk.Scrollbar(grid_frame, orient="vertical", command=canvas.yview)
    cards_host = ttk.Frame(canvas)
    cards_host.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=cards_host, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")
    grid_frame.bind("<Configure>", lambda e: canvas.itemconfigure(1, width=max(1, e.width - 12)))

    log_frame = ttk.LabelFrame(outer, text="Activity", padding=8)
    log_frame.grid(row=3, column=0, sticky="nsew", pady=(8, 0))
    log_frame.columnconfigure(0, weight=1)
    log_frame.rowconfigure(0, weight=1)
    log_box = tk.Text(log_frame, height=9, wrap="word")
    log_box.grid(row=0, column=0, sticky="nsew")
    root.log_box = log_box

    status = ttk.Label(outer, textvariable=tk_vars["status"], anchor="w")
    status.grid(row=4, column=0, sticky="ew", pady=(6, 0))

    def convert_mod(mod_info):
        input_mod = str(mod_info["path"])
        output_mod = _default_output_for(input_mod)
        root.log_box.insert("end", f"\nStarting conversion for: {input_mod}\n")
        root.log_box.insert("end", f"Output: {output_mod}\n")
        root.log_box.see("end")
        status_var_before = tk_vars["status"].get()
        tk_vars["status"].set(f"Converting {mod_info['name']}...")

        def done():
            tk_vars["status"].set(status_var_before or "Conversion finished.")
            refresh_mods()

        thread = threading.Thread(
            target=_run_conversion_worker,
            args=(
                root,
                input_mod,
                output_mod,
                tk_vars["assets_dir"].get().strip() or None,
                tk_vars["no_copy_assets"].get(),
                tk_vars["no_interactive"].get(),
                tk_vars["include_last_transition"].get(),
                tk_vars["scenario_name"].get().strip() or None,
                done,
            ),
            daemon=True,
        )
        thread.start()

    def make_card(parent, mod_info):
        card = ttk.Frame(parent, relief="ridge", borderwidth=1, padding=8)
        card.columnconfigure(1, weight=1)

        thumb = None
        thumb_path = mod_info.get("thumb")
        if thumb_path:
            try:
                thumb = tk.PhotoImage(file=str(thumb_path))
                # Keep a visible reference on both card and app-level storage.
                selected_photo_refs.append(thumb)
            except Exception:
                thumb = None
        if thumb is not None:
            max_w, max_h = 128, 96
            scale_x = max(1, (thumb.width() + max_w - 1) // max_w)
            scale_y = max(1, (thumb.height() + max_h - 1) // max_h)
            scale = max(scale_x, scale_y)
            if scale > 1:
                thumb = thumb.subsample(scale, scale)
                selected_photo_refs.append(thumb)
            ttk.Label(card, image=thumb).grid(row=0, column=0, rowspan=4, padx=(0, 10), sticky="n")
        else:
            ttk.Label(card, text="No\nthumbnail", anchor="center", width=14, relief="groove").grid(
                row=0, column=0, rowspan=4, padx=(0, 10), sticky="n")

        ttk.Label(card, text=str(mod_info["name"]), font=("TkDefaultFont", 11, "bold")).grid(
            row=0, column=1, sticky="w")
        subtitle = str(mod_info.get("song_title") or mod_info.get("artist") or "Legacy mod")
        ttk.Label(card, text=subtitle).grid(row=1, column=1, sticky="w", pady=(2, 0))
        ttk.Label(card, text=str(mod_info["path"]), wraplength=280).grid(row=2, column=1, sticky="w", pady=(4, 6))
        ttk.Button(card, text="Convert to Release", command=lambda: convert_mod(mod_info)).grid(
            row=3, column=1, sticky="w")
        return card

    def render_mod_grid(mods):
        nonlocal selected_photo_refs
        selected_photo_refs = []
        for child in cards_host.winfo_children():
            child.destroy()

        if not mods:
            ttk.Label(cards_host, text="No Legacy mods found. Each mod should be a folder containing chart.cfg.").grid(
                row=0, column=0, padx=12, pady=18, sticky="w")
            return

        columns = 3
        for index, mod_info in enumerate(mods):
            row, column = divmod(index, columns)
            card = make_card(cards_host, mod_info)
            card.grid(row=row, column=column, sticky="nsew", padx=6, pady=6)
            cards_host.columnconfigure(column, weight=1, uniform="mod")
        for row in range((len(mods) + columns - 1) // columns):
            cards_host.rowconfigure(row, weight=0)

    root.convert_button = None
    root.log_box = log_box

    if saved_root and os.path.isdir(saved_root):
        refresh_mods()
    else:
        render_mod_grid([])

    root.mainloop()


def main():
    args = build_arg_parser().parse_args()
    if args.gui:
        launch_gui()
        return 0

    if not args.input_mod:
        raise SystemExit("You must provide an input mod directory or use --gui to open the graphical interface.")

    from .convert_mod import build_release_mod

    input_mod = os.path.abspath(args.input_mod)
    output_mod = args.output_mod or _default_output_for(input_mod)
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
