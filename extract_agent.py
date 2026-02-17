from typing import TypedDict, Annotated, List, Dict
from langgraph.graph import StateGraph, END
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import ContentFormat
import operator
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# ===== SIMPLIFIED STATE FOR ISI EXTRACTION =====
class ISIExtractionState(TypedDict):
    """State for ISI extraction workflow"""

    # Input
    pdf_path: str

    # Document Intelligence outputs
    markdown_content: str
    layout_pages: List[Dict]
    layout_tables: List[Dict]

    # Agent outputs
    isi_locations: List[Dict]  # Where ISI content is found
    extracted_isi_chunks: Annotated[List[Dict], operator.add]  # All ISI content pieces
    table_isi_content: List[Dict]  # ISI from tables

    # Consolidation
    consolidated_isi: str  # Complete ISI text
    isi_metadata: Dict  # Page numbers, sections, etc.

    # Validation
    completeness_score: float
    duplicates_removed: int

    # Final output
    final_isi: Dict

    # Workflow tracking
    current_step: str
    error_messages: Annotated[List[str], operator.add]


# ===== INITIALIZE CLIENTS =====
# Using Managed Identity (DefaultAzureCredential)
credential = DefaultAzureCredential()

doc_intelligence_client = DocumentIntelligenceClient(
    endpoint=os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"), credential=credential
)

# Azure OpenAI setup with Managed Identity
token_provider = get_bearer_token_provider(
    credential, "https://cognitiveservices.azure.com/.default"
)

llm = AzureChatOpenAI(
    azure_ad_token_provider=token_provider,
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
    openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
    temperature=0,
)


# ===== NODE 1: DOCUMENT INTELLIGENCE LAYOUT EXTRACTION =====
def extract_layout_node(state: ISIExtractionState) -> ISIExtractionState:
    """Extract document layout using Azure Document Intelligence"""

    print(f"Node 1: Extracting layout from {state['pdf_path']}")

    try:
        with open(state["pdf_path"], "rb") as f:
            pdf_content = f.read()

        poller = doc_intelligence_client.begin_analyze_document(
            "prebuilt-layout",
            analyze_request=pdf_content,
            content_type="application/pdf",
            output_content_format=ContentFormat.MARKDOWN,
        )

        result = poller.result()

        # Extract pages
        pages = []
        if result.pages:
            for page in result.pages:
                pages.append(
                    {
                        "page_number": page.page_number,
                        "width": page.width,
                        "height": page.height,
                        "lines": [line.content for line in page.lines]
                        if page.lines
                        else [],
                    }
                )

        # Extract tables
        tables = []
        if result.tables:
            for table in result.tables:
                table_data = {
                    "row_count": table.row_count,
                    "column_count": table.column_count,
                    "cells": [
                        {
                            "content": cell.content,
                            "row_index": cell.row_index,
                            "column_index": cell.column_index,
                        }
                        for cell in table.cells
                    ],
                }
                tables.append(table_data)

        print(f"✓ Extracted {len(pages)} pages and {len(tables)} tables")

        return {
            "markdown_content": result.content,
            "layout_pages": pages,
            "layout_tables": tables,
            "current_step": "layout_extracted",
        }

    except Exception as e:
        print(f"✗ Error in layout extraction: {str(e)}")
        return {
            "error_messages": [f"Layout extraction failed: {str(e)}"],
            "current_step": "layout_failed",
        }


# ===== NODE 2: DETECT ISI LOCATIONS =====
def detect_isi_locations_node(state: ISIExtractionState) -> ISIExtractionState:
    """Detect where ISI content is located in the document"""

    print("Node 2: Detecting ISI locations")

    prompt = f"""You are a pharmaceutical document analyst. Identify ALL locations in this document that contain Important Safety Information (ISI).

ISI is the safety-related information required by FDA for pharmaceutical marketing materials. It may include:
- Safety warnings
- Usage instructions and precautions  
- Side effects information
- Patient safety information
- Risk information

ISI can be "sprinkled" throughout the document - in headers, footers, sidebars, small text sections, or interspersed with marketing content.

Document (Markdown with preserved structure):
{state["markdown_content"]}

Instructions:
1. Identify EVERY location where ISI appears (even if scattered)
2. Look for small text, footnotes, sidebars, boxed sections
3. Distinguish ISI from marketing/promotional content
4. Note if ISI spans multiple pages

Return JSON:
{{
    "isi_locations": [
        {{
            "location_description": "Footer of pages 1-3",
            "content_preview": "first 200 chars of ISI content found here",
            "estimated_pages": [1, 2, 3],
            "format": "small_text|sidebar|footer|header|body|table",
            "confidence": 0.0-1.0
        }}
    ],
    "isi_distribution": "concentrated|sprinkled|both",
    "total_isi_sections": 5
}}"""

    try:
        messages = [
            SystemMessage(
                content="You are an expert at identifying ISI content in pharmaceutical marketing materials."
            ),
            HumanMessage(content=prompt),
        ]

        response = llm.invoke(messages)
        detection_result = json.loads(response.content)

        locations = detection_result.get("isi_locations", [])
        print(f"✓ Detected ISI in {len(locations)} locations")
        print(f"✓ Distribution: {detection_result.get('isi_distribution', 'unknown')}")

        return {
            "isi_locations": locations,
            "isi_metadata": {
                "distribution": detection_result.get("isi_distribution"),
                "total_sections": detection_result.get("total_isi_sections", 0),
            },
            "current_step": "locations_detected",
        }

    except Exception as e:
        print(f"✗ Error in ISI detection: {str(e)}")
        return {
            "error_messages": [f"ISI detection failed: {str(e)}"],
            "current_step": "detection_failed",
        }


