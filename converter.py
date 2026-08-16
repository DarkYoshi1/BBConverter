from __future__ import annotations

import argparse

from animation_converter import convert_animations
from comparator import (
    compare_keyframes,
    compare_notes,
    format_comparison_report,
    format_keyframe_comparison_report,
    parse_release_keyframes,
    parse_release_notes,
)
from debug import write_debug_file
from legacy_parser import parse_legacy_chart
from models import Timeline
from note_generator import generate_notes
from release_writer import write_release_chart, write_release_keyframes
from timeline import build_changes, build_timeline


def convert_notes(parsed: dict):
    timeline = build_timeline(parsed)
    changes, collisions = build_changes(parsed)
    notes = generate_notes(changes, timeline, parsed)
    return changes, collisions, notes


def convert(input_path: str, notes_output: str, debug_path: str, keyframes_output: str = None,
            assets_dir: str = None, convert_animations_flag: bool = True,
            include_last_transition: bool = True):
    parsed = parse_legacy_chart(input_path)
    timeline = build_timeline(parsed)
    changes, collisions = build_changes(parsed)
    notes = generate_notes(changes, timeline, parsed)
    write_release_chart(notes_output, notes)

    animation_result = None
    if convert_animations_flag:
        animation_result = convert_animations(parsed, timeline=timeline, assets_dir=assets_dir,
                                               include_last_transition=include_last_transition)
        if keyframes_output:
            write_release_keyframes(keyframes_output, animation_result.keyframes)

    write_debug_file(debug_path, changes, notes, parsed.get('last_beat'), parsed, collisions, animation_result)
    return parsed, changes, notes, collisions, animation_result


def validate_notes(ground_truth_path: str, notes, report_path: str = None):
    expected = parse_release_notes(ground_truth_path)
    result = compare_notes(expected, notes)
    report = format_comparison_report(result, len(expected), len(notes))
    print(report)
    if report_path:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
    return result


def validate_keyframes(ground_truth_path: str, keyframes, report_path: str = None):
    expected = parse_release_keyframes(ground_truth_path)
    result = compare_keyframes(expected, keyframes)
    report = format_keyframe_comparison_report(result, len(expected), len(keyframes))
    print(report)
    if report_path:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
    return result


def build_arg_parser():
    p = argparse.ArgumentParser(description='Beat Banger Legacy -> Release conversion core')
    p.add_argument('input')
    p.add_argument('-o', '--notes-output', required=True)
    p.add_argument('-k', '--keyframes-output', default=None)
    p.add_argument('-d', '--debug-output', default='conversion_debug.txt')
    p.add_argument('--assets-dir', default=None)
    p.add_argument('--skip-animations', action='store_true')
    p.add_argument('--notes-ground-truth', default=None)
    p.add_argument('--keyframes-ground-truth', default=None)
    return p


if __name__ == '__main__':
    args = build_arg_parser().parse_args()
    parsed, changes, notes, collisions, anim = convert(
        args.input, args.notes_output, args.debug_output, args.keyframes_output,
        args.assets_dir, not args.skip_animations,
    )
    print(f'BPM: {parsed["bpm"]}')
    print(f'last_beat: {parsed.get("last_beat")}')
    print(f'notes: {len(notes)}')
    print(f'collisions: {len(collisions)}')
    if args.notes_ground_truth:
        validate_notes(args.notes_ground_truth, notes)
    if args.keyframes_ground_truth and anim:
        validate_keyframes(args.keyframes_ground_truth, anim.keyframes)
