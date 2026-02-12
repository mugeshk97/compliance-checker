import difflib
import re
from difflib import HtmlDiff

# -------------------------------------------------------
# 1. NORMALIZATION (Case-Preserving for Regulatory)
# -------------------------------------------------------
def normalize_words(text):
    """Word tokens WITHOUT lowercasing - preserves regulatory casing."""
    return re.findall(r'\b\w+\b', text)

def sentence_split(text):
    """Regulatory-aware sentence splitter."""
    return re.split(r'(?<=[.;:])\s+', text.strip())

# -------------------------------------------------------
# 2. WORD-LEVEL BLOCK EXTRACTION (Direction 2: FA → ISI)
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
    
    isi_from_fa = '. '.join(b['fa_words'] for b in blocks)
    return blocks, isi_from_fa

# -------------------------------------------------------
# 3. COVERAGE RATIO (Direction 1: ISI → FA)
# -------------------------------------------------------
def coverage_ratio(og_isi_text, extracted_isi_text):
    og_words = normalize_words(og_isi_text)
    ex_words = normalize_words(extracted_isi_text)
    matcher = difflib.SequenceMatcher(None, og_words, ex_words)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    return matched / len(og_words) if og_words else 0

# -------------------------------------------------------
# 4. REGULATORY HTML AUDIT REPORT
# -------------------------------------------------------
def generate_html_diff(og_isi, isi_from_fa, output_file="isi_compliance_report.html"):
    og_lines = sentence_split(og_isi)
    fa_lines = sentence_split(isi_from_fa)
    differ = HtmlDiff(wrapcolumn=90)
    html = differ.make_file(
        og_lines, fa_lines,
        fromdesc="✅ REQUIRED ISI (Original)",
        todesc="📄 DETECTED in FA (Extracted)",
        context=True, numlines=2
    )
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"<html><head><title>ISI Compliance Report</title></head><body>{html}</body></html>")
    print(f"✅ Audit report: {output_file}")

# -------------------------------------------------------
# 5. FULL TWO-WAY COMPLIANCE ENGINE
# -------------------------------------------------------
def run_compliance_check(og_isi, fa, min_word_block=2):
    print("🔍 PHARMACEUTICAL ISI/FA COMPLIANCE CHECK")
    print("=" * 60)
    
    # Direction 2: Extract ISI from FA
    blocks, isi_from_fa = word_level_block_match(og_isi, fa, 0)
    
    print("\n📋 BLOCKS EXTRACTED:")
    for i, b in enumerate(blocks, 1):
        print(f"  {i}. '{b['fa_words']}' ← {b['num_words']} words")
    
    print(f"\n✅ ISI_from_FA: {isi_from_fa}")
    print(f"\n📄 Original ISI:\n{og_isi}")
    
    # Direction 1: Coverage Check
    coverage = coverage_ratio(og_isi, isi_from_fa) * 100
    print(f"\n📊 COVERAGE: {coverage:.1f}%")
    
    if coverage >= 95:
        print("🟢 PASS - Full compliance")
    elif coverage >= 80:
        print("🟡 MODERATE - Review HTML diff")
    else:
        print("🔴 HIGH RISK - Critical safety info missing")
    
    generate_html_diff(og_isi, isi_from_fa)
    return coverage, isi_from_fa

# -------------------------------------------------------
# USAGE
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
