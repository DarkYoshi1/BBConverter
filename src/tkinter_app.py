from __future__ import annotations

import argparse


def build_arg_parser():
    p = argparse.ArgumentParser(description="Beat Banger Legacy -> Release conversion GUI (tkinter stub)")
    p.add_argument("--gui", action="store_true", help="Launch the tkinter conversion interface")
    return p


def launch_gui():
    raise RuntimeError("tkinter UI is not implemented in this environment")
