from typing import List, Tuple

from src.alignment import Token


def extract_contextual_isi(
    fa_text: str,
    fa_tokens: List[Token],
    matches: List[Tuple[int, int, int]],
    max_gap: int = 50,
) -> str:
    """
    Extracts ISI from FA, including text between close matches (gap <= max_gap).
    matches: List of (isi_token_start, fa_token_start, token_length)
    """
    if not fa_text or not matches or not fa_tokens:
        return ""

    # Convert matched FA token ranges to character spans
    spans: List[Tuple[int, int]] = []
    for _, fa_start, length in matches:
        if fa_start >= len(fa_tokens) or length <= 0:
            continue
        last_index = min(fa_start + length - 1, len(fa_tokens) - 1)
        span_start = fa_tokens[fa_start][1]
        span_end = fa_tokens[last_index][2]
        spans.append((span_start, span_end))

    if not spans:
        return ""

    # Sort and merge spans by character gap
    spans.sort(key=lambda x: x[0])
    merged_blocks: List[Tuple[int, int]] = []

    current_start, current_end = spans[0]
    for span_start, span_end in spans[1:]:
        gap = span_start - current_end
        if 0 <= gap <= max_gap:
            current_end = max(current_end, span_end)
        else:
            merged_blocks.append((current_start, current_end))
            current_start, current_end = span_start, span_end

    merged_blocks.append((current_start, current_end))

    # Extract raw FA substrings to preserve punctuation and spacing
    return " ".join(fa_text[start:end] for start, end in merged_blocks)
