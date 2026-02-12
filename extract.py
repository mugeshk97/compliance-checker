import difflib
import re

def normalize_text(text):
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    return re.sub(r'\s+', ' ', text).strip()

def direction2_compliance(og_isi_text, fa_text, min_block_size=10):
    og_norm = normalize_text(og_isi_text)
    fa_norm = normalize_text(fa_text)
    
    matcher = difflib.SequenceMatcher(None, og_norm, fa_norm)
    blocks = []
    
    for block in matcher.get_matching_blocks():
        i, j, n = block
        if n >= min_block_size:
            og_block = og_norm[i:i+n]
            fa_block = fa_norm[j:j+n]
            ratio = difflib.SequenceMatcher(None, og_block, fa_block).ratio()
            blocks.append({
                'og_block': og_block,
                'fa_block': fa_block,
                'size': n,
                'ratio': ratio
            })
    
    if not blocks:
        return [], "", 0.0
    
    # Assemble extracted ISI from FA as single text
    isi_from_fa = '. '.join(b['fa_block'].strip() for b in blocks)
    isi_from_fa = re.sub(r'\.\s*\.', '.', isi_from_fa).strip()
    
    ratios = [b['ratio'] for b in blocks]
    authenticity_ratio = sum(ratios) / len(ratios)
    
    return blocks, isi_from_fa, authenticity_ratio

# Demo usage
og_isi = """Contraindications: Hypersensitivity to the active substance. Warnings: May cause drowsiness. Do not operate machinery. Adverse Reactions: Headache, nausea."""

fa = """Product info here. Full contraindications include Hypersensitivity to the active substance. Important warnings May cause drowsiness while driving. Do not operate heavy machinery. Promo ends. Adverse Reactions: Headache, nausea possible."""

blocks, isi_from_fa, ratio = direction2_compliance(og_isi, fa)

print("=== EXTRACTED ISI FROM FA (for manual verification) ===")
print(isi_from_fa)
print("\n=== Detailed Blocks ===")
for b in blocks:
    print(f"OG: '{b['og_block']}' | FA: '{b['fa_block']}' | Ratio: {b['ratio']:.1%}")

print(f"\nAuthenticity Ratio: {ratio:.2%}")
print(f"OG ISI full: {normalize_text(og_isi)}")
