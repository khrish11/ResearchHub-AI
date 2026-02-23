from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional
import pdfplumber
import io

from database import get_db
from models import User, Paper, Workspace
from routers.auth import get_current_user
from utils.groq_client import client, model_config

router = APIRouter(prefix="/papers", tags=["upload"])


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
            **model_config(longform=False, max_tokens=2200, temperature=0.12),
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI summary failed: {str(e)}"


@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    workspace_id: Optional[int] = Form(None),
    summarize: bool = Form(True),
    db: Session = Depends(get_db),
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
    if workspace_id is not None:
        workspace = (
            db.query(Workspace)
            .filter(Workspace.id == workspace_id, Workspace.user_id == current_user.id)
            .first()
        )
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found.")

        # Use filename (without extension) as fallback title
        title = file.filename.replace(".pdf", "").replace("_", " ").replace("-", " ").title()
        new_paper = Paper(
            title=title,
            authors="Uploaded PDF",
            abstract=ai_summary or extracted_text[:500],
            url=None,
            workspace_id=workspace_id,
        )
        db.add(new_paper)
        db.commit()
        db.refresh(new_paper)
        paper_id = new_paper.id

    return {
        "filename": file.filename,
        "extracted_text": extracted_text,
        "ai_summary": ai_summary,
        "paper_id": paper_id,
        "char_count": len(extracted_text),
    }
