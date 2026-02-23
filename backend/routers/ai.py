from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Literal
from routers.auth import get_current_user
from models import User
from utils.groq_client import client, MODEL_CONFIG, model_config

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/status")
def ai_status():
    return {"enabled": client is not None, "model": MODEL_CONFIG.get("model") if client else None}


class AnalyzeRequest(BaseModel):
    prompt: str
    mode: Literal["general", "summaries", "insights", "review"] = "general"


ANALYZE_SYSTEM_PROMPTS = {
    "general": (
        "You are an expert research analyst. Deliver precise, technical, and evidence-aware answers. "
        "When source snippets are provided, cite them using [P1], [P2], etc."
    ),
    "summaries": (
        "You are writing expert-grade paper analyses. "
        "For each paper, cover problem framing, method details, dataset/benchmark setup, key quantitative findings, "
        "limitations, and practical implications. Avoid generic filler and keep evidence grounded in context."
    ),
    "insights": (
        "You are extracting cross-paper insights. "
        "Group findings into themes, include contradictions, and indicate confidence with reasoning. "
        "Cite evidence as [P#] where possible."
    ),
    "review": (
        "You are a senior literature-review writer. "
        "Produce a structured long-form synthesis with explicit gaps, limitations, and next experiments. "
        "Ground claims in provided context and cite evidence [P#]."
    ),
}

ANALYZE_OUTPUT_TARGETS = {
    "general": (
        "Output a direct answer first, then technical rationale, then actionable next steps. "
        "Use enough detail to be practically useful."
    ),
    "summaries": (
        "Target depth: for each paper include at least 6 concrete bullets and 180+ words when evidence exists. "
        "Include method, evaluation setup, strongest result, limitation, and transferability note."
    ),
    "insights": (
        "Target depth: 8-12 cross-paper insights plus contradictions, risk areas, and a prioritized action list. "
        "Include confidence (High/Medium/Low) for each major claim."
    ),
    "review": (
        "Target depth: substantial review draft (roughly 1200+ words when context supports it) with sections: "
        "Introduction, Taxonomy, Comparative Findings, Gaps, and Future Work."
    ),
}

ANALYZE_MAX_TOKENS = {
    "general": 3000,
    "summaries": 4200,
    "insights": 4600,
    "review": 5200,
}


@router.post("/analyze")
async def analyze(req: AnalyzeRequest, current_user: User = Depends(get_current_user)):
    """
    Direct AI analysis endpoint.
    Frontend can pass a fully prepared prompt; this endpoint adds robust analysis instructions.
    """
    if not client:
        raise HTTPException(status_code=503, detail="AI service is not configured. Set GROQ_API_KEY.")

    trimmed = (req.prompt or "").strip()[:36000]
    if not trimmed:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    mode = req.mode if req.mode in ANALYZE_SYSTEM_PROMPTS else "general"
    system_prompt = (
        f"{ANALYZE_SYSTEM_PROMPTS[mode]} "
        f"{ANALYZE_OUTPUT_TARGETS[mode]} "
        "When evidence is missing, explicitly say 'Insufficient evidence in provided papers.'"
    )

    try:
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {"role": "user", "content": trimmed},
            ],
            **model_config(
                longform=mode in {"summaries", "insights", "review"},
                max_tokens=ANALYZE_MAX_TOKENS.get(mode, MODEL_CONFIG.get("max_tokens", 3000)),
                temperature=0.18 if mode in {"summaries", "insights", "review"} else 0.2,
            ),
        )
        content = (response.choices[0].message.content or "").strip()

        # Recovery pass: expand thin answers for long-form analysis modes.
        if mode in {"summaries", "insights", "review"} and len(content) < 900:
            expand = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": trimmed},
                    {"role": "assistant", "content": content or "Draft was too brief."},
                    {
                        "role": "user",
                        "content": (
                            "Expand this into a substantially more detailed analysis. "
                            "Keep all claims evidence-grounded and cite [P#]."
                        ),
                    },
                ],
                **model_config(
                    longform=True,
                    max_tokens=2600,
                    temperature=0.16,
                ),
            )
            extra = (expand.choices[0].message.content or "").strip()
            if extra:
                content = f"{content}\n\n{extra}".strip()

        return {"response": content}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI API error: {str(exc)}")
