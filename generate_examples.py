import os
from converter import convert
from effect_converter import convert_effects
from sound_fx_converter import convert_sound_fx
from sound_loop_converter import convert_sound_loops
from voice_bank_converter import convert_voice_banks
from release_writer import (
    write_release_effects, write_release_sound_fx,
    write_release_sound_loops, write_release_voice_banks,
)
from release_writer import write_release_keyframes


def main():
    base = os.path.dirname(__file__)
    chart = os.path.join(base, 'chart.cfg')
    out_dir = os.path.join(base, 'outputs')
    os.makedirs(out_dir, exist_ok=True)

    notes_out = os.path.join(out_dir, 'notes_example.cfg')
    keyframes_out = os.path.join(out_dir, 'keyframes_example.cfg')
    debug_out = os.path.join(out_dir, 'conversion_debug.txt')

    print('Converting', chart)
    parsed, changes, notes, collisions, animation_result = convert(
        input_path=chart,
        notes_output=notes_out,
        debug_path=debug_out,
        keyframes_output=keyframes_out,
        assets_dir=None,
        convert_animations_flag=True,
    )

    print('Wrote:', notes_out)
    print('Wrote:', keyframes_out)
    print('Wrote:', debug_out)

    # additional systems
    effects_res = convert_effects(parsed)
    sfx_res = convert_sound_fx(parsed)
    loops_res = convert_sound_loops(parsed)
    vb_res = convert_voice_banks(parsed)

    # write a full keyframes-style payload that matches Release structure
    write_release_keyframes(
        os.path.join(out_dir, 'keyframes_example_full.cfg'),
        animation_result.keyframes if animation_result else [],
        effects=effects_res.keyframes,
        modifiers=[{"bpm": parsed['bpm'], "timestamp": 0.0}],
        shutter=[],
        sound_loops=loops_res.loops,
        sound_oneshot=sfx_res.triggers,
        voice_banks=vb_res.entries,
        background=[],
    )

    write_release_effects(os.path.join(out_dir, 'effects_example.cfg'), effects_res.keyframes)
    write_release_sound_fx(os.path.join(out_dir, 'sound_fx_example.cfg'), sfx_res.triggers)
    write_release_sound_loops(os.path.join(out_dir, 'sound_loops_example.cfg'), loops_res.loops)
    write_release_voice_banks(os.path.join(out_dir, 'voice_banks_example.cfg'), vb_res.entries)

    print('Wrote additional examples to', out_dir)


if __name__ == '__main__':
    main()
