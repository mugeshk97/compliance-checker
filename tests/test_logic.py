from src.normalization import normalize_text
from src.alignment import get_isi_matches_in_fa
from src.labeling import extract_contextual_isi
from src.metrics import (
    calculate_coverage,
    calculate_authenticity,
    get_edits,
    get_simple_diff,
    get_unexpected_additions,
)


def run_test_scenario(name: str, description: str, isi_raw: str, fa_raw: str):
    print(f"\n{'=' * 40}")
    print(f"SCENARIO: {name}")
    print(f"DESC:     {description}")
    print(f"{'=' * 40}")

    # Normalization
    isi_norm = normalize_text(isi_raw)
    fa_norm = normalize_text(fa_raw)

    print(f"ISI: '{isi_norm}'")
    print(f"FA:  '{fa_norm}'")

    # Alignment
    matches, isi_tokens, fa_tokens = get_isi_matches_in_fa(isi_norm, fa_norm)

    # Extract ISI from FA (including small gaps)
    extracted_isi = extract_contextual_isi(
        fa_norm, fa_tokens, matches, max_gap=50
    )

    # Metrics
    coverage = calculate_coverage(isi_tokens, matches)
    authenticity = calculate_authenticity(isi_norm, extracted_isi)

    print(f"\nCoverage:     {coverage:.2%}")
    print(f"Authenticity: {authenticity:.2%}")

    # Reporting
    missing = get_simple_diff(isi_norm, fa_norm)
    if missing:
        print(f"Missing Segments: {missing}")

    additions = get_unexpected_additions(isi_norm, extracted_isi)
    if additions:
        print(f"Unexpected Additions: {additions}")

    edits = get_edits(isi_norm, extracted_isi)
    if edits:
        print("Edits/Differences:")
        for e in edits[:5]:  # Show first 5
            print(f"  {e}")


def main():
    scenarios = [
        {
            "name": "Perfect Match",
            "description": "Ideal case where the FA contains the exact ISI text.",
            "isi": "Warning: Causes dizziness.",
            "fa": "Buy now! Warning: Causes dizziness.",
        },
        {
            "name": "Typo / OCR Error (Insertion)",
            "description": "Simulates an OCR error or typo where an extra letter is inserted (dizzziness). Coverage should remain high.",
            "isi": "Warning: Causes dizziness.",
            "fa": "Warning: Causes dizzziness.",
        },
        {
            "name": "Typo / OCR Error (Deletion)",
            "description": "Simulates a missing letter (diziness). Should still match most characters.",
            "isi": "Warning: Causes dizziness.",
            "fa": "Warning: Causes diziness.",
        },
        {
            "name": "Missing Critical Word",
            "description": "A critical safety word ('pregnant') is completely omitted. Should be flagged as missing.",
            "isi": "Do not take if pregnant.",
            "fa": "Do not take if.",
        },
        {
            "name": "Sentence Reordering",
            "description": "Safety sentences appear in a different order. Coverage remains 100%.",
            "isi": "Store in cool place. Keep away from children.",
            "fa": "Keep away from children. Also, Store in cool place.",
        },
        {
            "name": "Interrupted Word (Hyphenation)",
            "description": "A word is split by a hyphen and newline. Normalization should handle this.",
            "isi": "Important Safety Information",
            "fa": "Impor- tant Safety Information",
        },
        {
            "name": "Marketing Insertion",
            "description": "Marketing adjectives inserted into safety text. Should match the core ISI words.",
            "isi": "Side effects include mild headache.",
            "fa": "Side effects include very mild, almost non-existent headache.",
        },
        {
            "name": "Case Mismatch",
            "description": "Different casing used. Since we enforce exact case matching, this should fail (0% coverage).",
            "isi": "WARNING",
            "fa": "warning",
        },
        {
            "name": "Hidden in Fine Print",
            "description": "Extra spacing used to hide text. Normalization should fix this.",
            "isi": "Serious risks.",
            "fa": "Serious      risks.",
        },
        # --- Advanced Layout Scenarios ---
        {
            "name": "Multi-Column Flow (Newline Interruption)",
            "description": "Text flows from bottom of Col 1 to top of Col 2. Extraction often inserts newlines.",
            "isi": "This medication causes severe drowsiness.",
            "fa": "This medication causes\nsevere drowsiness.",
        },
        {
            "name": "Header/Footer Intrusion",
            "description": "Page numbers or headers interrupt the safety text flow.",
            "isi": "Do not take if you have heart problems.",
            "fa": "Do not take if you have\n[Page 1]\nheart problems.",
        },
        {
            "name": "Bullet Points vs Paragraph",
            "description": "ISI is a paragraph, but FA presents it as bullet points.",
            "isi": "Side effects include nausea, vomiting, and dizziness.",
            "fa": "Side effects include:\n• nausea\n• vomiting\n• and dizziness.",
        },
        {
            "name": "Buried in Marketing (Low Signal-to-Noise)",
            "description": "A small safety warning buried in a wall of marketing text.",
            "isi": "Warning: May cause insomnia.",
            "fa": "Get the best sleep of your life! (Warning: May cause insomnia.) Wake up refreshed!",
        },
        {
            "name": "Table Structure (Pipes/Tabs)",
            "description": "Safety info presented inside a table row.",
            "isi": "Dosage: 10mg daily.",
            "fa": "| Drug A | Dosage: 10mg daily | $50 |",
        },
        # --- Even More Scenarios ---
        {
            "name": "Duplicate/Repeated ISI",
            "description": "ISI appears twice in the brochure. Coverage should be 100%.",
            "isi": "Warning: Dizziness.",
            "fa": "Warning: Dizziness. ...later... Warning: Dizziness.",
        },
        {
            "name": "Footnote/Citation Interruption",
            "description": "Citations like [1] or (See Ref) inserted.",
            "isi": "reactions include rash and hives.",
            "fa": "reactions include rash[1] and hives(see Ref 2).",
        },
        {
            "name": "Special Characters / Symbol Map",
            "description": "Handling of symbols like Registered, Trademark, Greek letters.",
            "isi": "DrugX® reduces beta-amyloid.",
            "fa": "DrugX (R) reduces beta-amyloid.",  # Normalization might need to handle this? Or it fails.
        },
        {
            "name": "Run-on Sentences (Missing Punctuation)",
            "description": "Extraction removes period or space between sentences.",
            "isi": "Stop taking. Call doctor.",
            "fa": "Stop taking Call doctor",
        },
        {
            "name": "URL/Email Insertion",
            "description": "Contact info inserted in the middle of safety text.",
            "isi": "Report side effects to FDA.",
            "fa": "Report side effects (www.fda.gov) to FDA.",
        },
        {
            "name": "Major Hallucination (Reverse Diff Check)",
            "description": "FA adds a safety warning not in ISI within a block.",
            "isi": "Side effects: Headache.",
            "fa": "Side effects: Headache and Instant Death.",
            # " and Instant Death." (19 chars) is < 50 chars gap.
            # It should be picked up by Contextual Extraction.
        },
    ]

    for s in scenarios:
        run_test_scenario(s["name"], s["description"], s["isi"], s["fa"])


if __name__ == "__main__":
    main()
