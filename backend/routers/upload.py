from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Response
from typing import Optional
import pdfplumber
import io
import os
import re

from models import User
from repositories import ResearchRepository, get_research_repository
from routers.auth import get_current_user
from utils.groq_client import client, model_config
from utils.firebase_storage import download_bytes, storage_is_configured, upload_bytes

router = APIRouter(prefix="/papers", tags=["upload"])


def _safe_filename(name: str, fallback: str = "upload.pdf") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", (name or "").strip()).strip("-")
    return cleaned or fallback


def _backend_base_url() -> str:
    return (os.getenv("BACKEND_URL") or "http://127.0.0.1:8010").rstrip("/")


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract plain text from PDF bytes using pdfplumber."""
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
    return "\n".join(text_parts)


def summarize_with_ai(text: str) -> str:
    """Use Groq/LLaMA to produce a structured research summary."""
    if not client:
        return "AI summary unavailable: GROQ_API_KEY not configured."

    # Trim text to avoid exceeding context limits while preserving detail.
    trimmed = (text or "").strip()[:18000]
    if not trimmed:
        return "AI summary unavailable: extracted text is empty."

    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert scientific paper analyst.\n"
                "Produce high-signal technical synthesis grounded in the provided paper text.\n"
                "Output in markdown with EXACT sections:\n"
                "## Paper Snapshot\n"
                "## Key Contributions\n"
                "## Methodology and Experimental Setup\n"
                "## Main Results and Evidence\n"
                "## Limitations and Threats to Validity\n"
                "## Reproducibility Checklist\n"
                "## Practical Next Steps\n"
                "Use concise bullets and avoid vague statements."
            ),
        },
        {
            "role": "user",
            "content": (
                "Analyze this paper text and produce the structured summary.\n\n"
                f"{trimmed}"
            ),
        },
    ]

    try:
        response = client.chat.completions.create(
            messages=messages,
            **model_config(task="upload_summary", longform=False, max_tokens=2200, temperature=0.12),
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI summary failed: {str(e)}"


@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    workspace_id: Optional[int] = Form(None),
    summarize: bool = Form(True),
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a PDF, extract its text, optionally generate an AI summary,
    and optionally save it as a Paper in the given workspace.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Extract text
    try:
        extracted_text = extract_text_from_pdf(file_bytes)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse PDF: {str(e)}")

    # AI summary
    ai_summary = ""
    if summarize:
        ai_summary = summarize_with_ai(extracted_text)

    # Optionally save to workspace
    paper_id = None
    pdf_url = None
    storage_path = None
    storage_bucket = None
    file_record_id = None
    if workspace_id is not None:
        workspace = repo.find_workspace_for_user(workspace_id, current_user.id)
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found.")

        # Use filename (without extension) as fallback title
        title = file.filename.replace(".pdf", "").replace("_", " ").replace("-", " ").title()
        new_paper = repo.create_paper(
            workspace_id=workspace_id,
            title=title,
            authors="Uploaded PDF",
            abstract=ai_summary or extracted_text[:500],
            url=None,
        )
        paper_id = new_paper.id
        if storage_is_configured():
            safe_name = _safe_filename(file.filename, fallback=f"paper-{paper_id}.pdf")
            storage_path = (
                f"workspace-files/{current_user.id}/{workspace_id}/uploads/"
                f"{paper_id}-{safe_name}"
            )
            uploaded = upload_bytes(
                storage_path=storage_path,
                data=file_bytes,
                content_type=file.content_type or "application/pdf",
                metadata={
                    "workspace_id": str(workspace_id),
                    "paper_id": str(paper_id),
                    "kind": "uploaded_pdf",
                },
            )
            pdf_url = f"{_backend_base_url()}/papers/uploaded/{paper_id}/download"
            new_paper.pdf_url = pdf_url
            repo.save(new_paper)
            file_record = repo.create_workspace_file(
                workspace_id=workspace_id,
                user_id=current_user.id,
                kind="uploaded_pdf",
                filename=safe_name,
                storage_bucket=uploaded.bucket,
                storage_path=uploaded.path,
                content_type=uploaded.content_type,
                size_bytes=uploaded.size_bytes,
                download_url=pdf_url,
                paper_id=paper_id,
            )
            file_record_id = file_record.id
            storage_bucket = uploaded.bucket

    return {
        "filename": file.filename,
        "extracted_text": extracted_text,
        "ai_summary": ai_summary,
        "paper_id": paper_id,
        "pdf_url": pdf_url,
        "storage_path": storage_path,
        "storage_bucket": storage_bucket,
        "file_record_id": file_record_id,
        "char_count": len(extracted_text),
    }


@router.get("/uploaded/{paper_id}/download")
async def download_uploaded_pdf(
    paper_id: int,
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: User = Depends(get_current_user),
):
    paper = repo.find_paper_for_user(paper_id, current_user.id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found.")

    file_record = repo.get_workspace_file_for_paper(paper_id, paper.workspace_id, current_user.id)
    if not file_record:
        raise HTTPException(status_code=404, detail="Uploaded file metadata not found.")

    try:
        downloaded = download_bytes(storage_path=file_record.storage_path)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to download file from storage: {str(exc)}")

    headers = {"Content-Disposition": f'inline; filename="{file_record.filename}"'}
    return Response(content=downloaded.data, media_type=downloaded.content_type, headers=headers)
