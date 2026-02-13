import re
import numpy as np
from rapidfuzz import fuzz
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI


# ============================================================
#                 AZURE OPENAI (MANAGED IDENTITY)
# ============================================================

AZURE_ENDPOINT = "https://YOUR-RESOURCE-NAME.openai.azure.com/"
EMBEDDING_DEPLOYMENT = "text-embedding-3-large"
API_VERSION = "2024-02-01"

token_provider = get_bearer_token_provider(
    DefaultAzureCredential(),
    "https://cognitiveservices.azure.com/.default"
)

client = AzureOpenAI(
    azure_endpoint=AZURE_ENDPOINT,
    azure_ad_token_provider=token_provider,
    api_version=API_VERSION
)


# ============================================================
#                     TEXT NORMALIZATION
# ============================================================

def normalize_text(text: str) -> str:
    text = re.sub(r'[®™©]', '', text)
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    text = text.replace('\u200b', '')
    text = text.replace('\xad', '-')
    text = re.sub(r'(\w)-\s+(\w)', r'\1\2', text)
    text = re.sub(r'[-–—]', '-', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# ============================================================
#                      EMBEDDINGS
# ============================================================

def embed(text: str):
    response = client.embeddings.create(
        model=EMBEDDING_DEPLOYMENT,
        input=text
    )
    return response.data[0].embedding


def cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


# ============================================================
#                    DOCUMENT CHUNKING
# ============================================================

def chunk_document(text, size=120, overlap=40):
    words = text.split()
    chunks = []

    for i in range(0, len(words), size - overlap):
        chunk = " ".join(words[i:i+size])
        if len(chunk) > 40:
            chunks.append(chunk)

    return chunks


# ============================================================
#                SEMANTIC ISI LOCATOR (AI PART)
# ============================================================

def locate_isi_semantic(fa_text: str, golden_isi: str, threshold=0.88):

    fa_text = normalize_text(fa_text)
    golden_isi = normalize_text(golden_isi)

    fa_chunks = chunk_document(fa_text)
    print(f"\nCreated {len(fa_chunks)} searchable FA chunks")

    print("Embedding FA document (one-time)...")
    fa_embeddings = [embed(chunk) for chunk in fa_chunks]

    matches = []

    for line in golden_isi.splitlines():

        line = line.strip()
        if len(line) < 25:
            continue

        print(f"\nSearching: {line[:70]}...")

        g_emb = embed(line)

        best_score = 0
        best_chunk = ""

        for chunk, c_emb in zip(fa_chunks, fa_embeddings):
            score = cosine_similarity(g_emb, c_emb)

            if score > best_score:
                best_score = score
                best_chunk = chunk

        print(f"Best semantic score: {best_score:.3f}")

        if best_score >= threshold:
            matches.append((line, best_chunk, best_score))
            print(" -> ISI FOUND")
        else:
            print(" -> ISI NOT FOUND")

    return matches


# ============================================================
#              EXACT REGULATORY VERIFICATION
# ============================================================

def verify_with_fuzzy(semantic_matches, threshold=0.88):

    verified = []

    for golden, found, semantic_score in semantic_matches:

        fuzzy_score = fuzz.token_set_ratio(
            normalize_text(golden).lower(),
            normalize_text(found).lower()
        ) / 100

        verified.append((golden, found, semantic_score, fuzzy_score))

    return verified


# ============================================================
#                    METRICS
# ============================================================

def coverage_ratio(verified_matches, total_isi_lines):
    present = sum(1 for _, _, _, fuzzy in verified_matches if fuzzy >= 0.88)
    return present / total_isi_lines if total_isi_lines else 0


def authenticity_ratio(verified_matches):
    authentic = sum(1 for _, _, _, fuzzy in verified_matches if fuzzy >= 0.88)
    return authentic / len(verified_matches) if verified_matches else 0


# ============================================================
#                        MAIN
# ============================================================

if __name__ == "__main__":

    FA_TEXT = """
    Product brochure marketing content.

    IMPORTANT SAFETY INFORMATION

    Liver damage may occur during therapy.
    Monitor liver enzymes before and during treatment.

    Hypersensitivity to drug components is a contraindication.

    Do not exceed 100 mg per day.
    Contact physician if symptoms continue after one week.
    """

    GOLDEN_ISI = """
    Serious risk of hepatotoxicity. Monitor liver function tests before and during treatment.
    Hypersensitivity to the active substance or excipients.
    Do not exceed 100 mg daily. Consult physician if symptoms persist beyond 7 days.
    """

    print("\n=========== STEP 1: AI SEMANTIC DETECTION ===========")
    semantic_matches = locate_isi_semantic(FA_TEXT, GOLDEN_ISI)

    print("\n=========== STEP 2: EXACT WORDING CHECK =============")
    verified = verify_with_fuzzy(semantic_matches)

    total_lines = len([l for l in GOLDEN_ISI.splitlines() if len(l.strip()) > 25])

    coverage = coverage_ratio(verified, total_lines)
    authenticity = authenticity_ratio(verified)

    print("\n================ FINAL RESULTS =================")

    for g, f, sem, fuzz_score in verified:
        print("\n----------------------------------")
        print("GOLDEN ISI :", g)
        print("FOUND TEXT :", f[:200])
        print(f"Semantic Score : {sem:.3f}")
        print(f"Fuzzy Score    : {fuzz_score:.3f}")

    print("\n----------------------------------")
    print(f"COVERAGE RATIO     : {coverage:.2%}")
    print(f"AUTHENTICITY RATIO : {authenticity:.2%}")
