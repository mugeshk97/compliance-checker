import difflib
from typing import List, Tuple

from src.alignment import Token


def calculate_coverage(isi_tokens: List[Token], matches: List[Tuple[int, int, int]]) -> float:
    """
    Calculates what percentage of the ISI tokens are present in the FA.

    matches: List of (isi_token_start, fa_token_start, token_length)
    """
    if not isi_tokens:
        return 0.0

    isi_mask = [0] * len(isi_tokens)

    for isi_start, _, length in matches:
        for i in range(isi_start, isi_start + length):
            if i < len(isi_mask):
                isi_mask[i] = 1

    covered_tokens = sum(isi_mask)
    return covered_tokens / len(isi_tokens)


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


def get_simple_diff(isi_text: str, fa_text: str) -> List[str]:
    """
    Directly compares ISI vs FA to identify missing text blocks (order-sensitive).
    Returns a list of strings that are present in ISI but missing/deleted in FA.
    """
    if not isi_text:
        return []

    matcher = difflib.SequenceMatcher(None, isi_text, fa_text)
    missing_blocks = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "delete":
            # Text in ISI [i1:i2] is missing in FA
            segment = isi_text[i1:i2].strip()
            if len(segment) > 5:  # Filter small noise (punctuation etc)
                missing_blocks.append(segment)
        elif tag == "replace":
            # Text in ISI [i1:i2] was replaced by something else (effectively missing)
            segment = isi_text[i1:i2].strip()
            if len(segment) > 5:
                missing_blocks.append(segment)

    return missing_blocks


def get_unexpected_additions(isi_text: str, fa_text: str) -> List[str]:
    """
    Reverse Diff: Checks for text present in FA that is NOT in ISI.
    matches: List of strings that are "Inserted" or "Replaced" in FA.
    """
    if not isi_text or not fa_text:
        return []

    matcher = difflib.SequenceMatcher(None, isi_text, fa_text)
    additions = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "insert":
            # Text in FA [j1:j2] is new (not in ISI)
            segment = fa_text[j1:j2].strip()
            if len(segment) > 5:
                additions.append(segment)
        elif tag == "replace":
            # Text in FA [j1:j2] replaced something in ISI
            segment = fa_text[j1:j2].strip()
            if len(segment) > 5:
                additions.append(segment)

    return additions
