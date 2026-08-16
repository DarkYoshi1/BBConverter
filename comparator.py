"""
Compara las notas generadas por nuestro algoritmo contra un notes.cfg
REAL producido por Beat Banger Release (ground truth).

No usamos offsets arbitrarios para "hacer coincidir" timestamps: si algo
no coincide, lo reportamos tal cual para investigar qué regla del
formato estamos interpretando mal.
"""
import re
import json
from dataclasses import dataclass
from typing import List, Optional
from note_generator import Note

# Tolerancia de punto flotante para considerar dos timestamps "iguales".
# No es un offset de corrección: solo absorbe el ruido de redondeo
# binario de las divisiones (30/BPM), no discrepancias reales.
TIMESTAMP_EPSILON = 1e-6


def parse_release_notes(path: str) -> List[dict]:
    """Lee un notes.cfg de Release real y devuelve su lista de notas
    (input_type, note_modifier, timestamp) tal como están, sin modificar."""
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()

    m = re.search(r'data\s*=\s*(\{.*\})\s*$', text, re.DOTALL)
    if not m:
        raise ValueError(f"No se encontró el bloque 'data=' en {path}")

    data = json.loads(m.group(1))
    notes = data['charts'][0]['notes']
    # normalizamos orden por timestamp para comparar de forma determinista
    return sorted(notes, key=lambda n: (n['timestamp'], n['input_type']))


@dataclass
class ComparisonResult:
    matched: List[tuple]              # (expected, generated) que coinciden
    missing: List[dict]               # están en el real pero no generamos
    extra: List[Note]                 # generamos pero no están en el real
    timestamp_mismatches: List[tuple] # mismo índice/orden, timestamp distinto
    input_type_mismatches: List[tuple]


def compare_notes(expected: List[dict], generated: List[Note]) -> ComparisonResult:
    """
    Empareja notas por timestamp (con tolerancia de punto flotante).
    Reporta coincidencias, faltantes, sobrantes y diferencias de tipo.
    """
    remaining_generated = list(generated)
    matched = []
    missing = []
    timestamp_mismatches = []
    input_type_mismatches = []

    for exp in expected:
        # busca una nota generada con timestamp igual (dentro de epsilon)
        candidate = None
        for gen in remaining_generated:
            if abs(gen.timestamp - exp['timestamp']) <= TIMESTAMP_EPSILON:
                candidate = gen
                break

        if candidate is None:
            missing.append(exp)
            continue

        remaining_generated.remove(candidate)

        if candidate.input_type != exp['input_type']:
            input_type_mismatches.append((exp, candidate))
        else:
            matched.append((exp, candidate))

    extra = remaining_generated

    return ComparisonResult(
        matched=matched,
        missing=missing,
        extra=extra,
        timestamp_mismatches=timestamp_mismatches,
        input_type_mismatches=input_type_mismatches,
    )


