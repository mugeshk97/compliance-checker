import difflib
from typing import List, Tuple


def get_isi_matches_in_fa(isi_text: str, fa_text: str) -> List[Tuple[int, int, int]]:
    """
    Finds exact matching blocks of ISI text inside the FA text.
    Returns a list of (iso_start, fa_start, length) tuples.
    """
    # Quick optimization: if texts are identical or empty
    if not isi_text or not fa_text:
        return []

    matcher = difflib.SequenceMatcher(None, isi_text, fa_text)

    # get_matching_blocks returns pieces of the first string found in the second
    # Format: Match(a=i, b=j, size=n) where isi[i:i+n] == fa[j:j+n]
    # We only care about matches with substantial length (e.g. > 2 chars? or even 1?)
    # For strict compliance, even short matches might matter, but let's trust difflib
    matches = matcher.get_matching_blocks()

    # Filter out empty matches (the last one is always size=0)
    return [m for m in matches if m.size > 0]
