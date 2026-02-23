from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
import io
import re
import textwrap
from collections import Counter
from datetime import datetime, timezone

from utils.groq_client import client as groq_client, model_config

from database import get_db
from models import User, Workspace, Paper, Chat
from routers.auth import get_current_user

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class WorkspaceCreate(BaseModel):
    name: str
    description: Optional[str] = None


class WorkspaceOut(BaseModel):
    id: int
    name: str
    description: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class PaperOut(BaseModel):
    id: int
    title: str
    authors: str
    abstract: str
    url: Optional[str] = None
    doi: Optional[str] = None
    bibcode: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ChatOut(BaseModel):
    id: int
    message: str
    response: str

    model_config = ConfigDict(from_attributes=True)


class WorkspaceDetail(BaseModel):
    id: int
    name: str
    description: Optional[str]
    papers: List[PaperOut]
    chats: List[ChatOut]

    model_config = ConfigDict(from_attributes=True)


class ResearchReportRequest(BaseModel):
    topic: Optional[str] = None
    paper_ids: Optional[List[int]] = None


def _safe_filename(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", (text or "").strip().lower()).strip("-")
    return slug or "research-report"


def _extract_keywords(text: str, top_n: int = 12) -> List[str]:
    stop_words = {
        "with", "from", "that", "this", "these", "those", "their", "there", "about",
        "into", "using", "based", "study", "paper", "analysis", "results", "method",
        "methods", "data", "approach", "approaches", "system", "systems", "model",
        "models", "research", "through", "between", "across", "where", "while",
        "under", "over", "after", "before", "because", "which", "would", "could",
        "should", "have", "has", "been", "being", "were", "such", "than", "into",
        "more", "most", "less", "many", "also", "both", "each", "within", "without",
    }
    words = re.findall(r"[A-Za-z]{4,}", (text or "").lower())
    filtered = [word for word in words if word not in stop_words]
    counts = Counter(filtered)
    return [word for word, _ in counts.most_common(top_n)]


_STOP_WORDS = {
    "with", "from", "that", "this", "these", "those", "their", "there", "about",
    "into", "using", "based", "study", "paper", "analysis", "results", "method",
    "methods", "data", "approach", "approaches", "system", "systems", "model",
    "models", "research", "through", "between", "across", "where", "while",
    "under", "over", "after", "before", "because", "which", "would", "could",
    "should", "have", "has", "been", "being", "were", "such", "than", "into",
    "more", "most", "less", "many", "also", "both", "each", "within", "without",
}


def _tokenize_for_rank(text: str) -> List[str]:
    tokens = re.findall(r"[a-zA-Z0-9]{3,}", (text or "").lower())
    return [token for token in tokens if token not in _STOP_WORDS]


def _paper_relevance_score(topic: str, paper: Paper) -> int:
    query_set = set(_tokenize_for_rank(topic))
    if not query_set:
        return 0
    title_set = set(_tokenize_for_rank(paper.title or ""))
    abstract_set = set(_tokenize_for_rank(paper.abstract or ""))
    title_hits = len(query_set.intersection(title_set))
    abstract_hits = len(query_set.intersection(abstract_set))
    return (title_hits * 4) + (abstract_hits * 2)


def _build_context(topic: str, papers: List[Paper]) -> str:
    ranked = sorted(
        papers,
        key=lambda paper: (
            _paper_relevance_score(topic, paper),
            len((paper.abstract or "")),
            len((paper.title or "")),
        ),
        reverse=True,
    )
    selected = ranked[:40]
    lines = [f"Topic: {topic}", "", "Workspace papers (citation id [P#]):"]
    for idx, paper in enumerate(selected, start=1):
        abstract = (paper.abstract or "").replace("\n", " ").strip()
        if len(abstract) > 1200:
            abstract = abstract[:1200] + "..."
        doi = getattr(paper, "doi", "") or "N/A"
        url = (paper.url or "").strip() or "N/A"
        lines.append(
            (
                f"[P{idx}] Title: {paper.title}\n"
                f"Authors: {paper.authors}\n"
                f"DOI: {doi}\n"
                f"URL: {url}\n"
                f"Abstract: {abstract or 'No abstract available.'}\n"
            )
        )
    return "\n".join(lines)[:36000]


def _fallback_report_markdown(topic: str, papers: List[Paper]) -> str:
    combined_text = " ".join(
        [paper.title or "" for paper in papers] + [paper.abstract or "" for paper in papers]
    )
    keywords = _extract_keywords(combined_text, top_n=10)
    representative_titles = [paper.title for paper in papers[:8] if paper.title]
    evidence_rows = []
    for idx, paper in enumerate(papers[:6], start=1):
        key_claim = ((paper.abstract or "").split(".")[0] or "").strip()
        if not key_claim:
            key_claim = "No abstract sentence available."
        evidence_rows.append(f"| P{idx} | {paper.title} | {key_claim[:120]} |")
    evidence_table = "\n".join(
        ["| Paper | Title | Key claim snippet |", "| --- | --- | --- |", *evidence_rows]
    ) if evidence_rows else "| Paper | Title | Key claim snippet |\n| --- | --- | --- |\n| - | - | - |"

    gaps = [
        "Insufficient cross-benchmark comparability across studies.",
        "Limited reproducibility details for data preprocessing and hyperparameters.",
        "Sparse reporting on negative results and failure modes.",
        "Few studies evaluate long-term deployment constraints and robustness.",
    ]

    keyword_bullets = "\n".join([f"- {word.title()}" for word in keywords[:8]]) or "- Topic not inferable from provided papers."
    title_bullets = "\n".join([f"- {title}" for title in representative_titles]) or "- No representative titles available."
    gap_bullets = "\n".join([f"- {gap}" for gap in gaps])

    return f"""# Research Brief: {topic}

## Executive Summary
This report summarizes {len(papers)} papers currently stored in your workspace. It captures common themes, core methods, comparative insights, and open research opportunities.

## Core Concepts
{keyword_bullets}

## Methodological Landscape
- Dominant methods rely on data-driven modeling and empirical evaluation.
- Most papers compare against prior baselines but vary in benchmark rigor.
- Evaluation metrics are often domain-specific, which reduces direct comparability.

## Comparative Findings
- Recurrent trends indicate performance gains from improved feature engineering and stronger model priors.
- Papers diverge on dataset construction assumptions and validation strategies.
- Transferability across domains remains uneven.

## Gaps and Risks
{gap_bullets}

## Future Directions
- Standardize evaluation protocols and report uncertainty with confidence intervals.
- Increase ablation depth and publish reproducible training and inference recipes.
- Validate claims on diverse and out-of-distribution settings.

## Key Papers
{title_bullets}

## Evidence Matrix
{evidence_table}

## Action Plan
- Reproduce the top two cited approaches with a single standardized benchmark suite.
- Run ablations for data preprocessing, model scaling, and objective variants.
- Track failure modes explicitly and publish robustness diagnostics.

## Mindmap
- {topic}
  - Core Concepts
    - {keywords[0].title() if len(keywords) > 0 else "Foundational Concepts"}
    - {keywords[1].title() if len(keywords) > 1 else "Primary Methods"}
    - {keywords[2].title() if len(keywords) > 2 else "Evaluation Focus"}
  - Methods
    - Baseline comparisons
    - Optimization and tuning
    - Validation strategies
  - Evidence
    - Representative papers
    - Quantitative outcomes
    - Reported limitations
  - Gaps
    - Reproducibility
    - Generalization risk
    - Long-term deployment
  - Next Steps
    - Better benchmarks
    - Robustness stress tests
    - Cross-domain replication
"""


def _generate_report_markdown(topic: str, papers: List[Paper]) -> str:
    context = _build_context(topic=topic, papers=papers)
    if not groq_client:
        return _fallback_report_markdown(topic=topic, papers=papers)

    prompt = (
        "Generate a rigorous, publication-grade literature analysis with a practical mindmap.\n"
        "Strict output format in markdown only.\n\n"
        "Required sections in exact order:\n"
        "# Research Brief: <topic>\n"
        "## Executive Summary\n"
        "## Core Concepts\n"
        "## Methodological Landscape\n"
        "## Comparative Findings\n"
        "## Gaps and Risks\n"
        "## Future Directions\n"
        "## Key Papers\n"
        "## Evidence Matrix\n"
        "## Action Plan\n"
        "## Mindmap\n\n"
        "Rules:\n"
        "- Keep it concise but technically deep.\n"
        "- Use bullet points for all sections except Executive Summary.\n"
        "- Every non-trivial claim must cite one or more paper ids like [P3] from context.\n"
        "- In Evidence Matrix, build a markdown table with columns: Claim | Supporting Papers | Confidence.\n"
        "- Confidence must be one of High/Medium/Low.\n"
        "- Mindmap must be a hierarchical bullet tree with indentation depth up to 3 levels.\n"
        "- Base all claims on provided paper context and avoid hallucinations.\n"
        "- If evidence is weak, explicitly state 'Insufficient evidence in workspace.'\n\n"
        f"Context:\n{context}"
    )

    try:
        response = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior research scientist and technical reviewer. "
                        "Your output must be concrete, evidence-grounded, and decision-oriented."
                    ),
                },
                {"role": "user", "content": prompt[:26000]},
            ],
            **model_config(longform=True, max_tokens=3800, temperature=0.15),
        )
        text = (response.choices[0].message.content or "").strip()
        if not text:
            return _fallback_report_markdown(topic=topic, papers=papers)
        if not text.startswith("# Research Brief:"):
            text = f"# Research Brief: {topic}\n\n{text}"
        return text[:32000]
    except Exception:
        return _fallback_report_markdown(topic=topic, papers=papers)


