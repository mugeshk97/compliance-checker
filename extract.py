import difflib
import re

def normalize_words(text):
    return re.findall(r'\b\w+\b', text.lower())

def word_level_block_match(og_isi_text, fa_text, min_word_block=0):
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

# Your demo
og_isi = """Contraindications: Hypersensitivity to the active substance. Warnings: May cause drowsiness. Do not operate machinery. Adverse Reactions: Headache, nausea."""
fa = """Product info here. Full contraindications include Hypersensitivity to the active substance. Important warnings May cause drowsiness while driving. Do not operate heavy machinery. Promo ends. Adverse Reactions: Headache, nausea possible."""

blocks, isi_from_fa = word_level_block_match(og_isi, fa)
print("=== EXTRACTED ISI FROM FA ===")
print(isi_from_fa)

print("===OG ISI===")
print(og_isi)