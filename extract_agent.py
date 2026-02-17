from typing import TypedDict, Annotated, List, Dict, Optional
import operator
import os
from dotenv import load_dotenv
from rapidfuzz import fuzz, distance

from langgraph.graph import StateGraph, END
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from pydantic import BaseModel
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.ai.documentintelligence import DocumentIntelligenceClient

# =========================================================
# ENV
# =========================================================
load_dotenv()

# =========================================================
# STRUCTURED OUTPUT SCHEMAS  (THIS FIXES JSON ERRORS)
# =========================================================


class ISILocation(BaseModel):
    location_description: str
    content_preview: str
    estimated_pages: List[int]
    format: str
    confidence: float


class ISIDetectionResult(BaseModel):
    isi_locations: List[ISILocation]
    isi_distribution: str
    total_isi_sections: int


class ISIChunk(BaseModel):
    content: str
    source_location: str
    page_numbers: List[int]
    text_format: str
    word_count: int


class ISIExtractionResult(BaseModel):
    isi_chunks: List[ISIChunk]


class ISIConsolidationResult(BaseModel):
    consolidated_isi: str
    page_coverage: List[int]
    sections_found: List[str]
    duplicates_removed: int
    total_word_count: int
    completeness_score: float
    notes: str


class ComparisonResult(BaseModel):
    similarity_score: float
    missing_content: List[str]
    extra_content: List[str]
    notes: str


class ReasoningResult(BaseModel):
    final_score: float
    reasoning: str
    breakdown: Dict[str, float]


# =========================================================
# LANGGRAPH STATE
# =========================================================


class ISIExtractionState(TypedDict):
    pdf_path: str
    original_isi_text: str  # Input: The ground truth ISI text

    markdown_content: str
    layout_pages: List[Dict]
    layout_tables: List[Dict]

    isi_locations: List[Dict]
    extracted_isi_chunks: Annotated[List[Dict], operator.add]
    table_isi_content: List[Dict]

    consolidated_isi: str
    isi_metadata: Dict

    completeness_score: float
    duplicates_removed: int

    final_isi: Dict

    # Comparison & Reasoning
    comparison_original_fa: Dict  # Original ISI vs FA Document
    comparison_extracted_original: Dict  # Extracted ISI vs Original ISI
    final_score_reasoning: Dict  # Final LLM analysis

    current_step: str
    error_messages: Annotated[List[str], operator.add]


# =========================================================
# AZURE CLIENTS
# =========================================================

credential = DefaultAzureCredential()

doc_client = DocumentIntelligenceClient(
    endpoint=os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"), credential=credential
)

token_provider = get_bearer_token_provider(
    credential, "https://cognitiveservices.azure.com/.default"
)

base_llm = AzureChatOpenAI(
    azure_ad_token_provider=token_provider,
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
    openai_api_version="2024-02-15-preview",
    temperature=0,
    max_retries=3,
)

# =========================================================
# NODE 1 — LAYOUT EXTRACTION
# =========================================================


def extract_layout_node(state: ISIExtractionState) -> ISIExtractionState:

    try:
        with open(state["pdf_path"], "rb") as f:
            pdf_bytes = f.read()

        poller = doc_client.begin_analyze_document(
            "prebuilt-layout",
            body=pdf_bytes,
            content_type="application/pdf",
        )

        result = poller.result()

        pages = []
        for page in result.pages:
            pages.append(
                {
                    "page_number": page.page_number,
                    "lines": [line.content for line in page.lines]
                    if page.lines
                    else [],
                }
            )

        tables = []
        if result.tables:
            for table in result.tables:
                tables.append(
                    {
                        "row_count": table.row_count,
                        "column_count": table.column_count,
                        "cells": [
                            {
                                "content": c.content,
                                "row_index": c.row_index,
                                "column_index": c.column_index,
                            }
                            for c in table.cells
                        ],
                    }
                )

        return {
            "markdown_content": result.content,
            "layout_pages": pages,
            "layout_tables": tables,
            "current_step": "layout_extracted",
        }

    except Exception as e:
        return {"error_messages": [str(e)]}


# =========================================================
# NODE 2 — DETECT ISI
# =========================================================