def _build_docx_bytes(markdown_text: str) -> bytes:
    try:
        from docx import Document
        from docx.shared import Pt
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="DOCX export dependency missing. Install python-docx.",
        ) from exc

    document = Document()
    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        if not line:
            document.add_paragraph("")
            continue
        if line.startswith("# "):
            document.add_heading(line[2:].strip(), level=1)
            continue
        if line.startswith("## "):
            document.add_heading(line[3:].strip(), level=2)
            continue
        if line.startswith("### "):
            document.add_heading(line[4:].strip(), level=3)
            continue

        stripped = line.lstrip(" ")
        if stripped.startswith("- "):
            indent_spaces = len(line) - len(stripped)
            paragraph = document.add_paragraph(stripped[2:].strip(), style="List Bullet")
            if indent_spaces > 0:
                paragraph.paragraph_format.left_indent = Pt(min(indent_spaces * 4, 72))
            continue

        document.add_paragraph(line)

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _build_pdf_bytes(markdown_text: str) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="PDF export dependency missing. Install reportlab.",
        ) from exc

    page_width, page_height = A4
    margin_x = 40
    top_y = page_height - 42
    bottom_y = 42
    line_height = 14
    max_chars = 110

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    y = top_y

    def _draw_line(text: str, font: str = "Helvetica", size: int = 11) -> None:
        nonlocal y
        if y <= bottom_y:
            pdf.showPage()
            y = top_y
        pdf.setFont(font, size)
        pdf.drawString(margin_x, y, text)
        y -= line_height

    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        if not line:
            _draw_line("", font="Helvetica", size=11)
            continue

        font = "Helvetica"
        size = 11
        text = line

        if line.startswith("# "):
            font = "Helvetica-Bold"
            size = 15
            text = line[2:].strip()
        elif line.startswith("## "):
            font = "Helvetica-Bold"
            size = 13
            text = line[3:].strip()
        elif line.startswith("### "):
            font = "Helvetica-Bold"
            size = 12
            text = line[4:].strip()

        wrapped_lines = textwrap.wrap(text, width=max_chars) or [""]
        for wrapped in wrapped_lines:
            _draw_line(wrapped, font=font, size=size)

        if line.startswith("#"):
            y -= 3

    pdf.save()
    return buffer.getvalue()


