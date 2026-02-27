from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import User, Workspace, Paper, Chat
from routers.auth import get_current_user
from utils.groq_client import client, model_config
from pydantic import BaseModel
import re
from typing import Iterable, List, Optional, Tuple

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    message: str
    workspace_id: int
    selected_paper_ids: Optional[List[int]] = None
    include_recent_chats: bool = True


_STOP_WORDS = {
    "the", "and", "for", "with", "from", "that", "this", "into", "using", "your",
    "about", "have", "has", "are", "was", "were", "how", "what", "when", "where",
    "which", "will", "would", "could", "should", "can", "also", "than", "then",
    "their", "there", "these", "those", "over", "under", "between", "across",
}


def _tokenize(text: str) -> List[str]:
    tokens = re.findall(r"[a-zA-Z0-9]{3,}", (text or "").lower())
    return [tok for tok in tokens if tok not in _STOP_WORDS]


def _paper_score(paper: Paper, query_tokens: Iterable[str]) -> int:
    query_set = set(query_tokens)
    if not query_set:
        return 0
    title_tokens = set(_tokenize(getattr(paper, "title", "") or ""))
    abstract_tokens = set(_tokenize(getattr(paper, "abstract", "") or ""))
    title_hits = len(query_set.intersection(title_tokens))
    abstract_hits = len(query_set.intersection(abstract_tokens))
    return (title_hits * 4) + (abstract_hits * 2)


def build_context(papers: List[Paper], query: str, max_papers: int = 12, max_chars: int = 18000) -> str:
    """Build grounded context with ranked papers and stable citation ids [P#]."""
    if not papers:
        return "No papers available in this workspace."

    q_tokens = _tokenize(query)
    ranked: List[Tuple[int, Paper]] = [(_paper_score(paper, q_tokens), paper) for paper in papers]
    ranked.sort(
        key=lambda pair: (
            pair[0],
            len((getattr(pair[1], "abstract", "") or "")),
            len((getattr(pair[1], "title", "") or "")),
        ),
        reverse=True,
    )

    selected = [paper for _, paper in ranked[:max_papers]]
    lines: List[str] = []
    for idx, paper in enumerate(selected, start=1):
        abstract = (paper.abstract or "").replace("\n", " ").strip()
        if len(abstract) > 1200:
            abstract = abstract[:1200] + "..."
        doi = (getattr(paper, "doi", "") or "").strip()
        url = (getattr(paper, "url", "") or "").strip()
        lines.append(
            (
                f"[P{idx}] Title: {paper.title}\n"
                f"Authors: {paper.authors}\n"
                f"DOI: {doi or 'N/A'}\n"
                f"URL: {url or 'N/A'}\n"
                f"Abstract: {abstract or 'No abstract available.'}\n"
            )
        )

    joined = "\n---\n".join(lines)
    return joined[:max_chars]


def _recent_chat_context(
    db: Session,
    workspace_id: int,
    limit: int = 4,
    max_chars: int = 3600,
) -> Tuple[str, int]:
    rows = (
        db.query(Chat)
        .filter(Chat.workspace_id == workspace_id)
        .order_by(Chat.timestamp.desc())
        .limit(max(0, limit))
        .all()
    )
    if not rows:
        return "", 0
    lines: List[str] = []
    for idx, row in enumerate(reversed(rows), start=1):
        user_msg = (row.message or "").strip().replace("\n", " ")
        ai_msg = (row.response or "").strip().replace("\n", " ")
        if len(ai_msg) > 600:
            ai_msg = ai_msg[:600] + "..."
        lines.append(f"[Chat {idx}] User: {user_msg}\n[Chat {idx}] Assistant: {ai_msg}")
    return "\n\n".join(lines)[:max_chars], len(rows)


@router.post("/")
async def chat_with_papers(
    chat_msg: ChatMessage,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not client:
        raise HTTPException(status_code=503, detail="AI service not configured. Set GROQ_API_KEY.")

    question = (chat_msg.message or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    workspace = (
        db.query(Workspace)
        .filter(Workspace.id == chat_msg.workspace_id, Workspace.user_id == current_user.id)
        .first()
    )
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    paper_query = db.query(Paper).filter(Paper.workspace_id == chat_msg.workspace_id)
    if chat_msg.selected_paper_ids:
        clean_ids = sorted({paper_id for paper_id in chat_msg.selected_paper_ids if isinstance(paper_id, int) and paper_id > 0})
        if clean_ids:
            paper_query = paper_query.filter(Paper.id.in_(clean_ids))
    workspace_papers = paper_query.all()
    if not workspace_papers:
        raise HTTPException(
            status_code=400,
            detail="No papers available for chat context. Import papers or adjust selected papers.",
        )
    context = build_context(workspace_papers, question)
    conversation_context, recent_chat_turns = (
        _recent_chat_context(db, chat_msg.workspace_id) if chat_msg.include_recent_chats else ("", 0)
    )

    system_prompt = (
        "You are ResearchHub Copilot, a rigorous research analyst.\n"
        "Answer with technical precision and avoid generic language.\n"
        "Ground all non-trivial claims in provided papers and cite with [P#].\n"
        "If evidence is missing, explicitly state: 'Insufficient evidence in workspace.'\n"
        "Output format:\n"
        "### Direct Answer\n"
        "### Evidence From Workspace\n"
        "### Gaps and Risks\n"
        "### Next Best Actions\n"
    )

    user_prompt = (
        f"User question:\n{question}\n\n"
        f"Recent chat context (if available):\n{conversation_context or 'No prior chat context.'}\n\n"
        f"Workspace paper context:\n{context}\n\n"
        "Constraints:\n"
        "- Prefer concise bullet points where possible.\n"
        "- Include at least 2 citations when evidence exists.\n"
        "- Do not invent paper details."
    )

    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            **model_config(longform=False, max_tokens=2400, temperature=0.18),
        )
        ai_response = (response.choices[0].message.content or "").strip()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI analysis failed: {str(exc)}")

    new_chat = Chat(
        message=question,
        response=ai_response,
        workspace_id=chat_msg.workspace_id,
    )
    db.add(new_chat)
    db.commit()

    return {
        "response": ai_response,
        "papers_used": len(workspace_papers),
        "recent_chat_turns_used": recent_chat_turns,
    }
