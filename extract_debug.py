import difflib
import re
from difflib import HtmlDiff


# -------------------------------------------------------
# WORD NORMALIZATION
# -------------------------------------------------------

def normalize_words(text):
    """
    Convert text into ordered word tokens.
    Removes punctuation and lowercases.
    """
    return re.findall(r'\b\w+\b', text.lower())


# -------------------------------------------------------
# WORD BLOCK EXTRACTION (YOUR MATCHER)
# -------------------------------------------------------

def word_level_block_match(og_isi_text, fa_text, min_word_block=2):
    og_words = normalize_words(og_isi_text)
    fa_words = normalize_words(fa_text)

    matcher = difflib.SequenceMatcher(None, og_words, fa_words)
    blocks = []

    for block in matcher.get_matching_blocks():
        i, j, n = block

        if n >= min_word_block:
            og_block_words = og_words[i:i+n]
            fa_block_words = fa_words[j:j+n]

            blocks.append({
                'og_words': ' '.join(og_block_words),
                'fa_words': ' '.join(fa_block_words),
                'num_words': n
            })

    # reconstruct ISI detected inside FA
    isi_from_fa = '. '.join(b['fa_words'] for b in blocks)

    return blocks, isi_from_fa


# -------------------------------------------------------
# WORD-LEVEL HTML DEBUG DIFF
# -------------------------------------------------------

def word_level_debug_diff(og_isi, isi_from_fa, output_file="word_debug_diff.html"):
    """
    Compare OG ISI vs Extracted ISI at WORD LEVEL.
    Each word is treated as a line so HtmlDiff highlights alignment errors.
    """

    og_words = normalize_words(og_isi)
    fa_words = normalize_words(isi_from_fa)

    # each word becomes a line (required for HtmlDiff)
    og_lines = [w + "\n" for w in og_words]
    fa_lines = [w + "\n" for w in fa_words]

    differ = HtmlDiff(wrapcolumn=40)

    html = differ.make_file(
        og_lines,
        fa_lines,
        fromdesc="ORIGINAL ISI WORDS",
        todesc="EXTRACTED WORDS FROM FA",
        context=False
    )

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nWord-level debug HTML created → {output_file}")


# -------------------------------------------------------
# MAIN RUNNER
# -------------------------------------------------------

def run_debug(og_isi, fa):

    print("\n=========== BLOCKS FOUND ===========\n")

    blocks, isi_from_fa = word_level_block_match(og_isi, fa)

    for idx, b in enumerate(blocks, 1):
        print(f"[Block {idx}]")
        print("OG Words :", b['og_words'])
        print("FA Words :", b['fa_words'])
        print("Word Count:", b['num_words'])
        print()

    print("\n=========== RECONSTRUCTED ISI FROM FA ===========\n")
    print(isi_from_fa)

    print("\n=========== ORIGINAL ISI ===========\n")
    print(og_isi)

    # generate debug comparison
    word_level_debug_diff(og_isi, isi_from_fa)


# -------------------------------------------------------
# DEMO INPUT
# -------------------------------------------------------

if __name__ == "__main__":

    og_isi = """
    Contraindications: Hypersensitivity to the active substance.
    Warnings: May cause drowsiness. Do not operate machinery.
    Adverse Reactions: Headache, nausea.
    """

    fa = """
    Product info here. Full contraindications include Hypersensitivity to the less active substance.
    Important warnings May cause drowsiness while driving. Do not operate heavy machinery.
    Promo ends. Adverse Reactions: Headache, nausea possible.
    """

    run_debug(og_isi, fa)
