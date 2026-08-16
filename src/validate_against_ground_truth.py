import argparse
import os

try:
    from .comparator import (
        parse_release_keyframes,
        compare_keyframes,
        parse_release_effects,
        compare_effects,
        parse_release_sound_fx,
        parse_release_sound_loops,
        parse_release_voice_banks,
    )
except ImportError:  # pragma: no cover
    from src.comparator import (
        parse_release_keyframes,
        compare_keyframes,
        parse_release_effects,
        compare_effects,
        parse_release_sound_fx,
        parse_release_sound_loops,
        parse_release_voice_banks,
    )


def run_keyframes_validation(gt_path, generated_keyframes):
    expected = parse_release_keyframes(gt_path)
    result = compare_keyframes(expected, generated_keyframes)
    print('Keyframes validation:')
    print(f'  expected={len(expected)} generated={len(generated_keyframes)} matched={len(result.matched)}')
    if result.missing:
        print('  Missing keyframes:', len(result.missing))
    if result.animation_mismatches:
        print('  Animation mismatches:', len(result.animation_mismatches))


def main():
    p = argparse.ArgumentParser(description='Validate generated outputs against Release ground-truth files')
    p.add_argument('--generated-keyframes', default='outputs/keyframes_example.cfg')
    p.add_argument('--gt-keyframes', required=True, help='Real Release keyframes.cfg to compare against')
    args = p.parse_args()

    # import late to avoid circular imports when used differently
    from .animation_converter import convert_animations
    from .legacy_parser import parse_legacy_chart

    # For convenience, if generated_keyframes is a path to a parser result, we parse it
    # But here we only support comparing a generated list by re-running conversion.
    chart = os.path.join(os.path.dirname(__file__), 'chart.cfg')
    parsed = parse_legacy_chart(chart)
    anim_res = convert_animations(parsed)

    run_keyframes_validation(args.gt_keyframes, anim_res.keyframes)


if __name__ == '__main__':
    main()
