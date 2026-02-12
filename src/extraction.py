import os
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeResult
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extracts text from a PDF using Azure Document Intelligence (Layout model).
    Supports API Key or Managed Identity.
    """
    endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")

    if not endpoint:
        raise ValueError("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT not found in .env")

    if key:
        credential = AzureKeyCredential(key)
    else:
        print(
            "AZURE_DOCUMENT_INTELLIGENCE_KEY not found. Attempting Managed Identity..."
        )
        credential = DefaultAzureCredential()

    client = DocumentIntelligenceClient(endpoint=endpoint, credential=credential)

    with open(pdf_path, "rb") as f:
        poller = client.begin_analyze_document(
            "prebuilt-layout", analyze_request=f, content_type="application/pdf"
        )

    result: AnalyzeResult = poller.result()

    # Concatenate all content
    # We might want to be smarter about this (e.g. keeping structure),
    # but for now, raw content is what we aligned against.
    # Result.content is usually the full text.
    if result.content:
        return result.content

    return ""
