# Compliance Checker

A tool to verify pharmaceutical promotional compliance by comparing an "ISI" (Important Safety Information) document against a "FA" (Promotional Material) document.

## Setup

1.  **Install Dependencies**:
    ```bash
    uv add azure-ai-documentintelligence python-dotenv
    ```
    (or just `uv sync`)

2.  **Configure Credentials**:
    Create a `.env` file in the root directory with:
    ```
    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT="https://<your-endpoint>.cognitiveservices.azure.com/"
    AZURE_DOCUMENT_INTELLIGENCE_KEY="<your-key>"
    ```

3.  **Prepare Data**:
    Place your `isi.pdf` and `fa.pdf` in a directory (e.g., `data/`).

## Usage

Run the checker:

```bash
uv run python main.py <path_to_isi> <path_to_fa>
```

Example:

```bash
uv run python main.py data/isi.pdf data/fa.pdf
```

## Output

The tool will output:
-   **Coverage Score**: Percentage of ISI text found in FA.
-   **Authenticity Score**: Accuracy of the copied ISI text.
