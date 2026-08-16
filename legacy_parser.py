import re
import json


def _extract_int_list(text, key):
    m = re.search(rf'{key}\s*=\s*\[([^\]]*)\]', text)
    if not m:
        return []
    body = m.group(1).strip()
    if not body:
        return []
    return [int(x.strip()) for x in body.split(',') if x.strip() != '']


def _extract_scalar_number(text, key):
    m = re.search(rf'^{key}\s*=\s*(-?[0-9.]+)', text, re.MULTILINE)
    if not m:
        raise ValueError(f"Could not find scalar '{key}' in chart")
    val = m.group(1)
    return float(val) if '.' in val else int(val)


def _extract_quoted_string(text, key, required=False):
    m = re.search(rf'^{key}\s*=\s*"([^"]*)"', text, re.MULTILINE)
    if not m:
        if required:
            raise ValueError(f"Could not find string '{key}' in chart")
        return None
    return m.group(1)


def _find_balanced_block(text, start_brace_index):
    """Given the index of an opening '{', returns the text span (inclusive)
    of the balanced block, i.e. text[start_brace_index:end_index+1]."""
    depth = 0
    i = start_brace_index
    while i < len(text):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return text[start_brace_index:i + 1], i
        i += 1
    raise ValueError("Unbalanced braces while parsing chart")


def _extract_dict_block(text, key, required=True):
    """Extracts a `key = { ... }` block as raw text (braces balanced),
    where the block itself is valid JSON (quoted string keys only)."""
    m = re.search(rf'{key}\s*=\s*\{{', text)
    if not m:
        if required:
            raise ValueError(f"Could not find '{key}' block")
        return None
    start = m.end() - 1
    block_text, _ = _find_balanced_block(text, start)
    return json.loads(block_text)


def _extract_transitions(text):
    """Parses the `transitions = { 32: {...}, 64: {...}, ... }` block.

    The OUTER structure is NOT valid JSON (unquoted integer keys), but each
    individual transition object IS valid JSON, so we locate each `N: {`
    entry, balance its braces, and json.loads just that inner object.
    """
    m = re.search(r'transitions\s*=\s*\{', text)
    if not m:
        return {}
    outer_start = m.end() - 1
    outer_block, _ = _find_balanced_block(text, outer_start)
    inner_text = outer_block[1:-1]  # strip the outer { }

    transitions = {}
    entry_re = re.compile(r'(\d+)\s*:\s*\{')
    i = 0
    while True:
        entry_m = entry_re.search(inner_text, i)
        if not entry_m:
            break
        frame = int(entry_m.group(1))
        obj_start = entry_m.end() - 1
        obj_text, obj_end = _find_balanced_block(inner_text, obj_start)
        transitions[frame] = json.loads(obj_text)
        i = obj_end + 1

    return transitions


def parse_legacy_chart(path):
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()

    bpm = _extract_scalar_number(text, 'bpm')
    note_offset = _extract_scalar_number(text, 'note_offset')

    half_spawn = _extract_int_list(text, 'half_spawn')
    quarter_spawn = _extract_int_list(text, 'quarter_spawn')
    eighth_spawn = _extract_int_list(text, 'eighth_spawn')
    no_spawn = _extract_int_list(text, 'no_spawn')

    initial_data = _extract_dict_block(text, 'initial_data')
    note_type = initial_data.get('note_type', 0)

    transitions = _extract_transitions(text)
    last_transition = _extract_dict_block(text, 'last_transition', required=False)

    last_beat_list = _extract_int_list(text, 'last_beat')
    last_beat = last_beat_list[0] if last_beat_list else None

    name = _extract_quoted_string(text, 'name')
    song_path = _extract_quoted_string(text, 'song_path')
    game_over_sound = _extract_quoted_string(text, 'game_over_sound')

    # Top-level Legacy settings used by Release metadata/settings.
    def optional_scalar(key):
        m = re.search(rf'^{key}\s*=\s*(-?[0-9.]+|true|false)', text, re.MULTILINE)
        if not m:
            return None
        raw = m.group(1)
        if raw == 'true': return True
        if raw == 'false': return False
        return float(raw) if '.' in raw else int(raw)

    bar_position = optional_scalar('bar_position')
    music_volume = optional_scalar('music_volume')
    sfx_volume = optional_scalar('sfx_volume')
    voice_volume = optional_scalar('voice_volume')
    loop_speed = optional_scalar('loop_speed')
    screen_flash = optional_scalar('screen_flash')
    post_song_delay = optional_scalar('post_song_delay')

    return {
        'bpm': bpm,
        'note_offset': note_offset,
        'half_spawn': half_spawn,
        'quarter_spawn': quarter_spawn,
        'eighth_spawn': eighth_spawn,
        'no_spawn': no_spawn,
        'note_type': note_type,
        'last_beat': last_beat,
        # new in v2 (does not affect note parsing above):
        'initial_data': initial_data,
        'transitions': transitions,
        'last_transition': last_transition,
        'name': name,
        'song_path': song_path,
        'game_over_sound': game_over_sound,
        'bar_position': bar_position,
        'music_volume': music_volume,
        'sfx_volume': sfx_volume,
        'voice_volume': voice_volume,
        'loop_speed': loop_speed,
        'screen_flash': screen_flash,
        'post_song_delay': post_song_delay,
    }


def parse_legacy_meta(path):
    """
    Parses Legacy's meta.cfg (a SIBLING file to chart.cfg, not a key inside
    it). Format observed:

        [META]
        mod_title = "..."
        mod_creator = "..."
        mod_artist = "..."
        song_artist = "..."
        song_title = "..."
        length = "4:18"

    Returns a dict with whatever keys were found (missing keys are simply
    absent — never invented).
    """
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()

    fields = ('mod_title', 'mod_creator', 'mod_artist', 'song_artist', 'song_title', 'length')
    result = {}
    for field in fields:
        value = _extract_quoted_string(text, field)
        if value is not None:
            result[field] = value
    return result
