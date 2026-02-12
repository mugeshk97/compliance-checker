from collections import Counter
from typing import List, Tuple

from src.normalization import tokenize_text


def label_fa_words(fa_text: str, isi_text: str) -> List[Tuple[str, str]]:
    """
    Labels FA tokens as ISI or marketing based on exact token presence in ISI.
    Matching is case-sensitive and ignores FA order.
    """
    if not fa_text:
        return []

    isi_counts = Counter(tokenize_text(isi_text))
    labeled_words: List[Tuple[str, str]] = []

    for token in tokenize_text(fa_text):
        if isi_counts[token] > 0:
            label = "ISI"
            isi_counts[token] -= 1
        else:
            label = "MARKETING"

        labeled_words.append((token, label))

    return labeled_words
