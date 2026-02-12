import difflib
import re

def normalize_words(text):
    """Extract words preserving case."""
    return re.findall(r'\b\w+\b', text)

# -------------------------------------------------------
# COMPARISON 1: ISI → FA (Coverage Check)
# -------------------------------------------------------
def check_isi_in_fa(og_isi, fa):
    """Check if all ISI content is present in FA."""
    og_words = normalize_words(og_isi)
    fa_words = normalize_words(fa)

    if not og_words:
        return 100.0, []

    matcher = difflib.SequenceMatcher(None, og_words, fa_words)

    # Track matched ISI words
    matched_indices = set()
    for i, j, n in matcher.get_matching_blocks():
        matched_indices.update(range(i, i + n))

    # Find missing content
    missing_sequences = []
    current_missing = []

    for idx, word in enumerate(og_words):
        if idx not in matched_indices:
            current_missing.append(word)
        else:
            if current_missing:
                missing_sequences.append(' '.join(current_missing))
                current_missing = []

    if current_missing:
        missing_sequences.append(' '.join(current_missing))

    coverage = (len(matched_indices) / len(og_words)) * 100

    return coverage, missing_sequences

# -------------------------------------------------------
# COMPARISON 2: Extracted ISI from FA → Original ISI  
# -------------------------------------------------------
def check_extracted_isi_modifications(og_isi, fa):
    """
    Extract ONLY matched ISI blocks from FA and check for 
    insertions/modifications WITHIN those ISI sections.
    """
    og_words = normalize_words(og_isi)
    fa_words = normalize_words(fa)

    matcher = difflib.SequenceMatcher(None, og_words, fa_words)

    # Get matched blocks
    matched_blocks = []
    for i, j, n in matcher.get_matching_blocks():
        if n > 0:
            matched_blocks.append({
                'og_start': i,
                'fa_start': j,
                'length': n,
                'og_words': og_words[i:i+n],
                'fa_words': fa_words[j:j+n]
            })

    if not matched_blocks:
        return 100.0, "", []

    # Reconstruct ISI from matched blocks only
    isi_from_fa = ' '.join(' '.join(block['fa_words']) for block in matched_blocks)

    # Check for insertions BETWEEN matched blocks in FA
    additional_in_isi = []

    for idx in range(len(matched_blocks) - 1):
        current_block = matched_blocks[idx]
        next_block = matched_blocks[idx + 1]

        # Get FA position range between two ISI blocks
        gap_start = current_block['fa_start'] + current_block['length']
        gap_end = next_block['fa_start']

        # Get OG position range
        og_gap_start = current_block['og_start'] + current_block['length']
        og_gap_end = next_block['og_start']

        # If blocks are consecutive in OG but not in FA, there's an insertion
        if og_gap_end == og_gap_start and gap_end > gap_start:
            inserted = ' '.join(fa_words[gap_start:gap_end])
            if len(inserted.strip()) > 0:
                additional_in_isi.append(inserted)

    # Calculate authenticity
    total_extracted_words = len(normalize_words(isi_from_fa))
    if total_extracted_words:
        additional_word_count = sum(len(normalize_words(add)) for add in additional_in_isi)
        authenticity = ((total_extracted_words - additional_word_count) / total_extracted_words) * 100
    else:
        authenticity = 100.0

    return authenticity, isi_from_fa, additional_in_isi

# -------------------------------------------------------
# MAIN VALIDATION
# -------------------------------------------------------
def validate_compliance(og_isi, fa):
    """
    Two-way compliance check:
    1. ISI → FA: Coverage check
    2. Extracted ISI from FA → Original ISI: Modifications within ISI
    """
    print("=" * 70)
    print("COMPLIANCE VALIDATION")
    print("=" * 70)

    # Comparison 1: ISI → FA
    print("\n1. ISI → FA (Coverage Check)")
    print("-" * 70)
    coverage, missing = check_isi_in_fa(og_isi, fa)
    print(f"Coverage: {coverage:.1f}%")

    if missing:
        print(f"Missing ISI content ({len(missing)} segments):")
        for i, m in enumerate(missing, 1):
            print(f"  {i}. {m}")
    else:
        print("✅ All ISI content found in FA")

    # Comparison 2: Extracted ISI → Original ISI
    print("\n2. Extracted ISI from FA → Original ISI")
    print("-" * 70)
    authenticity, extracted_isi, modifications = check_extracted_isi_modifications(og_isi, fa)

    print("\nExtracted ISI from FA (matched blocks only):")
    print(f"  {extracted_isi}")

    print(f"\nAuthenticity: {authenticity:.1f}%")

    if modifications:
        print(f"\nModifications/additions within ISI sections ({len(modifications)} found):")
        for i, mod in enumerate(modifications, 1):
            print(f"  {i}. '{mod}'")
    else:
        print("✅ No modifications in extracted ISI")

    print("\n" + "=" * 70)

    return {
        'coverage': coverage,
        'missing': missing,
        'authenticity': authenticity,
        'modifications': modifications,
        'extracted_isi': extracted_isi
    }

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
    Product info here. Full contraindications never include Hypersensitivity to the active substance.
    Important warnings May cause drowsiness while driving. Do not operate heavy machinery.
    Promo ends. Adverse Reactions: Headache, nausea possible.
    """

    result = validate_compliance(og_isi, fa)