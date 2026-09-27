from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Response
from typing import Optional
import os
import re
import logging
import socket
import time

from repositories.research import User
from repositories import ResearchRepository, get_research_repository
from routers.auth import get_current_user
from services.pdf_text_service import clean_extracted_text, extract_text_from_pdf_bytes
from services.rag_hooks import index_paper_best_effort
from utils.groq_client import client, model_config
from utils.firebase_storage import download_bytes, storage_is_configured, upload_bytes

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/papers", tags=["upload"])


def _safe_filename(name: str, fallback: str = "upload.pdf") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", (name or "").strip()).strip("-")
    return cleaned or fallback


def _backend_base_url() -> str:
    return (os.getenv("BACKEND_URL") or "http://127.0.0.1:8010").rstrip("/")


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
            **model_config(
                task="upload_summary", longform=False, max_tokens=2200, temperature=0.12
            ),
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

    # Validate MIME type before reading the full payload.
    allowed_content_types = {
        "application/pdf",
        "application/x-pdf",
        "binary/octet-stream",
    }
    if file.content_type and file.content_type not in allowed_content_types:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{file.content_type}'. Only PDF files are accepted.",
        )

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    MAX_PDF_BYTES = 20 * 1024 * 1024  # 20 MB
    if len(file_bytes) > MAX_PDF_BYTES:
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum allowed size is 20 MB.",
        )

    # Verify PDF magic bytes (%PDF-) regardless of declared MIME type.
    if not file_bytes.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=415,
            detail="Uploaded file does not appear to be a valid PDF.",
        )

    # Extract text
    try:
        extracted_text = clean_extracted_text(extract_text_from_pdf_bytes(file_bytes))
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
        title = (
            file.filename.replace(".pdf", "")
            .replace("_", " ")
            .replace("-", " ")
            .title()
        )
        new_paper = repo.create_paper(
            workspace_id=workspace.id,
            title=title,
            authors="Uploaded PDF",
            abstract=ai_summary or extracted_text[:500],
            url=None,
        )
        paper_id = new_paper.id
        
        # Try storage upload only if emulator is actually reachable
        storage_upload_attempted = False
        if storage_is_configured():
            # Quick check if storage emulator is actually reachable
            try:
                storage_host = os.getenv("STORAGE_EMULATOR_HOST", "").replace("http://", "").replace("https://", "")
                if storage_host:
                    host, port = storage_host.split(":") if ":" in storage_host else (storage_host, "9199")
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1)
                    result = sock.connect_ex((host, int(port)))
                    sock.close()
                    if result != 0:
                        logger.warning(f"UPLOAD_STORAGE_EMULATOR_NOT_REACHABLE: {storage_host} - skipping storage")
                        storage_upload_attempted = False
                    else:
                        storage_upload_attempted = True
            except Exception as check_error:
                logger.warning(f"UPLOAD_STORAGE_CHECK_FAILED: {str(check_error)} - skipping storage")
                storage_upload_attempted = False
        
        if storage_upload_attempted:
            safe_name = _safe_filename(file.filename, fallback=f"paper-{paper_id}.pdf")
            storage_path = (
                f"workspace-files/{current_user.id}/{workspace.id}/uploads/"
                f"{paper_id}-{safe_name}"
            )
            try:
                uploaded = upload_bytes(
                    storage_path=storage_path,
                    data=file_bytes,
                    content_type=file.content_type or "application/pdf",
                    metadata={
                        "workspace_id": str(workspace.id),
                        "paper_id": str(paper_id),
                        "kind": "uploaded_pdf",
                    },
                )
                
                pdf_url = f"{_backend_base_url()}/papers/uploaded/{paper_id}/download"
                new_paper.pdf_url = pdf_url
                repo.save(new_paper)
                
                file_record = repo.create_workspace_file(
                    workspace_id=workspace.id,
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
            except Exception as storage_error:
                logger.warning(f"UPLOAD_STORAGE_FAILED: {str(storage_error)} - continuing without storage")
        else:
            logger.info("UPLOAD_STORAGE_SKIPPED: emulator not reachable")
        
        try:
            index_paper_best_effort(repo=repo, paper=new_paper)
        except Exception as indexing_error:
            logger.warning(f"UPLOAD_INDEXING_FAILED: {str(indexing_error)} - continuing without indexing")

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

    file_record = repo.get_workspace_file_for_paper(
        paper_id, paper.workspace_id, current_user.id
    )
    if not file_record:
        raise HTTPException(status_code=404, detail="Uploaded file metadata not found.")

    try:
        downloaded = download_bytes(storage_path=file_record.storage_path)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Failed to download file from storage: {str(exc)}"
        )

    headers = {"Content-Disposition": f'inline; filename="{file_record.filename}"'}
    return Response(
        content=downloaded.data, media_type=downloaded.content_type, headers=headers
    )
