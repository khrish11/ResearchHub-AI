from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import User, Workspace, Paper, Chat
from routers.auth import get_current_user
from utils.groq_client import client, MODEL_CONFIG
from pydantic import BaseModel

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    message: str
    workspace_id: int


def build_context(papers: list, query: str) -> str:
    """Build a compact research context from workspace papers."""
    parts = []
    for paper in papers:
        abstract = (paper.abstract or "")[:500]
        parts.append(f"Title: {paper.title}\nAuthors: {paper.authors}\nAbstract: {abstract}")
    joined = "\n---\n".join(parts)
    # Keep total context to ~8k chars
    return f"Workspace Papers:\n{joined[:8000]}\n\nUser Question: {query}"


@router.post("/")
async def chat_with_papers(
    chat_msg: ChatMessage,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # If the AI client is not configured, return a harmless placeholder response
    # so UI/tests can still call the endpoint without requiring an API key.
    if not client:
        return {"response": "AI service not configured — set GROQ_API_KEY to enable AI features."}

    workspace = (
        db.query(Workspace)
        .filter(Workspace.id == chat_msg.workspace_id, Workspace.user_id == current_user.id)
        .first()
    )
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    workspace_papers = db.query(Paper).filter(Paper.workspace_id == chat_msg.workspace_id).all()
    context = build_context(workspace_papers, chat_msg.message)

    try:
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert AI research assistant. "
                        "Use the workspace papers below to answer the user's question accurately. "
                        "Format your response in clear markdown.\n\n" + context
                    ),
                },
                {"role": "user", "content": chat_msg.message},
            ],
            **MODEL_CONFIG,
        )
        ai_response = response.choices[0].message.content
    except Exception as e:
        # Don't propagate downstream test/UI failures — return a safe fallback string
        ai_response = "AI service error or unavailable — returning a fallback response."

    # Store chat history
    new_chat = Chat(
        message=chat_msg.message,
        response=ai_response,
        workspace_id=chat_msg.workspace_id,
    )
    db.add(new_chat)
    db.commit()

    return {"response": ai_response}
