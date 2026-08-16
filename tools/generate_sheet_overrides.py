import json
import argparse
from comparator import parse_release_keyframes

def main():
    p = argparse.ArgumentParser()
    p.add_argument('keyframes', help='Path to a Release keyframes.cfg')
    p.add_argument('--out', default='sheet_overrides.json')
    args = p.parse_args()

    loops = parse_release_keyframes(args.keyframes)
    overrides = {}
    for l in loops:
        anim = l.get('animation')
        # try to read sheet_data from the raw file by loading the JSON is harder here,
        # but parse_release_keyframes currently discards sheet_data. Instead, we
        # open file and extract via a simple JSON parse of the full data.
    # fallback: load full JSON and extract loops with sheet_data
    import re, json as _json
    with open(args.keyframes, 'r', encoding='utf-8') as f:
        text = f.read()
    m = re.search(r'data\s*=\s*(\{.*\})\s*$', text, re.DOTALL)
    if not m:
        raise SystemExit('no data= block')
    data = _json.loads(m.group(1))
    for loop in data.get('loops', []):
        anim = loop.get('animations', {}).get('normal')
        sheet = loop.get('sheet_data')
        if anim and sheet:
            overrides[anim] = sheet

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(overrides, f, indent=2)
    print('Wrote', args.out)

if __name__ == '__main__':
    main()
