from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import User, Workspace, Paper, Chat
from routers.auth import get_current_user
from utils.groq_client import client, model_config
from pydantic import BaseModel
import re
from typing import Iterable, List, Tuple

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    message: str
    workspace_id: int


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

    workspace_papers = db.query(Paper).filter(Paper.workspace_id == chat_msg.workspace_id).all()
    context = build_context(workspace_papers, question)

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

    return {"response": ai_response}

