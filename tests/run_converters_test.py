import pprint
import sys
import os

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

from legacy_parser import parse_legacy_chart
from effect_converter import convert_effects
from sound_fx_converter import convert_sound_fx
from sound_loop_converter import convert_sound_loops


def main():
    chart_path = os.path.join(ROOT, 'chart.cfg')
    print('Using chart:', chart_path)
    parsed = parse_legacy_chart(chart_path)
    pp = pprint.PrettyPrinter(indent=2)

    print('\n--- Effects ---')
    effects = convert_effects(parsed)
    pp.pprint({'keyframes_count': len(effects.keyframes), 'warnings': effects.warnings, 'errors': effects.errors})

    print('\n--- Sound FX Triggers ---')
    sfx = convert_sound_fx(parsed)
    pp.pprint({'triggers_count': len(sfx.triggers), 'warnings': sfx.warnings})

    print('\n--- Sound Loops ---')
    loops = convert_sound_loops(parsed)
    pp.pprint({'loops_count': len(loops.loops), 'warnings': loops.warnings})



if __name__ == '__main__':
    main()