@router.get("/", response_model=List[WorkspaceOut])
def list_workspaces(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspaces = (
        db.query(Workspace)
        .filter(Workspace.user_id == current_user.id)
        .order_by(Workspace.created_at.desc())
        .all()
    )
    return workspaces


@router.post("/", response_model=WorkspaceOut)
def create_workspace(
    payload: WorkspaceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace = Workspace(
        name=payload.name,
        description=payload.description,
        user_id=current_user.id,
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


@router.get("/{workspace_id}", response_model=WorkspaceDetail)
def get_workspace(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace = (
        db.query(Workspace)
        .filter(Workspace.id == workspace_id, Workspace.user_id == current_user.id)
        .first()
    )
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    papers = db.query(Paper).filter(Paper.workspace_id == workspace.id).all()
    chats = (
        db.query(Chat)
        .filter(Chat.workspace_id == workspace.id)
        .order_by(Chat.timestamp.asc())
        .all()
    )

    return WorkspaceDetail(
        id=workspace.id,
        name=workspace.name,
        description=workspace.description,
        papers=papers,
        chats=chats,
    )


@router.post("/default", response_model=WorkspaceOut)
def get_or_create_default_workspace(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace = (
        db.query(Workspace)
        .filter(Workspace.user_id == current_user.id, Workspace.name == "Default Workspace")
        .first()
    )
    if workspace:
        return workspace

    workspace = Workspace(
        name="Default Workspace",
        description="Automatically created workspace for quick imports.",
        user_id=current_user.id,
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


@router.delete("/{workspace_id}")
def delete_workspace(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace = (
        db.query(Workspace)
        .filter(Workspace.id == workspace_id, Workspace.user_id == current_user.id)
        .first()
    )
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Cascade delete papers and chats
    db.query(Paper).filter(Paper.workspace_id == workspace_id).delete()
    db.query(Chat).filter(Chat.workspace_id == workspace_id).delete()
    db.delete(workspace)
    db.commit()
    return {"message": "Workspace deleted successfully"}


@router.get("/{workspace_id}/export")
def export_workspace(
    workspace_id: int,
    format: str = "bibtex",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export papers in a workspace as BibTeX or CSV."""
    workspace = (
        db.query(Workspace)
        .filter(Workspace.id == workspace_id, Workspace.user_id == current_user.id)
        .first()
    )
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    papers = db.query(Paper).filter(Paper.workspace_id == workspace.id).all()

    if format not in ("bibtex", "csv"):
        raise HTTPException(status_code=400, detail="Unsupported export format. Use 'bibtex' or 'csv'.")

    # CSV export
    if format == "csv":
        import csv, io, re
        def _sanitize_cell(v: str) -> str:
            s = (v or "")
            # Neutralize CSV injection vectors for Excel: prefix if starts with =, +, -, @
            if s.startswith(('=', '+', '-', '@')):
                s = "'" + s
            # Remove control chars that break CSVs
            s = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", " ", s)
            return s
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["title", "authors", "abstract", "url", "doi", "bibcode"])
        for p in papers:
            row = [
                _sanitize_cell(p.title or ""),
                _sanitize_cell(p.authors or ""),
                _sanitize_cell(p.abstract or ""),
                _sanitize_cell(p.url or ""),
                _sanitize_cell(getattr(p, 'doi', '') or ""),
                _sanitize_cell(getattr(p, 'bibcode', '') or ""),
            ]
            writer.writerow(row)
        content = buf.getvalue()
        return Response(content=content, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=workspace-{workspace.id}.csv"})

    # BibTeX export
    def _escape(s: str) -> str:
        return (s or "").replace("\n", " ").replace("{", "").replace("}", "").strip()

    entries = []
    for p in papers:
        key = f"paper{p.id}"
        authors = _escape(p.authors)
        title = _escape(p.title)
        year = ""
        url = _escape(p.url)
        doi = _escape(getattr(p, 'doi', '') or "")
        abstract = _escape(p.abstract)
        bib_fields = []
        if doi:
            bib_fields.append(f"  doi = {{{doi}}},")
        if url:
            bib_fields.append(f"  url = {{{url}}},")
        bib_fields_str = "\n".join(bib_fields)
        entry = f"@misc{{{key},\n  title = {{{title}}},\n  author = {{{authors}}},{('\n' + bib_fields_str) if bib_fields_str else ''}\n  year = {{{year}}},\n  abstract = {{{abstract}}}\n}}\n"
        entries.append(entry)
    content = "\n".join(entries)
    return Response(content=content, media_type="application/x-bibtex", headers={"Content-Disposition": f"attachment; filename=workspace-{workspace.id}.bib"})


@router.post("/{workspace_id}/research-report")
def export_research_report(
    workspace_id: int,
    format: str = "pdf",
    payload: Optional[ResearchReportRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate a structured research brief + mindmap from workspace papers.
    Export options: PDF or DOCX.
    """
    workspace = (
        db.query(Workspace)
        .filter(Workspace.id == workspace_id, Workspace.user_id == current_user.id)
        .first()
    )
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if format not in ("pdf", "docx"):
        raise HTTPException(status_code=400, detail="Unsupported export format. Use 'pdf' or 'docx'.")

    requested_ids = set(payload.paper_ids or []) if payload else set()
    query = db.query(Paper).filter(Paper.workspace_id == workspace.id)
    if requested_ids:
        query = query.filter(Paper.id.in_(requested_ids))
    papers = query.all()

    if not papers:
        raise HTTPException(status_code=400, detail="No papers available for report generation.")

    topic = (payload.topic or workspace.name or "Research topic").strip() if payload else (workspace.name or "Research topic")
    topic = topic[:160]
    report_markdown = _generate_report_markdown(topic=topic, papers=papers)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    safe_topic = _safe_filename(topic)

    if format == "docx":
        content = _build_docx_bytes(report_markdown)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = f"{safe_topic}-mindmap-{timestamp}.docx"
    else:
        content = _build_pdf_bytes(report_markdown)
        media_type = "application/pdf"
        filename = f"{safe_topic}-mindmap-{timestamp}.pdf"

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type=media_type, headers=headers)
