from fastapi import APIRouter
from utils.groq_client import client, MODEL_CONFIG

router = APIRouter(prefix="/ai", tags=["ai"])

@router.get("/status")
def ai_status():
    return {"enabled": client is not None, "model": MODEL_CONFIG.get("model") if client else None}
