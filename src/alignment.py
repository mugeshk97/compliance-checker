import difflib
import re
from typing import List, Tuple

Token = Tuple[str, int, int]


def _tokenize_words(text: str) -> List[Token]:
    """
    Tokenize into words only (no punctuation), preserving character spans.
    """
    if not text:
        return []

    tokens: List[Token] = []
    for match in re.finditer(r"\b\w+\b", text):
        tokens.append((match.group(), match.start(), match.end()))
    return tokens


def get_isi_matches_in_fa(
    isi_text: str, fa_text: str
) -> Tuple[List[Tuple[int, int, int]], List[Token], List[Token]]:
    """
    Finds matching token blocks of ISI words inside the FA words.
    Returns:
      - matches: List of (isi_token_start, fa_token_start, token_length)
      - isi_tokens: List of (token, start, end)
      - fa_tokens: List of (token, start, end)
    """
    if not isi_text or not fa_text:
        return [], [], []

    isi_tokens = _tokenize_words(isi_text)
    fa_tokens = _tokenize_words(fa_text)

    isi_words = [t[0] for t in isi_tokens]
    fa_words = [t[0] for t in fa_tokens]

    if not isi_words or not fa_words:
        return [], isi_tokens, fa_tokens

    matcher = difflib.SequenceMatcher(None, isi_words, fa_words)
    matches = matcher.get_matching_blocks()

    # Filter out empty matches (the last one is always size=0)
    return [m for m in matches if m.size > 0], isi_tokens, fa_tokens
