from typing import List, Tuple
import re


def label_fa_words(
    fa_text: str, matches: List[Tuple[int, int, int]]
) -> Tuple[List[str], str]:
    """
    Labels words in FA as ISI or marketing based on character matches.
    Returns:
        - List of labeled words (or tuples with labels) - sticking to user request "label FA words"
        - Reconstructed ISI string from FA
    """
    if not fa_text:
        return [], ""

    # 1. Create character mask
    # 0 = Marketing, 1 = ISI
    mask = [0] * len(fa_text)

    for _, fa_start, length in matches:
        for i in range(fa_start, fa_start + length):
            if i < len(mask):
                mask[i] = 1

    # 2. Split FA into words (keeping track of indices to map back to mask)
    # Simple whitespace splitting for now, but we need character indices
    # Regex iter is better to get span

    reconstructed_isi_parts = []
    labeled_words = []  # List of (word, label)

    # Using a simple regex to capture words and everything else as delimiters if needed
    # But usually "words" means linguistic words.
    # Let's iterate over tokens.

    for match in re.finditer(r"\S+", fa_text):
        word = match.group()
        start, end = match.span()

        # Calculate coverage of this word
        word_mask = mask[start:end]
        isi_char_count = sum(word_mask)

        # Threshold: if > 50% of characters are ISI, label as ISI
        if len(word) > 0 and (isi_char_count / len(word)) > 0.5:
            label = "ISI"
            reconstructed_isi_parts.append(word)
        else:
            label = "MARKETING"

        labeled_words.append((word, label))

    reconstructed_isi = " ".join(reconstructed_isi_parts)

    return labeled_words, reconstructed_isi
