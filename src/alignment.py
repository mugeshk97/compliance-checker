from collections import Counter
from typing import List, Tuple

from src.normalization import tokenize_text


def extract_isi_from_fa(isi_text: str, fa_text: str) -> Tuple[List[bool], str]:
    """
    Extracts ISI tokens from FA and penalizes reordering.
    Returns:
        - A boolean mask for ISI tokens indicating which are found in FA
        - Extracted ISI text reconstructed in FA order
    """
    isi_tokens = tokenize_text(isi_text)
    fa_tokens = tokenize_text(fa_text)

    # Coverage mask: ISI tokens found anywhere in FA (order-insensitive)
    fa_counts = Counter(fa_tokens)
    matched_mask: List[bool] = []
    for token in isi_tokens:
        if fa_counts[token] > 0:
            matched_mask.append(True)
            fa_counts[token] -= 1
        else:
            matched_mask.append(False)

    # Extracted ISI in FA order: consume only the tokens that exist in ISI (counts matter)
    isi_counts = Counter(isi_tokens)
    extracted_tokens: List[str] = []
    for token in fa_tokens:
        if isi_counts[token] > 0:
            extracted_tokens.append(token)
            isi_counts[token] -= 1

    return matched_mask, " ".join(extracted_tokens)
