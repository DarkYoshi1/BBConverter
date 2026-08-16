from typing import List
from timeline import Change, Collision
from note_generator import Note

TYPE_LABEL = {0: "0 (half)", 1: "1 (quarter)", 2: "2 (eighth)", None: "NO SPAWN"}


def write_debug_file(path: str, changes: List[Change], notes: List[Note], last_beat,
                      parsed: dict, collisions: List[Collision] = None,
                      animation_result=None):
    collisions = collisions or []
    with open(path, 'w', encoding='utf-8') as f:
        f.write("Beat Banger Legacy -> Release\n")
        f.write("Conversion diagnostic report\n")
        f.write("=" * 60 + "\n\n")

        # ---- summary: notes -------------------------------------------------
        counts = {0: 0, 1: 0, 2: 0}
        for n in notes:
            counts[n.input_type] = counts.get(n.input_type, 0) + 1
        f.write("Notes:\n")
        f.write(f"    input_type 0: {counts.get(0, 0)}\n")
        f.write(f"    input_type 1: {counts.get(1, 0)}\n")
        f.write(f"    input_type 2: {counts.get(2, 0)}\n")
        f.write(f"    total: {len(notes)}\n\n")

        # ---- summary: animations ---------------------------------------------
        if animation_result is not None:
            unique_assets = sorted({k.animation for k in animation_result.keyframes})
            f.write("Animations:\n")
            f.write(f"    total transitions: {len(parsed.get('transitions') or {})}\n")
            f.write(f"    unique animation assets: {len(unique_assets)}\n")
            f.write(f"    generated keyframes: {len(animation_result.keyframes)}\n\n")

            f.write("Animation timeline:\n")
            f.write("-" * 60 + "\n")
            f.write(f"{'frame':<8}{'timestamp':<12}{'animation'}\n")
            f.write("-" * 60 + "\n")
            for kf in animation_result.keyframes:
                f.write(f"{kf.frame:<8}{kf.timestamp:<12.6f}{kf.animation}\n")
            f.write("\n")

            if animation_result.skipped_duplicates:
                f.write(f"Skipped no-op transitions (animation unchanged): "
                        f"{len(animation_result.skipped_duplicates)}\n")
                for c in animation_result.skipped_duplicates:
                    f.write(f"    frame={c.frame:<5} source={c.source:<12} animation={c.animation}\n")
                f.write("\n")

            if animation_result.last_transition_info:
                info = animation_result.last_transition_info
                f.write("last_transition (reported, NOT included in generated keyframes):\n")
                f.write(f"    animation = {info['animation']}\n")
                f.write(f"    unverified hypothesis timestamp (at last_beat) = "
                        f"{info['hypothesis_timestamp_at_last_beat']}\n\n")

            f.write("Warnings:\n")
            if animation_result.warnings:
                for w in animation_result.warnings:
                    f.write(f"    - {w}\n")
            else:
                f.write("    (none)\n")
            f.write("\n")

            f.write("Errors:\n")
            if animation_result.errors:
                for e in animation_result.errors:
                    f.write(f"    - {e}\n")
            else:
                f.write("    (none)\n")
            f.write("\n")

        f.write("=" * 60 + "\n")
        f.write("DETAILED NOTE CONVERSION LOG\n")
        f.write("=" * 60 + "\n\n")
        f.write("BEAT BANGER LEGACY -> RELEASE : NOTE CONVERSION DEBUG\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"bpm             = {parsed['bpm']}\n")
        f.write(f"note_offset     = {parsed['note_offset']}\n")
        f.write(f"initial note_type (legacy) = {parsed['note_type']}\n")
        f.write(f"last_beat       = {last_beat}\n\n")

        f.write(f"half_spawn entries    = {len(parsed['half_spawn'])}\n")
        f.write(f"quarter_spawn entries = {len(parsed['quarter_spawn'])}\n")
        f.write(f"eighth_spawn entries  = {len(parsed['eighth_spawn'])}\n")
        f.write(f"no_spawn entries      = {len(parsed['no_spawn'])}\n")
        f.write(f"TOTAL raw entries (old, WRONG note count) = "
                f"{len(parsed['half_spawn']) + len(parsed['quarter_spawn']) + len(parsed['eighth_spawn'])}\n\n")

        if collisions:
            f.write("!! UNRESOLVED COLLISIONS !!\n")
            f.write("-" * 60 + "\n")
            f.write(
                "The same frame appears in more than one spawn array with a "
                "DIFFERENT declared state. No priority was assumed — the "
                "first-declared source was used as an UNVERIFIED placeholder. "
                "These need to be checked against real Legacy runtime behavior.\n\n"
            )
            for col in collisions:
                sources = ", ".join(f"{c.source}->{TYPE_LABEL[c.input_type]}" for c in col.conflicting)
                f.write(f"frame={col.frame:<5} conflicting: {sources}\n")
            f.write("\n")

        f.write("INTERVAL CHANGES\n")
        f.write("-" * 60 + "\n")
        for c in changes:
            f.write(f"frame={c.frame:<5} source={c.source:<15} active_type={TYPE_LABEL[c.input_type]}\n")
        f.write("\n")

        f.write(f"GENERATED NOTES (total = {len(notes)})\n")
        f.write("-" * 60 + "\n")
        f.write(f"{'index':<7}{'frame':<8}{'input_type':<12}{'timestamp':<12}\n")
        for idx, n in enumerate(notes):
            f.write(f"{idx:<7}{n.legacy_frame:<8}{n.input_type:<12}{n.timestamp:<12.6f}\n")
