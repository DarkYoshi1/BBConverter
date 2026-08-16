import os
import sys
ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

from src.legacy_parser import parse_legacy_chart
from src.effect_converter import convert_effects, check_assets as check_effect_assets
from src.sound_fx_converter import convert_sound_fx, check_assets as check_sfx_assets


def test_asset_warnings():
    parsed = parse_legacy_chart(os.path.join(ROOT, 'chart.cfg'))
    eff = convert_effects(parsed)
    check_effect_assets(eff, assets_dir=None)
    assert any('No --assets-dir provided' in w for w in eff.warnings)

    sfx = convert_sound_fx(parsed)
    check_sfx_assets(sfx, assets_dir=None)
    assert any('No --assets-dir provided' in w for w in sfx.warnings)


if __name__ == '__main__':
    test_asset_warnings()
    print('asset check tests passed')
