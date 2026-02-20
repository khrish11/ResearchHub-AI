from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from routers.auth import get_current_user
from models import User
from utils.groq_client import client, MODEL_CONFIG

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/status")
def ai_status():
    return {"enabled": client is not None, "model": MODEL_CONFIG.get("model") if client else None}


class AnalyzeRequest(BaseModel):
    prompt: str


@router.post("/analyze")
async def analyze(req: AnalyzeRequest, current_user: User = Depends(get_current_user)):
    """
    Direct AI analysis endpoint — send a ready-made prompt and get a response.
    Used by AI Tools to avoid double-injecting workspace context.
    """
    if not client:
        raise HTTPException(status_code=503, detail="AI service is not configured. Set GROQ_API_KEY.")

    # Trim prompt to stay within token limits (~12k chars ≈ ~3k tokens)
    trimmed = req.prompt[:14000]

    try:
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert AI research assistant. "
                        "Respond clearly, accurately, and in well-structured markdown."
                    ),
                },
                {"role": "user", "content": trimmed},
            ],
            **MODEL_CONFIG,
        )
        return {"response": response.choices[0].message.content}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI API error: {str(e)}")