# ===== NODE 3: EXTRACT ISI CONTENT FROM ALL LOCATIONS =====
def extract_isi_content_node(state: ISIExtractionState) -> ISIExtractionState:
    """Extract complete ISI content from all detected locations"""

    print("Node 3: Extracting ISI content from all locations")

    isi_locations = state.get("isi_locations", [])

    prompt = f"""Extract the COMPLETE Important Safety Information (ISI) from this pharmaceutical document.

The ISI may be scattered across multiple locations. Extract ALL ISI content and consolidate it.

Document:
{state["markdown_content"]}

Detected ISI locations:
{json.dumps(isi_locations, indent=2)}

Instructions:
1. Extract ALL ISI text from every location identified
2. Preserve the original wording exactly
3. Maintain logical flow and organization
4. Track which pages each piece comes from
5. Ignore marketing/promotional content

Return JSON:
{{
    "isi_chunks": [
        {{
            "content": "complete ISI text from this section",
            "source_location": "footer pages 1-3",
            "page_numbers": [1, 2, 3],
            "text_format": "small_text|normal|bold",
            "word_count": 150
        }}
    ]
}}"""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        extraction_result = json.loads(response.content)

        isi_chunks = extraction_result.get("isi_chunks", [])
        total_words = sum(chunk.get("word_count", 0) for chunk in isi_chunks)

        print(f"✓ Extracted {len(isi_chunks)} ISI chunks")
        print(f"✓ Total ISI word count: ~{total_words}")

        return {"extracted_isi_chunks": isi_chunks, "current_step": "isi_extracted"}

    except Exception as e:
        print(f"✗ Error extracting ISI: {str(e)}")
        return {
            "extracted_isi_chunks": [],
            "error_messages": [f"ISI extraction failed: {str(e)}"],
        }


# ===== NODE 4: EXTRACT ISI FROM TABLES =====
def extract_table_isi_node(state: ISIExtractionState) -> ISIExtractionState:
    """Extract ISI content specifically from tables"""

    print("Node 4: Extracting ISI from Tables")

    if not state.get("layout_tables"):
        print("✓ No tables found")
        return {"table_isi_content": [], "current_step": "table_extraction_complete"}

    table_isi = []

    for idx, table in enumerate(state["layout_tables"]):
        # Convert table to markdown
        table_md = convert_table_to_markdown(table)

        prompt = f"""Does this table contain Important Safety Information (ISI)?

Table {idx + 1}:
{table_md}

If it contains ISI (safety data, side effects, risk information, etc.), extract the complete content.

Return:
{{
    "contains_isi": true/false,
    "isi_content": "full ISI text from table if contains_isi is true",
    "table_type": "adverse_reactions|dosing|safety_data|other"
}}"""

        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            result = json.loads(response.content)

            if result.get("contains_isi"):
                table_isi.append(
                    {
                        "table_index": idx + 1,
                        "content": result.get("isi_content", ""),
                        "table_type": result.get("table_type", "other"),
                    }
                )

        except Exception as e:
            print(f"✗ Error processing table {idx + 1}: {str(e)}")

    print(f"✓ Found ISI in {len(table_isi)} tables")

    return {"table_isi_content": table_isi, "current_step": "table_extraction_complete"}


def convert_table_to_markdown(table: Dict) -> str:
    """Helper: Convert Document Intelligence table to markdown"""
    rows = table["row_count"]
    cols = table["column_count"]
    matrix = [["" for _ in range(cols)] for _ in range(rows)]

    for cell in table["cells"]:
        matrix[cell["row_index"]][cell["column_index"]] = cell["content"]

    md = "| " + " | ".join(matrix[0]) + " |\n"
    md += "| " + " | ".join(["---"] * cols) + " |\n"
    for row in matrix[1:]:
        md += "| " + " | ".join(row) + " |\n"

    return md


