from fastapi import APIRouter, Depends, HTTPException
from repositories.research import User, Paper
from repositories import ResearchRepository, get_research_repository
from routers.auth import get_current_user
from utils.groq_client import client, model_config
from pydantic import BaseModel
import re
import time
from typing import Iterable, List, Optional, Tuple
from services.analytics_service import log_ai_usage
from services.rag_runtime import get_rag_runtime

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    message: str
    workspace_id: int
    selected_paper_ids: Optional[List[int]] = None
    include_recent_chats: bool = True


from utils.text_utils import STOP_WORDS as _STOP_WORDS, tokenize as _tokenize


def _paper_score(paper: Paper, query_tokens: Iterable[str]) -> int:
    query_set = set(query_tokens)
    if not query_set:
        return 0
    title_tokens = set(_tokenize(getattr(paper, "title", "") or ""))
    abstract_tokens = set(_tokenize(getattr(paper, "abstract", "") or ""))
    title_hits = len(query_set.intersection(title_tokens))
    abstract_hits = len(query_set.intersection(abstract_tokens))
    return (title_hits * 4) + (abstract_hits * 2)


def build_context(
    papers: List[Paper], query: str, max_papers: int = 12, max_chars: int = 18000
) -> str:
    """Build grounded context with ranked papers and stable citation ids [P#]."""
    if not papers:
        return "No papers available in this workspace."

    q_tokens = _tokenize(query)
    ranked: List[Tuple[int, Paper]] = [
        (_paper_score(paper, q_tokens), paper) for paper in papers
    ]
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
    repo: ResearchRepository,
    workspace_id: int,
    limit: int = 4,
    max_chars: int = 3600,
) -> Tuple[str, int]:
    rows = repo.list_chats_for_workspace(
        workspace_id,
        ascending=False,
        limit=max(0, limit),
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
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: User = Depends(get_current_user),
):
    if not client:
        raise HTTPException(
            status_code=503, detail="AI service not configured. Set GROQ_API_KEY."
        )

    question = (chat_msg.message or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    workspace = repo.find_workspace_for_user(chat_msg.workspace_id, current_user.id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    clean_ids = None
    if chat_msg.selected_paper_ids:
        clean_ids = sorted(
            {
                paper_id
                for paper_id in chat_msg.selected_paper_ids
                if isinstance(paper_id, int) and paper_id > 0
            }
        )
    workspace_papers = repo.list_papers_for_workspace(chat_msg.workspace_id, clean_ids)
    if not workspace_papers:
        raise HTTPException(
            status_code=400,
            detail="No papers available for chat context. Import papers or adjust selected papers.",
        )
    context = build_context(workspace_papers, question)
    conversation_context, recent_chat_turns = (
        _recent_chat_context(repo, chat_msg.workspace_id)
        if chat_msg.include_recent_chats
        else ("", 0)
    )
    rag_context = ""
    try:
        runtime = get_rag_runtime(db=getattr(repo, "db", None))
        rag_context = await runtime.retrieval_service.retrieve_and_format(
            query=question,
            workspace_id=chat_msg.workspace_id,
            top_k=5,
            source_types=["paper", "summary", "checker", "report"],
            max_context_tokens=900,
        )
        if rag_context.strip().lower().startswith("no relevant workspace context"):
            rag_context = ""
    except Exception:
        rag_context = ""

    system_prompt = (
        "You are Soyog AI Copilot, a rigorous research analyst.\n"
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
        f"Retrieved workspace RAG context:\n{rag_context or 'No additional retrieved context.'}\n\n"
        "Constraints:\n"
        "- Prefer concise bullet points where possible.\n"
        "- Include at least 2 citations when evidence exists.\n"
        "- Do not invent paper details."
    )

    try:
        _t0 = time.monotonic()
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            **model_config(
                task="chat", longform=False, max_tokens=2400, temperature=0.18
            ),
        )
        ai_response = (response.choices[0].message.content or "").strip()
        _duration_ms = max(0, int((time.monotonic() - _t0) * 1000))
        _model_used = str(getattr(response, "model", "") or "")
        log_ai_usage(
            repo.db,
            user_id=str(current_user.id),
            route="chat",
            input_size=len(user_prompt),
            output_size=len(ai_response),
            duration_ms=_duration_ms,
            status="success",
            model=_model_used,
            cache_hit=False,
        )
    except Exception as exc:
        log_ai_usage(
            repo.db,
            user_id=str(current_user.id),
            route="chat",
            input_size=len(user_prompt),
            output_size=0,
            duration_ms=0,
            status="error",
            model="",
            cache_hit=False,
        )
        raise HTTPException(status_code=502, detail=f"AI analysis failed: {str(exc)}")

    repo.create_chat(chat_msg.workspace_id, question, ai_response)

    return {
        "response": ai_response,
        "papers_used": len(workspace_papers),
        "recent_chat_turns_used": recent_chat_turns,
        "rag_context_used": bool(rag_context),
    }
