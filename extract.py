import difflib
import re

def normalize_text(text):
    """Normalize for matching."""
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    return re.sub(r'\s+', ' ', text).strip()

def extract_isi_blocks(og_isi_text, fa_text, min_block_size=15):
    """Extract all matching blocks of OG ISI from FA."""
    og_norm = normalize_text(og_isi_text)
    fa_norm = normalize_text(fa_text)
    
    matcher = difflib.SequenceMatcher(None, og_norm, fa_norm)
    extracted_blocks = []
    
    for block in matcher.get_matching_blocks():
        i, j, n = block  # OG start, FA start, length
        if n >= min_block_size:
            og_block = og_norm[i:i+n]
            fa_block = fa_norm[j:j+n]
            block_ratio = difflib.SequenceMatcher(None, og_block, fa_block).ratio()
            extracted_blocks.append({
                'og_block': og_block,
                'extracted_fa_block': fa_block,
                'size': n,
                'ratio': block_ratio
            })
    return extracted_blocks

def direction2_compliance(og_isi_text, fa_text, min_block_size=15):
    blocks = extract_isi_blocks(og_isi_text, fa_text, min_block_size)
    
    if not blocks:
        print("No ISI blocks extracted from FA.")
        return [], 0.0
    
    ratios = [b['ratio'] for b in blocks]
    authenticity_ratio = sum(ratios) / len(ratios)
    
    print("Extracted ISI Blocks from FA:")
    for b in blocks:
        print(f"OG: '{b['og_block']}' | FA Extract: '{b['extracted_fa_block']}' | Size: {b['size']} | Ratio: {b['ratio']:.1%}")
    
    print(f"\nAuthenticity Ratio: {authenticity_ratio:.2%}")
    return blocks, authenticity_ratio

# Demo
og_isi = """Contraindications: Hypersensitivity to the active substance. Warnings: May cause drowsiness. Do not operate machinery. Adverse Reactions: Headache, nausea."""
fa = """Product info. Safety: Hypersensitivity to the active substance contraindicated. Warnings: May cause drowsiness. Promo text. Headache and nausea are adverse reactions."""
direction2_compliance(og_isi, fa)