def detect_isi_locations_node(state: ISIExtractionState) -> ISIExtractionState:

    llm = base_llm.with_structured_output(ISIDetectionResult)

    messages = [
        SystemMessage(
            content="You identify Important Safety Information in pharma documents."
        ),
        HumanMessage(
            content=f"""
Find all Important Safety Information in this document.

{state["markdown_content"]}
"""
        ),
    ]

    result: ISIDetectionResult = llm.invoke(messages)

    return {
        "isi_locations": [loc.model_dump() for loc in result.isi_locations],
        "isi_metadata": {
            "distribution": result.isi_distribution,
            "total_sections": result.total_isi_sections,
        },
        "current_step": "locations_detected",
    }


# =========================================================
# NODE 3 — EXTRACT ISI TEXT
# =========================================================


def extract_isi_content_node(state: ISIExtractionState) -> ISIExtractionState:

    llm = base_llm.with_structured_output(ISIExtractionResult)

    result: ISIExtractionResult = llm.invoke(f"""
Extract COMPLETE Important Safety Information.

Document:
{state["markdown_content"]}

Locations:
{state["isi_locations"]}
""")

    return {
        "extracted_isi_chunks": [c.model_dump() for c in result.isi_chunks],
        "current_step": "isi_extracted",
    }


# =========================================================
# NODE 4 — TABLE ISI
# =========================================================


def extract_table_isi_node(state: ISIExtractionState) -> ISIExtractionState:

    if not state["layout_tables"]:
        return {"table_isi_content": []}

    table_results = []

    for idx, table in enumerate(state["layout_tables"]):
        text = " ".join(cell["content"] for cell in table["cells"])

        if any(
            x in text.lower()
            for x in [
                "adverse",
                "warning",
                "contraindication",
                "side effect",
                "toxicity",
            ]
        ):
            table_results.append(
                {"table_index": idx, "content": text, "table_type": "safety_data"}
            )

    return {"table_isi_content": table_results}


# =========================================================
# JOIN NODE (FIXES LANGGRAPH RACE CONDITION)
# =========================================================


def join_node(state: ISIExtractionState) -> ISIExtractionState:
    return state


# =========================================================
# NODE 5 — CONSOLIDATION
# =========================================================


def consolidate_isi_node(state: ISIExtractionState) -> ISIExtractionState:

    llm = base_llm.with_structured_output(ISIConsolidationResult)

    result: ISIConsolidationResult = llm.invoke(f"""
Combine and deduplicate all ISI.

Chunks:
{state["extracted_isi_chunks"]}

Tables:
{state["table_isi_content"]}
""")

    metadata = state.get("isi_metadata", {})
    metadata["page_coverage"] = result.page_coverage
    metadata["sections_found"] = result.sections_found
    metadata["total_word_count"] = result.total_word_count

    return {
        "consolidated_isi": result.consolidated_isi,
        "isi_metadata": metadata,
        "duplicates_removed": result.duplicates_removed,
        "completeness_score": result.completeness_score,
        "final_isi": {
            "isi_content": result.consolidated_isi,
            "metadata": metadata,
            "completeness_score": result.completeness_score,
            "notes": result.notes,
        },
    }


# =========================================================
# BUILD GRAPH
# =========================================================


# =========================================================
# HELPER: SCORING FUNCTION
# =========================================================


def calculate_compliance_score(text1: str, text2: str) -> Dict:
    """Calculate multi-algorithm compliance score between two texts."""

    # 1. Token Set Ratio (30%) - Content coverage
    token_set = fuzz.token_set_ratio(text1, text2)

    # 2. Sequence Matcher (25%) - Order preservation
    sequence_matcher = fuzz.ratio(text1, text2)

    # 3. Token Sort (20%) - Order-agnostic
    token_sort = fuzz.token_sort_ratio(text1, text2)

    # 4. Partial Ratio (15%) - Substring matching
    partial = fuzz.partial_ratio(text1, text2)

    # 5. Levenshtein (10%) - Character-level
    levenshtein = distance.Levenshtein.normalized_similarity(text1, text2) * 100

    # Calculate Weighted Score
    final_score = (
        (token_set * 0.30)
        + (sequence_matcher * 0.25)
        + (token_sort * 0.20)
        + (partial * 0.15)
        + (levenshtein * 0.10)
    )

    return {
        "final_weighted_score": round(final_score, 2),
        "metrics": {
            "token_set_ratio": round(token_set, 2),
            "sequence_matcher": round(sequence_matcher, 2),
            "token_sort_ratio": round(token_sort, 2),
            "partial_ratio": round(partial, 2),
            "levenshtein": round(levenshtein, 2),
        },
    }


