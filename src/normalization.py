import re


def normalize_text(text: str) -> str:
    """
    Normalizes text by joining broken lines and removing extra spaces.
    Keeps punctuation and case.
    """
    if not text:
        return ""

    # Join hyphenated words at line breaks (e.g., "impor-\ntant" -> "important")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

    # Join broken lines that are not paragraphs (basic heuristic)
    # Replace single newline with space, but keep double newline as paragraph break
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)

    # Remove extra spaces (multiple spaces -> single space)
    text = re.sub(r"\s+", " ", text)

    return text.strip()
