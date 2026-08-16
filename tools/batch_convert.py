#!/usr/bin/env python3
import os
import argparse
import sys
from subprocess import check_call

def find_mods(root):
    mods = []
    for d, dirs, files in os.walk(root):
        if any(f.lower() == 'chart.cfg' for f in files):
            mods.append(d)
    return mods

def main():
    p = argparse.ArgumentParser()
    p.add_argument('root', help='Root folder to search for Legacy mods')
    p.add_argument('outdir', help='Output folder root for Release mods')
    p.add_argument('--no-copy-assets', action='store_true')
    p.add_argument('--no-last-transition', action='store_true', help='Omit the final Legacy last_transition state')
    args = p.parse_args()

    root = os.path.abspath(args.root)
    outdir = os.path.abspath(args.outdir)
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    converter_script = os.path.join(script_dir, 'convert_mod.py')

    mods = find_mods(root)
    print('Found', len(mods), 'mods')
    for m in mods:
        name = os.path.basename(m)
        out = os.path.join(outdir, name)
        cmd = [sys.executable, converter_script, m, out]
        if args.no_copy_assets:
            cmd.append('--no-copy-assets')
        if args.no_last_transition:
            cmd.append('--no-last-transition')
        print('Running:', ' '.join(cmd))
        check_call(cmd, cwd=script_dir)

if __name__ == '__main__':
    main()
