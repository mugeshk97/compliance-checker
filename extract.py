import difflib
import re
from difflib import HtmlDiff


# -------------------------------------------------------
# 1. NORMALIZATION
# -------------------------------------------------------

def normalize_words(text):
    """
    Convert text → list of lowercase words
    Removes punctuation but preserves word order.
    """
    return re.findall(r'\b\w+\b', text.lower())


def sentence_split(text):
    """
    Regulatory ISI often uses :, ; and .
    This splitter keeps disclosures readable in diff.
    """
    return re.split(r'(?<=[.;:])\s+', text.strip())


# -------------------------------------------------------
# 2. WORD-LEVEL BLOCK MATCHING
# (Find ISI content that appears inside FA)
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

    # reconstruct communicated ISI
    isi_from_fa = '. '.join(b['fa_words'] for b in blocks)

    return blocks, isi_from_fa


# -------------------------------------------------------
# 3. COVERAGE METRIC (IMPORTANT)
# Measures how much of ISI was communicated
# -------------------------------------------------------

def coverage_ratio(og_isi_text, extracted_isi_text):
    og_words = normalize_words(og_isi_text)
    ex_words = normalize_words(extracted_isi_text)

    matcher = difflib.SequenceMatcher(None, og_words, ex_words)

    matched = sum(block.size for block in matcher.get_matching_blocks())
    total = len(og_words)

    if total == 0:
        return 0

    return matched / total


# -------------------------------------------------------
# 4. HTML DIFF REPORT (AUDIT DOCUMENT)
# -------------------------------------------------------

def generate_html_diff(og_isi, isi_from_fa, output_file="isi_diff.html"):

    og_lines = sentence_split(og_isi)
    fa_lines = sentence_split(isi_from_fa)

    differ = HtmlDiff(wrapcolumn=90)

    html_content = differ.make_file(
        og_lines,
        fa_lines,
        fromdesc="Original ISI (Required Disclosure)",
        todesc="Communicated ISI Detected in FA",
        context=True,
        numlines=2
    )

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\nHTML compliance report created → {output_file}")


# -------------------------------------------------------
# 5. MAIN COMPLIANCE CHECK
# -------------------------------------------------------

def run_compliance_check(og_isi, fa):

    print("\n========== EXTRACTING ISI FROM FA ==========\n")

    blocks, isi_from_fa = word_level_block_match(og_isi, fa)

    for idx, b in enumerate(blocks, 1):
        print(f"[Block {idx}]")
        print("Matched Words :", b['og_words'])
        print("Found In FA   :", b['fa_words'])
        print("Word Count    :", b['num_words'])
        print()

    print("\n========== RECONSTRUCTED ISI FROM FA ==========\n")
    print(isi_from_fa)

    print("\n========== COVERAGE ANALYSIS ==========\n")
    cov = coverage_ratio(og_isi, isi_from_fa)
    print(f"ISI Coverage Ratio: {cov:.2%}")

    if cov >= 0.90:
        print("Compliance Risk: LOW")
    elif cov >= 0.70:
        print("Compliance Risk: MODERATE")
    else:
        print("Compliance Risk: HIGH (Missing Safety Information)")

    # generate regulatory audit file
    generate_html_diff(og_isi, isi_from_fa)


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
    Product info here. Full contraindications include Hypersensitivity to the active substance.
    Important warnings May cause drowsiness while driving. Do not operate heavy machinery.
    Promo ends. Adverse Reactions: Headache, nausea possible.
    """

    run_compliance_check(og_isi, fa)