def format_comparison_report(result: ComparisonResult, expected_count: int, generated_count: int) -> str:
    lines = []
    lines.append("VALIDATION REPORT: generated notes vs real Release notes.cfg")
    lines.append("=" * 60)
    lines.append(f"Expected (real) note count : {expected_count}")
    lines.append(f"Generated note count       : {generated_count}")
    lines.append(f"Matched (timestamp + type) : {len(result.matched)}")
    lines.append(f"Input_type mismatches      : {len(result.input_type_mismatches)}")
    lines.append(f"Missing (in real, not gen.): {len(result.missing)}")
    lines.append(f"Extra (generated, not real): {len(result.extra)}")
    lines.append("")

    if result.input_type_mismatches:
        lines.append("INPUT_TYPE MISMATCHES")
        lines.append("-" * 60)
        for exp, gen in result.input_type_mismatches:
            lines.append(
                f"timestamp={exp['timestamp']:<12} expected_type={exp['input_type']}"
                f"  generated_type={gen.input_type}  (legacy_frame={gen.legacy_frame})"
            )
        lines.append("")

    if result.missing:
        lines.append("MISSING NOTES (present in real Release, not generated)")
        lines.append("-" * 60)
        for exp in result.missing:
            lines.append(f"timestamp={exp['timestamp']:<12} input_type={exp['input_type']}")
        lines.append("")

    if result.extra:
        lines.append("EXTRA NOTES (generated, not present in real Release)")
        lines.append("-" * 60)
        for gen in result.extra:
            lines.append(
                f"timestamp={gen.timestamp:<12} input_type={gen.input_type}"
                f"  (legacy_frame={gen.legacy_frame})"
            )
        lines.append("")

    if not result.missing and not result.extra and not result.input_type_mismatches:
        lines.append("PERFECT MATCH: every generated note matches the real Release chart.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Keyframes (animations) comparison
# ---------------------------------------------------------------------------

def parse_release_keyframes(path: str) -> List[dict]:
    """Lee un keyframes.cfg REAL de Release y devuelve su lista de loops
    (timestamp, animation), sin modificar nada."""
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()

    m = re.search(r'data\s*=\s*(\{.*\})\s*$', text, re.DOTALL)
    if not m:
        raise ValueError(f"No se encontró el bloque 'data=' en {path}")

    data = json.loads(m.group(1))
    loops = data['loops']
    normalized = [
        {'timestamp': loop['timestamp'], 'animation': loop.get('animations', {}).get('normal')}
        for loop in loops
    ]
    return sorted(normalized, key=lambda l: l['timestamp'])


def parse_release_effects(path: str) -> List[dict]:
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    m = re.search(r'data\s*=\s*(\{.*\})\s*$', text, re.DOTALL)
    if not m:
        raise ValueError(f"No 'data=' block in {path}")
    data = json.loads(m.group(1))
    effects = data.get('effects', [])
    normalized = [{'timestamp': e.get('timestamp'), 'effect': e.get('effect')} for e in effects]
    return sorted(normalized, key=lambda e: (e['timestamp'] if e['timestamp'] is not None else -1))


def compare_effects(expected: List[dict], generated: List) -> dict:
    remaining = list(generated)
    matched = []
    missing = []
    extra = []
    for exp in expected:
        candidate = None
        for gen in remaining:
            if gen.timestamp is None or exp.get('timestamp') is None:
                # cannot reliably match missing timestamp
                continue
            if abs(gen.timestamp - exp['timestamp']) <= TIMESTAMP_EPSILON:
                candidate = gen
                break
        if candidate is None:
            missing.append(exp)
            continue
        remaining.remove(candidate)
        if getattr(candidate, 'effect', None) != exp.get('effect'):
            extra.append({'expected': exp, 'generated': getattr(candidate, 'effect', None)})
        else:
            matched.append((exp, candidate))
    extra = remaining
    return {'matched': matched, 'missing': missing, 'extra': extra}


def parse_release_sound_fx(path: str) -> List[dict]:
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    m = re.search(r'data\s*=\s*(\{.*\})\s*$', text, re.DOTALL)
    if not m:
        raise ValueError(f"No 'data=' block in {path}")
    data = json.loads(m.group(1))
    return data.get('sound_fx_triggers', [])


def parse_release_sound_loops(path: str) -> List[dict]:
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    m = re.search(r'data\s*=\s*(\{.*\})\s*$', text, re.DOTALL)
    if not m:
        raise ValueError(f"No 'data=' block in {path}")
    data = json.loads(m.group(1))
    return data.get('sound_loops', [])


def parse_release_voice_banks(path: str) -> List[dict]:
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    m = re.search(r'data\s*=\s*(\{.*\})\s*$', text, re.DOTALL)
    if not m:
        raise ValueError(f"No 'data=' block in {path}")
    data = json.loads(m.group(1))
    return data.get('voice_banks', [])


@dataclass
class KeyframeComparisonResult:
    matched: List[tuple]
    missing: List[dict]
    extra: List
    animation_mismatches: List[tuple]


def compare_keyframes(expected: List[dict], generated: List) -> KeyframeComparisonResult:
    remaining = list(generated)
    matched = []
    missing = []
    animation_mismatches = []

    for exp in expected:
        candidate = None
        for gen in remaining:
            if abs(gen.timestamp - exp['timestamp']) <= TIMESTAMP_EPSILON:
                candidate = gen
                break

        if candidate is None:
            missing.append(exp)
            continue

        remaining.remove(candidate)

        if candidate.animation != exp['animation']:
            animation_mismatches.append((exp, candidate))
        else:
            matched.append((exp, candidate))

    return KeyframeComparisonResult(
        matched=matched,
        missing=missing,
        extra=remaining,
        animation_mismatches=animation_mismatches,
    )


def format_keyframe_comparison_report(result: KeyframeComparisonResult, expected_count: int, generated_count: int) -> str:
    lines = []
    lines.append("VALIDATION REPORT: generated keyframes vs real Release keyframes.cfg")
    lines.append("=" * 60)
    lines.append(f"Expected (real) keyframe count : {expected_count}")
    lines.append(f"Generated keyframe count        : {generated_count}")
    lines.append(f"Matched (timestamp + animation)  : {len(result.matched)}")
    lines.append(f"Animation mismatches             : {len(result.animation_mismatches)}")
    lines.append(f"Missing (in real, not generated)  : {len(result.missing)}")
    lines.append(f"Extra (generated, not real)       : {len(result.extra)}")
    lines.append("")

    if result.animation_mismatches:
        lines.append("ANIMATION MISMATCHES")
        lines.append("-" * 60)
        for exp, gen in result.animation_mismatches:
            lines.append(
                f"timestamp={exp['timestamp']:<12} expected={exp['animation']}  generated={gen.animation}"
            )
        lines.append("")

    if result.missing:
        lines.append("MISSING KEYFRAMES (present in real Release, not generated)")
        lines.append("-" * 60)
        for exp in result.missing:
            lines.append(f"timestamp={exp['timestamp']:<12} animation={exp['animation']}")
        lines.append("")

    if result.extra:
        lines.append("EXTRA KEYFRAMES (generated, not present in real Release)")
        lines.append("-" * 60)
        for gen in result.extra:
            lines.append(f"timestamp={gen.timestamp:<12} animation={gen.animation}  (frame={gen.frame})")
        lines.append("")

    if not result.missing and not result.extra and not result.animation_mismatches:
        lines.append("PERFECT MATCH: every generated keyframe matches the real Release chart.")

    return "\n".join(lines)


def find_best_note_offset(gt_keyframes_path: str, gen_keyframes_path: str, search_range_beats=8):
    """Heurística: intenta pequeños desplazamientos en segundos para maximizar
    la cantidad de notas generadas que coinciden con las notas del ground-truth.
    Devuelve dict {'offset': seconds, 'matches': n} o None si no puede evaluar.
    """
    try:
        with open(gt_keyframes_path, 'r', encoding='utf-8') as f:
            gt_text = f.read()
        with open(gen_keyframes_path, 'r', encoding='utf-8') as f:
            gen_text = f.read()
    except Exception:
        return None

    try:
        gt_data = json.loads(gt_text.split('data =', 1)[1])
        gen_data = json.loads(gen_text.split('data =', 1)[1])
    except Exception:
        return None

    gt_notes = [n.get('timestamp') for n in gt_data.get('charts', [])[0].get('notes', []) if n.get('timestamp') is not None]
    gen_notes = [n.get('timestamp') for n in gen_data.get('charts', [])[0].get('notes', []) if n.get('timestamp') is not None]
    if not gt_notes or not gen_notes:
        return None

    bpm = gen_data.get('modifiers', [{}])[0].get('bpm') or 120
    quarter = 60.0 / bpm

    best = {'offset': 0.0, 'matches': -1}
    # increments of quarter/4 (sixteenth) across the beat range
    step = quarter / 4.0
    steps = int((search_range_beats * 4) * 2)  # half-steps to cover quarter-beat granularity
    for i in range(-steps, steps + 1):
        off = i * step
        shifted = [t + off for t in gen_notes]
        tol = 0.02
        matches = 0
        gi = 0
        gj = 0
        shifted_sorted = sorted(shifted)
        gt_sorted = sorted(gt_notes)
        while gi < len(shifted_sorted) and gj < len(gt_sorted):
            if abs(shifted_sorted[gi] - gt_sorted[gj]) <= tol:
                matches += 1
                gi += 1
                gj += 1
            elif shifted_sorted[gi] < gt_sorted[gj]:
                gi += 1
            else:
                gj += 1
        if matches > best['matches']:
            best = {'offset': off, 'matches': matches}

    return best
