import sys
import os
import argparse
from dotenv import load_dotenv

from src.extraction import extract_text_from_pdf
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


def main():
    parser = argparse.ArgumentParser(
        description="Compliance Checker: Compare ISI vs FA"
    )
    parser.add_argument("isi_pdf", help="Path to ISI PDF")
    parser.add_argument("fa_pdf", help="Path to FA PDF")
    args = parser.parse_args()

    # Load env
    load_dotenv()

    if not os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"):
        print("Error: AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT not found in .env file.")
        print("Please set it to use Azure Document Intelligence.")
        sys.exit(1)

    print(f"Processing ISI: {args.isi_pdf}")
    print(f"Processing FA:  {args.fa_pdf}")

    try:
        # 1. Extraction
        print("\n--- Step 1: Extracting Text ---")
        isi_text_raw = extract_text_from_pdf(args.isi_pdf)
        fa_text_raw = extract_text_from_pdf(args.fa_pdf)

        print(f"ISI Raw Length: {len(isi_text_raw)} chars")
        print(f"FA Raw Length:  {len(fa_text_raw)} chars")

        # 2. Normalization
        print("\n--- Step 2: Normalizing Text ---")
        isi_norm = normalize_text(isi_text_raw)
        fa_norm = normalize_text(fa_text_raw)

        # 3. Alignment
        print("\n--- Step 3: Aligning & Matching ---")
        matches, isi_tokens, fa_tokens = get_isi_matches_in_fa(isi_norm, fa_norm)
        print(f"Found {len(matches)} matching blocks.")

        # 4. Extract ISI From FA
        print("\n--- Step 4: Extracting ISI From FA ---")
        extracted_isi = extract_contextual_isi(
            fa_norm, fa_tokens, matches, max_gap=50
        )
        print(
            f'Extracted ISI from FA: "{extracted_isi[:100]}..."'
            if len(extracted_isi) > 100
            else f'Extracted ISI from FA: "{extracted_isi}"'
        )

        # 5. Metrics
        print("\n--- Step 5: Calculating Metrics ---")
        coverage = calculate_coverage(isi_tokens, matches)
        authenticity = calculate_authenticity(isi_norm, extracted_isi)

        print("\n" + "=" * 30)
        print("       COMPLIANCE REPORT       ")
        print("=" * 30)
        print(f"Coverage Score:    {coverage:.2%}")
        print(f"Authenticity Score: {authenticity:.2%}")
        print("-" * 30)

        # Detailed Report
        missing_segments = get_simple_diff(isi_norm, fa_norm)

        if missing_segments:
            print("\n[MISSING ISI SEGMENTS (Simple Diff)]")
            for i, seg in enumerate(missing_segments, 1):
                print(f'{i}. "{seg}"')
        else:
            print("\n[NO MISSING ISI SEGMENTS FOUND]")

        # Reverse Diff (Additions)
        additions = get_unexpected_additions(isi_norm, extracted_isi)

        if additions:
            print("\n[UNEXPECTED ADDITIONS (Reverse Diff)]")
            for i, seg in enumerate(additions, 1):
                print(f'{i}. "{seg}"')
        else:
            print("\n[NO UNEXPECTED ADDITIONS FOUND]")

        edits = get_edits(isi_norm, extracted_isi)
        if edits:
            print("\n[AUTHENTICITY ISSUES (EDITS)]")
            # Limit to first 10 edits to avoid spamming console
            for i, edit in enumerate(edits[:10], 1):
                print(f"{i}. {edit}")
            if len(edits) > 10:
                print(f"... and {len(edits) - 10} more.")
        else:
            print("\n[NO TEXT DIFFERENCES FOUND]")

        print("=" * 30)

    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
