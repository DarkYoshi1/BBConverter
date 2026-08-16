import os
import sys
ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

from src.legacy_parser import parse_legacy_chart
from src.animation_converter import convert_animations


def test_include_last_transition():
    parsed = parse_legacy_chart(os.path.join(ROOT, 'chart.cfg'))
    # without including last_transition
    res = convert_animations(parsed, assets_dir=None, include_last_transition=False)
    frames_without_last = [kf.frame for kf in res.keyframes]
    assert parsed.get('last_beat') not in frames_without_last

    # with including last_transition
    res2 = convert_animations(parsed, assets_dir=None, include_last_transition=True)
    frames_with_last = [kf.frame for kf in res2.keyframes]
    # if last_beat exists, it should be present now
    if parsed.get('last_beat') is not None:
        assert parsed.get('last_beat') in frames_with_last


if __name__ == '__main__':
    test_include_last_transition()
    print('animation_converter tests passed')
