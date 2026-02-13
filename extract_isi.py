import re
from typing import List, Tuple

try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    print("WARNING: rapidfuzz not installed. Install for 3x better performance:")
    print("  pip install rapidfuzz")
    try:
        import difflib
        HAS_RAPIDFUZZ = False
    except ImportError:
        print("ERROR: Neither rapidfuzz nor difflib available!")
        exit(1)


def normalize_text(text: str) -> str:
    """
    Normalize text for pharmaceutical document matching.
    Handles common PDF extraction artifacts and formatting issues.
    """
    # Remove trademark symbols
    text = re.sub(r'[®™©]', '', text)
    
    # Remove control characters and zero-width spaces
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    text = text.replace('\u200b', '')  # Zero-width space
    text = text.replace('\xad', '-')   # Soft hyphen
    
    # Fix hyphenated line breaks (e.g., "hepa-\ntotoxicity" -> "hepatotoxicity")
    text = re.sub(r'(\w)-\s+(\w)', r'\1\2', text)
    
    # Normalize dashes and quotes
    text = re.sub(r'[-–—]', '-', text)
    text = re.sub(r'["""]', '"', text)
    
    # Collapse multiple whitespaces
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def calculate_similarity(text1: str, text2: str, use_token_sort: bool = True) -> float:
    """
    Calculate similarity score between two texts.
    Returns score in range [0.0, 1.0]
    """
    text1_lower = text1.lower()
    text2_lower = text2.lower()
    
    if HAS_RAPIDFUZZ:
        if use_token_sort:
            # token_set_ratio is better for ISI text with word order variations
            score = fuzz.token_set_ratio(text1_lower, text2_lower)
        else:
            # Standard ratio for exact matching
            score = fuzz.ratio(text1_lower, text2_lower)
        return score / 100.0  # Normalize to 0-1
    else:
        # Fallback to difflib
        return difflib.SequenceMatcher(None, text1_lower, text2_lower).ratio()


