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

def create_research_context(papers, query):
    context_parts = []
    for paper in papers:
        paper_context = f'''
Title: {paper.title}
Authors: {paper.authors}
Abstract: {paper.abstract}
'''
        context_parts.append(paper_context)
    
    full_context = "\n---\n".join(context_parts)
    # Truncate context if too large (naive approach for now)
    return f"Research Papers Context:\n{full_context[:10000]}\n\nUser Query: {query}"

@router.post("/")
async def chat_with_papers(chat_msg: ChatMessage, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    workspace = db.query(Workspace).filter(Workspace.id == chat_msg.workspace_id, Workspace.user_id == current_user.id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    workspace_papers = db.query(Paper).filter(Paper.workspace_id == chat_msg.workspace_id).all()
    
    context = create_research_context(workspace_papers, chat_msg.message)
    
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": f"You are an expert research assistant. Context: {context}"},
                {"role": "user", "content": chat_msg.message}
            ],
            **MODEL_CONFIG
        )
        ai_response = response.choices[0].message.content
    except Exception as e:
        print(f"Groq API Error: {e}")
        ai_response = "I'm sorry, I encountered an error communicating with the AI service. Please ensure the API key is set."

    # Store chat history
    new_chat = Chat(
        message=chat_msg.message,
        response=ai_response,
        workspace_id=chat_msg.workspace_id
    )
    db.add(new_chat)
    db.commit()

    return {"response": ai_response}
