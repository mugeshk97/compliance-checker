import difflib
from typing import List

from src.normalization import tokenize_text


def calculate_coverage(matched_mask: List[bool]) -> float:
    """
    Calculates what percentage of the ISI text is present in the FA.
    """
    if not matched_mask:
        return 0.0

    covered_tokens = sum(1 for matched in matched_mask if matched)
    return covered_tokens / len(matched_mask)


def calculate_authenticity(original_isi: str, reconstructed_isi: str) -> float:
    """
    Calculates how accurately the included ISI was copied.
    Compares original ISI vs Reconstructed ISI (extracted from FA).
    """
    original_tokens = tokenize_text(original_isi)
    reconstructed_tokens = tokenize_text(reconstructed_isi)

    if not original_tokens:
        return 0.0  # Undefined, but 0 is safe
    if not reconstructed_tokens:
        return 0.0

    matcher = difflib.SequenceMatcher(None, original_tokens, reconstructed_tokens)
    return matcher.ratio()


def get_missing_isi_segments(
    isi_text: str, matched_mask: List[bool]
) -> List[str]:
    """
    Identifies segments of ISI text that are NOT covered by matches.
    """
    isi_tokens = tokenize_text(isi_text)
    if not isi_tokens or not matched_mask:
        return []

    missing_segments = []
    current_segment: List[str] = []

    for i, covered in enumerate(matched_mask):
        if i >= len(isi_tokens):
            break
        if not covered:
            current_segment.append(isi_tokens[i])
        else:
            if current_segment:
                segment_str = " ".join(current_segment).strip()
                if len(segment_str) > 5:  # Filter out tiny noise
                    missing_segments.append(segment_str)
                current_segment = []

    if current_segment:
        segment_str = " ".join(current_segment).strip()
        if len(segment_str) > 5:
            missing_segments.append(segment_str)

    return missing_segments


def get_edits(original_isi: str, reconstructed_isi: str) -> List[str]:
    """
    Returns a list of string descriptions of edits (insertions/deletions/replacements).
    """
    original_tokens = tokenize_text(original_isi)
    reconstructed_tokens = tokenize_text(reconstructed_isi)
    matcher = difflib.SequenceMatcher(None, original_tokens, reconstructed_tokens)
    edits = []
    for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
        if opcode == "equal":
            continue
        elif opcode == "delete":
            segment = " ".join(original_tokens[a0:a1])
            edits.append(f"MISSING in FA: '{segment}'")
        elif opcode == "insert":
            segment = " ".join(reconstructed_tokens[b0:b1])
            edits.append(f"ADDED in FA: '{segment}'")
        elif opcode == "replace":
            original_segment = " ".join(original_tokens[a0:a1])
            reconstructed_segment = " ".join(reconstructed_tokens[b0:b1])
            edits.append(
                f"CHANGED: '{original_segment}' -> '{reconstructed_segment}'"
            )

    return edits
