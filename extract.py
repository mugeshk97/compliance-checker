import difflib
import re
from difflib import HtmlDiff
from pathlib import Path

# -------------------------------------------------------
# 1. NORMALIZATION (Regulatory Case-Preserving)
# -------------------------------------------------------
def normalize_words(text):
    """Extract words preserving case for legal fidelity."""
    return re.findall(r'\b\w+\b', text)

def sentence_split(text):
    """Regulatory sentence splitter (: . ; aware)."""
    return re.split(r'(?<=[.;:])\s+', text.strip())

# -------------------------------------------------------
# 2. DIRECTION 2: EXTRACTION (FA → ISI) - Authenticity Check
# -------------------------------------------------------
def word_level_block_match(og_isi_text, fa_text, min_word_block=1):
    """Extract verbatim ISI sequences from FA."""
    og_words = normalize_words(og_isi_text)
    fa_words = normalize_words(fa_text)
    
    matcher = difflib.SequenceMatcher(None, og_words, fa_words)
    blocks = []
    
    for block in matcher.get_matching_blocks():
        i, j, n = block
        if n >= min_word_block:
            og_block = ' '.join(og_words[i:i+n])
            fa_block = ' '.join(fa_words[j:j+n])
            blocks.append({
                'og_block': og_block,
                'fa_block': fa_block,
                'num_words': n,
                'exact': og_block == fa_block
            })
    
    isi_from_fa = '. '.join(b['fa_block'] for b in blocks)
    authenticity_ratio = sum(1 for b in blocks if b['exact']) / len(blocks) * 100 if blocks else 0
    return blocks, isi_from_fa, authenticity_ratio

# -------------------------------------------------------
# 3. DIRECTION 1: COVERAGE (ISI → FA)
# -------------------------------------------------------
def coverage_ratio(og_isi_text, extracted_isi_text):
    """Percentage of OG ISI found in extracted FA content."""
    og_words = normalize_words(og_isi_text)
    ex_words = normalize_words(extracted_isi_text)
    if not og_words:
        return 0
    matcher = difflib.SequenceMatcher(None, og_words, ex_words)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    return matched / len(og_words)

# -------------------------------------------------------
# 4. REGULATORY COMPLIANCE REPORT
# -------------------------------------------------------
def generate_html_diff(og_isi, isi_from_fa, output_file="isi_compliance_report.html"):
    """FDA/EMA audit-ready HTML diff."""
    og_lines = sentence_split(og_isi)
    fa_lines = sentence_split(isi_from_fa or "")
    differ = HtmlDiff(wrapcolumn=90)
    html = differ.make_file(
        og_lines, fa_lines,
        fromdesc="✅ REQUIRED ISI (Authority Source)",
        todesc="📄 EXTRACTED FROM FA (Promotional Material)",
        context=True, numlines=2
    )
    Path(output_file).write_text(
        f"<html><head><title>ISI Compliance Audit Report</title>"
        f"<style>body{{font-family:Arial;}} table{{border-collapse:collapse;}}</style></head>"
        f"<body><h1>Pharma Compliance Report</h1>{html}</body></html>",
        encoding="utf-8"
    )
    return output_file

# -------------------------------------------------------
# 5. TWO-WAY COMPLIANCE VALIDATION ENGINE
# -------------------------------------------------------
def run_compliance_check(og_isi, fa, min_word_block=1, output_dir="./compliance_reports"):
    """Full Direction 1 + Direction 2 validation."""
    Path(output_dir).mkdir(exist_ok=True)
    
    print("🔍 TWO-WAY PHARMACEUTICAL COMPLIANCE VALIDATION")
    print("=" * 70)
    
    # Direction 2: Authenticity (FA → ISI extraction)
    blocks, isi_from_fa, authenticity = word_level_block_match(og_isi, fa, min_word_block)
    
    print("\n📋 DIRECTION 2 - EXTRACTION BLOCKS:")
    for i, b in enumerate(blocks[:10], 1):  # Top 10
        status = "✅" if b['exact'] else "⚠️"
        print(f"  {i}. {status} '{b['fa_block']}' ({b['num_words']} words)")
    
    print(f"\n✅ Reconstructed ISI_from_FA:\n{isi_from_fa}")
    
    # Direction 1: Coverage (ISI → FA)
    coverage = coverage_ratio(og_isi, isi_from_fa) * 100
    
    print("\n📊 METRICS:")
    print(f"   Coverage (Dir 1):  {coverage:6.1f}%")
    print(f"   Authenticity (Dir 2): {authenticity:6.1f}%")
    
    # Risk Assessment
    if coverage >= 95 and authenticity >= 98:
        print("🟢 PASS - Full regulatory compliance")
    elif coverage >= 85:
        print("🟡 MODERATE - Acceptable with review")
    else:
        print("🔴 HIGH RISK - Safety information incomplete")
    
    # Audit Report
    report_file = generate_html_diff(og_isi, isi_from_fa, f"{output_dir}/isi_report_{Path(f'a').stem}.html")
    print(f"\n📄 Audit report saved: {report_file}")
    
    return {
        'coverage': coverage,
        'authenticity': authenticity,
        'isi_from_fa': isi_from_fa,
        'blocks': blocks,
        'report_file': report_file
    }

# -------------------------------------------------------
# PRODUCTION USAGE
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
    
    result = run_compliance_check(og_isi, fa, min_word_block=1)