# =========================================================
# NODE 6 — COMPARE ORIGINAL ISI vs FA
# =========================================================


def compare_original_fa_node(state: ISIExtractionState) -> ISIExtractionState:
    """Compare Original ISI text against the full FA content (markdown) using RapidFuzz."""

    if not state.get("original_isi_text"):
        return {"comparison_original_fa": {"error": "No original ISI text provided"}}

    original = state["original_isi_text"]
    fa_content = state["markdown_content"]

    # Use shared scoring logic
    result = calculate_compliance_score(original, fa_content)

    return {"comparison_original_fa": result}


# =========================================================
# NODE 7 — COMPARE EXTRACTED ISI vs ORIGINAL ISI
# =========================================================


def compare_extracted_original_node(state: ISIExtractionState) -> ISIExtractionState:
    """Compare Extracted ISI against Original ISI to verify extraction accuracy."""

    if not state.get("original_isi_text"):
        return {
            "comparison_extracted_original": {"error": "No original ISI text provided"}
        }

    original = state["original_isi_text"]
    extracted = state["consolidated_isi"]

    # Use shared scoring logic
    result = calculate_compliance_score(extracted, original)

    return {"comparison_extracted_original": result}


# =========================================================
# NODE 8 — REASONING & SCORING
# =========================================================


def reasoning_scoring_node(state: ISIExtractionState) -> ISIExtractionState:
    """Final LLM analysis with weighted scoring."""

    llm = base_llm.with_structured_output(ReasoningResult)

    prompt = f"""Analyze the compliance of the extracted ISI against the Original ISI.

Original ISI vs FA (Multi-Algorithm Metrics): {state.get("comparison_original_fa")}
Extracted ISI vs Original ISI (Multi-Algorithm Metrics): {state.get("comparison_extracted_original")}
Extracted Metadata: {state.get("isi_metadata")}

Provide a final compliance score (0-100) based on the computed metrics and your analysis.
Focus on:
1. Completeness (Did we miss anything?)
2. Accuracy (Is the text faithful?)

Return reasoning for the score and the breakdown.
"""

    result: ReasoningResult = llm.invoke(prompt)

    return {"final_score_reasoning": result.model_dump()}


# =========================================================
# BUILD GRAPH
# =========================================================


def build_graph():
    g = StateGraph(ISIExtractionState)

    g.add_node("layout", extract_layout_node)
    g.add_node("detect", detect_isi_locations_node)
    g.add_node("extract", extract_isi_content_node)
    g.add_node("table", extract_table_isi_node)
    g.add_node("join", join_node)
    g.add_node("consolidate", consolidate_isi_node)

    g.add_node("compare_original_fa", compare_original_fa_node)
    g.add_node("compare_extracted_original", compare_extracted_original_node)
    g.add_node("reasoning", reasoning_scoring_node)

    g.set_entry_point("layout")
    g.add_edge("layout", "detect")

    g.add_edge("detect", "extract")
    g.add_edge("detect", "table")
    g.add_edge("detect", "compare_original_fa")  # Can run parallel to extraction

    g.add_edge("extract", "join")
    g.add_edge("table", "join")

    g.add_edge("join", "consolidate")

    g.add_edge("consolidate", "compare_extracted_original")
    g.add_edge("compare_extracted_original", "reasoning")
    g.add_edge("compare_original_fa", "reasoning")

    g.add_edge("reasoning", END)

    return g.compile()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    app = build_graph()

    initial_state = {
        "pdf_path": "dummy_isi.pdf",
        "original_isi_text": "Important Safety Information: This drug may cause side effects.",  # Dummy Original ISI
        "markdown_content": "",
        "layout_pages": [],
        "layout_tables": [],
        "isi_locations": [],
        "extracted_isi_chunks": [],
        "table_isi_content": [],
        "consolidated_isi": "",
        "isi_metadata": {},
        "completeness_score": 0.0,
        "duplicates_removed": 0,
        "final_isi": {},
        "current_step": "start",
        "error_messages": [],
        "comparison_original_fa": {},
        "comparison_extracted_original": {},
        "final_score_reasoning": {},
    }

    result = app.invoke(initial_state)

    print("\nCOMPLETENESS:", result["completeness_score"])
    print("\nFINAL SCORE:", result.get("final_score_reasoning", {}).get("final_score"))
    print("\nREASONING:", result.get("final_score_reasoning", {}).get("reasoning"))
    print("\nISI:\n")
    print(result["consolidated_isi"])
