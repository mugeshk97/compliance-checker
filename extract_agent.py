from typing import TypedDict, Annotated, List, Dict
import operator
import os
from dotenv import load_dotenv

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


# =========================================================
# LANGGRAPH STATE
# =========================================================


class ISIExtractionState(TypedDict):
    pdf_path: str

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


def build_graph():
    g = StateGraph(ISIExtractionState)

    g.add_node("layout", extract_layout_node)
    g.add_node("detect", detect_isi_locations_node)
    g.add_node("extract", extract_isi_content_node)
    g.add_node("table", extract_table_isi_node)
    g.add_node("join", join_node)
    g.add_node("consolidate", consolidate_isi_node)

    g.set_entry_point("layout")
    g.add_edge("layout", "detect")

    g.add_edge("detect", "extract")
    g.add_edge("detect", "table")

    g.add_edge("extract", "join")
    g.add_edge("table", "join")

    g.add_edge("join", "consolidate")
    g.add_edge("consolidate", END)

    return g.compile()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    app = build_graph()

    initial_state = {
        "pdf_path": "dummy_isi.pdf",
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
    }

    result = app.invoke(initial_state)

    print("\nCOMPLETENESS:", result["completeness_score"])
    print("\nISI:\n")
    print(result["consolidated_isi"])