# ===== NODE 5: CONSOLIDATE & DEDUPLICATE ISI =====
def consolidate_isi_node(state: ISIExtractionState) -> ISIExtractionState:
    """Consolidate all ISI chunks and remove duplicates from sprinkled content"""

    print("🔗 Node 5: Consolidating and Deduplicating ISI")

    isi_chunks = state.get("extracted_isi_chunks", [])
    table_isi = state.get("table_isi_content", [])

    prompt = f"""Consolidate this Important Safety Information (ISI) that was extracted from multiple locations in a pharmaceutical document.

ISI Chunks from Document:
{json.dumps(isi_chunks, indent=2)}

ISI from Tables:
{json.dumps(table_isi, indent=2)}

Tasks:
1. Combine all ISI content into a single, coherent document
2. Remove duplicates (ISI sprinkled across pages may have been extracted multiple times)
3. Maintain logical organization and flow
4. Preserve all unique safety information
5. Track which pages the ISI came from

Return JSON:
{{
    "consolidated_isi": "Complete, deduplicated ISI text with proper formatting and structure",
    "page_coverage": [1, 2, 3, 4, 5],
    "sections_found": ["safety warnings", "usage information", "side effects"],
    "duplicates_removed": 3,
    "total_word_count": 850,
    "completeness_score": 0.95,
    "notes": "Any important observations about the ISI"
}}"""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        consolidation_result = json.loads(response.content)

        print("Consolidated ISI")
        print(f"Page coverage: {consolidation_result.get('page_coverage', [])}")
        print(f"Removed {consolidation_result.get('duplicates_removed', 0)} duplicates")
        print(f"Completeness: {consolidation_result.get('completeness_score', 0)}")

        # Update metadata with page coverage
        metadata = state.get("isi_metadata", {})
        metadata.update(
            {
                "page_coverage": consolidation_result.get("page_coverage", []),
                "sections_found": consolidation_result.get("sections_found", []),
                "total_word_count": consolidation_result.get("total_word_count", 0),
            }
        )

        return {
            "consolidated_isi": consolidation_result.get("consolidated_isi", ""),
            "isi_metadata": metadata,
            "completeness_score": consolidation_result.get("completeness_score", 0.0),
            "duplicates_removed": consolidation_result.get("duplicates_removed", 0),
            "final_isi": {
                "isi_content": consolidation_result.get("consolidated_isi", ""),
                "metadata": metadata,
                "completeness_score": consolidation_result.get(
                    "completeness_score", 0.0
                ),
                "notes": consolidation_result.get("notes", ""),
            },
            "current_step": "consolidation_complete",
        }

    except Exception as e:
        print(f"Error in consolidation: {str(e)}")
        # Return unconsolidated data
        return {
            "consolidated_isi": "\n\n".join(
                [chunk.get("content", "") for chunk in isi_chunks]
            ),
            "completeness_score": 0.5,
            "duplicates_removed": 0,
            "error_messages": [f"Consolidation failed: {str(e)}"],
            "current_step": "consolidation_failed",
        }


# ===== BUILD THE LANGGRAPH WORKFLOW =====
def build_isi_extraction_graph():
    """Build the simplified ISI extraction workflow"""

    workflow = StateGraph(ISIExtractionState)

    # Add nodes (simplified pipeline)
    workflow.add_node("extract_layout", extract_layout_node)
    workflow.add_node("detect_isi_locations", detect_isi_locations_node)
    workflow.add_node("extract_isi_content", extract_isi_content_node)
    workflow.add_node("extract_table_isi", extract_table_isi_node)
    workflow.add_node("consolidate_isi", consolidate_isi_node)

    # Define linear flow with parallel table extraction
    workflow.set_entry_point("extract_layout")
    workflow.add_edge("extract_layout", "detect_isi_locations")
    workflow.add_edge("detect_isi_locations", "extract_isi_content")
    workflow.add_edge("detect_isi_locations", "extract_table_isi")

    # Both content and table extraction flow to consolidation
    workflow.add_edge("extract_isi_content", "consolidate_isi")
    workflow.add_edge("extract_table_isi", "consolidate_isi")

    # End after consolidation
    workflow.add_edge("consolidate_isi", END)

    return workflow.compile()


# ===== EXECUTE THE WORKFLOW =====
if __name__ == "__main__":
    # Build graph
    app = build_isi_extraction_graph()

    # Initial state
    initial_state = {
        "pdf_path": "final_asset_drug_brochure.pdf",
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
        "current_step": "initialized",
        "error_messages": [],
    }

    print("Starting ISI Extraction Workflow\n")

    # Run the graph
    final_state = app.invoke(initial_state)

    # Output results
    print("\n" + "=" * 60)
    print("FINAL ISI EXTRACTION RESULTS")
    print("=" * 60)
    print(f"\nCompleteness Score: {final_state['completeness_score']}")
    print(f"Duplicates Removed: {final_state['duplicates_removed']}")
    print(f"Pages Covered: {final_state['isi_metadata'].get('page_coverage', [])}")
    print(f"Word Count: {final_state['isi_metadata'].get('total_word_count', 0)}")
    print(f"\n{'=' * 60}")
    print("EXTRACTED ISI CONTENT:")
    print("=" * 60)
    print(final_state["consolidated_isi"])

    # Save to file
    with open("extracted_isi_langgraph.json", "w") as f:
        json.dump(final_state["final_isi"], f, indent=2)

    # Also save as plain text
    with open("extracted_isi_content.txt", "w") as f:
        f.write(final_state["consolidated_isi"])

    print("\nISI extraction complete!")
    print("Saved to: extracted_isi_langgraph.json and extracted_isi_content.txt")
