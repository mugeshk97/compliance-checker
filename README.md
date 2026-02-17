# 🏥 Pharma ISI Compliance Agent

An advanced AI agent designed to verify **Important Safety Information (ISI)** compliance in pharmaceutical promotional materials.

Built with **LangGraph**, **Azure OpenAI**, and **Azure Document Intelligence**, this tool autonomously extracts, consolidates, and validates safety information against approved reference text.

## 🚀 Key Features

*   **⚡ Agentic Workflow**: Uses a defined state machine (Directed Acyclic Graph) to orchestrate complex verification steps.
*   **📄 Semantic Extraction**: Uses **LLM semantic extraction** (GPT-4o) to contextualize and extract safety data effectively.
*   **🔍 Dual-Path Verification**:
    1.  **Broad Search**: Scans the *entire document* to ensure safety concepts are present anywhere.
    2.  **Precision Check**: Validates the *extracted text* against the official source for verbatim accuracy.
*   **📊 Deterministic Scoring**: Uses **RapidFuzz** (Levenshtein, Token Sort, Set Ratio) for objective similarity metrics, avoiding "LLM vibe checks."
*   **🧩 Structured Outputs**: Enforces strict JSON schemas using Pydantic to ensure reliable downstream processing.

## 🛠️ Architecture

The agent follows a multi-step graph architecture:

```mermaid
graph TD
    Start([Start]) --> Layout[Layout Extraction<br/>(Azure Doc Intelligence)]
    Layout --> Detect[Detect ISI Locations]
    
    Detect --> Extract[LLM Extraction]
    Detect --> CompareGlobal[Compare: Global Search]
    
    Extract --> Consolidate[Consolidate & Deduplicate]
    
    Consolidate --> CompareLocal[Compare: Extracted Text]
    
    CompareGlobal --> Reasoning[Final Reasoning & Scoring]
    CompareLocal --> Reasoning
    
    Reasoning --> End([End])
```

## 📦 Installation

This project is managed with `uv`.

```bash
# Install dependencies
uv sync
```

### Dependencies
-   `langgraph`: State orchestration
-   `langchain-openai`: LLM interface
-   `azure-ai-documentintelligence`: Layout analysis
-   `rapidfuzz`: Fuzzy string matching scoring

## ⚙️ Configuration

Create a `.env` file in the root directory:

```ini
# Azure OpenAI
AZURE_OPENAI_ENDPOINT="https://<your-resource>.openai.azure.com/"
AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4o"
AZURE_OPENAI_API_VERSION="2024-02-15-preview"

# Azure Document Intelligence
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT="https://<your-resource>.cognitiveservices.azure.com/"

# Authentication
# Uses DefaultAzureCredential (CLI login or Managed Identity)
# OR API Keys (Optional)
AZURE_OPENAI_API_KEY=""
AZURE_DOCUMENT_INTELLIGENCE_KEY=""
```

## 🏃 Usage

Run the agent directly:

```bash
# Run the extraction agent
uv run python extract_agent.py
```

### Input/Output
-   **Input**: PDF Document & "Ground Truth" Original ISI Text.
-   **Output**: 
    -   Compliance Score (0-100)
    -   Missing/Extra Content Analysis
    -   Consolidated ISI Text

## 🧠 Logic Breakdown

### 1. Layout Analysis
We don't just read text; we read **structure**. Azure Document Intelligence provides spatial awareness, allowing us to identify tables and reading order correctly.

### 2. Multi-Metric Scoring
Compliance isn't binary. We use a weighted score:
-   **30% Token Set Ratio**: Did we cover the key terms?
-   **25% Sequence Matcher**: Is the order correct?
-   **20% Token Sort**: Are all words present regardless of order?
-   **15% Partial Ratio**: Are substrings matching?
-   **10% Levenshtein**: Character-level precision.

### 3. Reasoning
The final node uses an LLM to interpret these hard metrics. It distinguishes between *critical omissions* (missing a warning) vs. *formatting differences* via a "Reasoning" step.