def find_isi_in_document(
    document_text: str,
    golden_isi: str | List[str],
    min_length: int = 25,
    similarity_threshold: float = 0.88,
    window_expansion: int = 6,
    step_divisor: int = 2,
    use_token_sort: bool = True,
    return_positions: bool = False,
) -> List[Tuple[str, str, float]] | List[Tuple[str, str, float, int, int]]:
    """
    Find ISI chunks in document text using fuzzy matching.
    
    Args:
        document_text: Full text from document (already extracted)
        golden_isi: Reference ISI text (string or list of chunks)
        min_length: Minimum character length for chunks to process
        similarity_threshold: Minimum similarity score (0.0-1.0)
        window_expansion: Extra words to add to search window
        step_divisor: Controls sliding window step size (higher = faster but less thorough)
        use_token_sort: Use token-based matching (better for word order variations)
        return_positions: If True, also return (start_pos, end_pos) in document
    
    Returns:
        List of (found_text, golden_chunk, similarity_score[, start_pos, end_pos])
    """
    results = []
    
    # Normalize document once
    doc_normalized = normalize_text(document_text)
    doc_normalized_lower = doc_normalized.lower()
    
    # Prepare golden chunks
    if isinstance(golden_isi, str):
        chunks = [line.strip() for line in golden_isi.splitlines() if line.strip()]
    else:
        chunks = [str(x).strip() for x in golden_isi if str(x).strip()]
    
    # Filter by minimum length
    chunks = [c for c in chunks if len(c) >= min_length]
    
    for golden in chunks:
        golden_normalized = normalize_text(golden)
        golden_lower = golden_normalized.lower()
        
        # STEP 1: Try exact match first (fastest path)
        if golden_lower in doc_normalized_lower:
            start_pos = doc_normalized_lower.find(golden_lower)
            end_pos = start_pos + len(golden_lower)
            found_text = doc_normalized[start_pos:end_pos]
            
            if return_positions:
                results.append((found_text, golden, 1.0, start_pos, end_pos))
            else:
                results.append((found_text, golden, 1.0))
            continue
        
        # STEP 2: Fuzzy sliding window search
        words_golden = golden_lower.split()
        if len(words_golden) < 4:
            # Too short for reliable fuzzy matching
            continue
        
        words_doc = doc_normalized_lower.split()
        
        # Calculate window parameters
        window_size = len(words_golden) + window_expansion
        step = max(1, len(words_golden) // step_divisor)
        
        best_ratio = 0.0
        best_match = ""
        best_start_pos = -1
        best_end_pos = -1
        
        # Sliding window with early termination heuristics
        for i in range(0, len(words_doc) - window_size + 1, step):
            window_words = words_doc[i : i + window_size]
            window_text = " ".join(window_words)
            
            # HEURISTIC 1: Length difference check
            len_diff = abs(len(golden_lower) - len(window_text))
            max_len_diff = len(golden_lower) * 0.35  # Allow 35% length variation
            if len_diff > max_len_diff:
                continue
            
            # HEURISTIC 2: Quick character set overlap check
            golden_chars = set(golden_lower.replace(' ', ''))
            window_chars = set(window_text.replace(' ', ''))
            char_overlap = len(golden_chars & window_chars) / len(golden_chars)
            if char_overlap < 0.6:  # At least 60% character overlap
                continue
            
            # Calculate similarity
            ratio = calculate_similarity(golden_lower, window_text, use_token_sort)
            
            if ratio > best_ratio:
                best_ratio = ratio
                
                # Find original text position in document
                # Search for first few words to locate position
                search_phrase = " ".join(window_words[:3])
                char_pos = doc_normalized_lower.find(search_phrase)
                
                if char_pos >= 0:
                    # Estimate window boundaries in original text
                    approx_len = len(window_text)
                    start_pos = char_pos
                    end_pos = min(start_pos + int(approx_len * 1.2), len(doc_normalized))
                    
                    best_match = doc_normalized[start_pos:end_pos]
                    best_start_pos = start_pos
                    best_end_pos = end_pos
        
        # Add result if meets threshold
        if best_ratio >= similarity_threshold:
            if return_positions:
                results.append((best_match, golden, round(best_ratio, 4), best_start_pos, best_end_pos))
            else:
                results.append((best_match, golden, round(best_ratio, 4)))
    
    return results


# ────────────────────────────────────────────────
#                  EXAMPLE USAGE
# ────────────────────────────────────────────────

if __name__ == "__main__":
    
    # Example: Direct text input (your extracted PDF text goes here)
    DOCUMENT_TEXT = """
    Product Name XYZ - Prescribing Information
    
    IMPORTANT SAFETY INFORMATION
    
    WARNING: HEPATOTOXICITY
    Serious risk of hepatotoxicity has been observed. Monitor liver function 
    tests before and during treatment. Discontinue if ALT exceeds 3x ULN.
    
    CONTRAINDICATIONS
    Hypersensitivity to the active substance or to any of the excipients listed.
    Patients with severe hepatic impairment (Child-Pugh C).
    
    WARNINGS AND PRECAUTIONS
    Do not exceed 100 mg daily dose. Consult physician if symptoms persist 
    beyond 7 days. Risk of cardiovascular events in elderly patients.
    """
    
    # Golden ISI reference (what you're looking for)
    GOLDEN_ISI = """
    WARNING: Serious risk of hepatotoxicity. Monitor liver function tests before and during treatment.
    CONTRAINDICATIONS: Hypersensitivity to the active substance or excipients.
    Do not exceed 100 mg daily. Consult physician if symptoms persist beyond 7 days.
    """
    
    print("=" * 80)
    print("ISI DETECTION RESULTS")
    print("=" * 80)
    print(f"\nDocument length: {len(DOCUMENT_TEXT):,} characters")
    print(f"Using: {'RapidFuzz (optimized)' if HAS_RAPIDFUZZ else 'difflib (fallback)'}\n")
    
    # Find ISI matches
    matches = find_isi_in_document(
        DOCUMENT_TEXT,
        GOLDEN_ISI,
        min_length=30,
        similarity_threshold=0.85,
        use_token_sort=True,
        return_positions=True
    )
    
    if not matches:
        print("❌ No ISI chunks found.\n")
    else:
        print(f"✅ Found {len(matches)} match(es):\n")
        for i, (found, golden, score, start, end) in enumerate(matches, 1):
            print(f"{'─' * 80}")
            print(f"Match #{i}  |  Similarity: {score:.1%}  |  Position: {start}-{end}")
            print(f"{'─' * 80}")
            print(f"GOLDEN:\n{golden}\n")
            print(f"FOUND:\n{found}\n")
    
    print("=" * 80)
