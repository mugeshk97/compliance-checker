import difflib
from typing import List, Tuple


def calculate_coverage(isi_text: str, matches: List[Tuple[int, int, int]]) -> float:
    """
    Calculates what percentage of the ISI text is present in the FA.

    matches: List of (isi_start, fa_start, length)
    """
    if not isi_text:
        return 0.0

    # We need to count unique ISI characters covered.
    # Matches might overlap in ISI? Usually difflib produces non-overlapping matches in A.
    # But let's be safe and use a mask for ISI.

    isi_mask = [0] * len(isi_text)

    for isi_start, _, length in matches:
        for i in range(isi_start, isi_start + length):
            if i < len(isi_mask):
                isi_mask[i] = 1

    covered_chars = sum(isi_mask)
    return covered_chars / len(isi_text)


def calculate_authenticity(original_isi: str, reconstructed_isi: str) -> float:
    """
    Calculates how accurately the included ISI was copied.
    Compares original ISI vs Reconstructed ISI (extracted from FA).
    """
    if not original_isi:
        return 0.0  # Undefined, but 0 is safe
    if not reconstructed_isi:
        return 0.0

    matcher = difflib.SequenceMatcher(None, original_isi, reconstructed_isi)
    return matcher.ratio()


def get_missing_isi_segments(
    isi_text: str, matches: List[Tuple[int, int, int]]
) -> List[str]:
    """
    Identifies segments of ISI text that are NOT covered by matches.
    """
    if not isi_text:
        return []

    isi_mask = [0] * len(isi_text)
    for isi_start, _, length in matches:
        for i in range(isi_start, isi_start + length):
            if i < len(isi_mask):
                isi_mask[i] = 1

    missing_segments = []
    current_segment = []

    for i, covered in enumerate(isi_mask):
        if covered == 0:
            current_segment.append(isi_text[i])
        else:
            if current_segment:
                segment_str = "".join(current_segment).strip()
                if len(segment_str) > 5:  # Filter out tiny noise
                    missing_segments.append(segment_str)
                current_segment = []

    if current_segment:
        segment_str = "".join(current_segment).strip()
        if len(segment_str) > 5:
            missing_segments.append(segment_str)

    return missing_segments


def get_edits(original_isi: str, reconstructed_isi: str) -> List[str]:
    """
    Returns a list of string descriptions of edits (insertions/deletions/replacements).
    """
    matcher = difflib.SequenceMatcher(None, original_isi, reconstructed_isi)
    edits = []
    for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
        if opcode == "equal":
            continue
        elif opcode == "delete":
            edits.append(f"MISSING in FA: '{original_isi[a0:a1]}'")
        elif opcode == "insert":
            edits.append(f"ADDED in FA: '{reconstructed_isi[b0:b1]}'")
        elif opcode == "replace":
            edits.append(
                f"CHANGED: '{original_isi[a0:a1]}' -> '{reconstructed_isi[b0:b1]}'"
            )

    return edits
