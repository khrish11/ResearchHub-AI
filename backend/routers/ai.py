from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Literal, List, Optional
import re
from routers.auth import get_current_user
from models import User
from utils.groq_client import (
    client,
    MODEL_CONFIG,
    model_config,
    groq_client_status,
    set_active_models,
)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/status")
def ai_status():
    status = groq_client_status()
    return {
        **status,
        "model": status.get("active_model") if status["enabled"] else None,
    }


@router.get("/models")
def ai_models(current_user: User = Depends(get_current_user)):
    status = groq_client_status()
    return {
        "configured": status.get("configured"),
        "enabled": status.get("enabled"),
        "error": status.get("error"),
        "available_models": status.get("available_models", []),
        "active_model": status.get("active_model"),
        "active_longform_model": status.get("active_longform_model"),
        "active_task_models": status.get("active_task_models", {}),
        "task_model_labels": status.get("task_model_labels", {}),
    }


class ModelSelectionRequest(BaseModel):
    model: str
    longform_model: Optional[str] = None
    apply_to_all: bool = True
    task_models: Optional[Dict[str, str]] = None


@router.post("/models/select")
def select_ai_models(req: ModelSelectionRequest, current_user: User = Depends(get_current_user)):
    selected_longform = req.model if req.apply_to_all else (req.longform_model or req.model)
    selected_task_models = dict(req.task_models or {})
    if req.apply_to_all:
        selected_task_models = {
            "chat": req.model,
            "upload_summary": req.model,
            "mindmap": selected_longform,
            "pipeline": selected_longform,
            **selected_task_models,
        }
    try:
        updated = set_active_models(req.model, selected_longform, selected_task_models)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    status = groq_client_status()
    return {
        "message": "AI model selection updated.",
        "configured": status.get("configured"),
        "enabled": status.get("enabled"),
        "error": status.get("error"),
        **updated,
    }


class AnalyzeRequest(BaseModel):
    prompt: str
    mode: Literal["general", "summaries", "insights", "review"] = "general"
    detail_level: Literal["quick", "balanced", "deep"] = "balanced"
    focus: Literal["broad", "methods", "applications", "risks"] = "broad"
    include_paper_links: bool = True
    reference_style: Literal["paper", "legacy"] = "paper"


ANALYZE_SYSTEM_PROMPTS = {
    "general": (
        "You are an expert research analyst. Deliver precise, technical, and evidence-aware answers. "
        "When source snippets are provided, cite them using human-readable references such as Paper 1, Paper 2."
    ),
    "summaries": (
        "You are writing expert-grade paper analyses. "
        "For each paper, cover problem framing, method details, dataset/benchmark setup, key quantitative findings, "
        "limitations, and practical implications. Avoid generic filler and keep evidence grounded in context. "
        "Use references like Paper 1, Paper 2 and avoid shorthand [P1]."
    ),
    "insights": (
        "You are extracting cross-paper insights. "
        "Group findings into themes, include contradictions, and indicate confidence with reasoning. "
        "Cite evidence as Paper N where possible."
    ),
    "review": (
        "You are a senior literature-review writer. "
        "Produce a structured long-form synthesis with explicit gaps, limitations, and next experiments. "
        "Ground claims in provided context and cite evidence using Paper N style references."
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
        "Target depth: 10-14 cross-paper insights plus contradictions, risk areas, and a prioritized action list. "
        "Include confidence (High/Medium/Low) for each major claim."
    ),
    "review": (
        "Target depth: substantial review draft (roughly 1200+ words when context supports it) with sections: "
        "Introduction, Taxonomy, Comparative Findings, Gaps, Key Insights, and Future Work."
    ),
}

ANALYZE_MAX_TOKENS = {
    "general": 3000,
    "summaries": 4200,
    "insights": 4600,
    "review": 5200,
}


DETAIL_LEVEL_TOKEN_MULTIPLIER = {
    "quick": 0.72,
    "balanced": 1.0,
    "deep": 1.22,
}


FOCUS_INSTRUCTIONS = {
    "broad": "Balanced across methods, findings, risks, and applications.",
    "methods": "Prioritize methodology comparisons, assumptions, and benchmark quality.",
    "applications": "Prioritize practical applicability, deployment constraints, and transferability.",
    "risks": "Prioritize limitations, uncertainty, failure modes, and evidence weaknesses.",
}


def _normalize_paper_refs(text: str, reference_style: str = "paper") -> str:
    if reference_style != "paper":
        return text
    normalized = text or ""
    normalized = re.sub(r"\[(?:P|p)\s*(\d+)\]", r"Paper \1", normalized)
    normalized = re.sub(r"\b(?:P|p)\s*(\d+)\b", r"Paper \1", normalized)
    normalized = re.sub(r"\bPaper\s+Paper\s+(\d+)\b", r"Paper \1", normalized)
    return normalized


def _extract_prompt_papers(prompt: str) -> List[Dict[str, Optional[str]]]:
    papers: Dict[int, Dict[str, Optional[str]]] = {}
    current_idx: Optional[int] = None
    for raw in (prompt or "").splitlines():
        line = raw.strip()
        if not line:
            continue

        title_match = re.match(r"^\[(?:P|p)\s*(\d+)\]\s*Title:\s*(.+)$", line)
        if not title_match:
            title_match = re.match(r"^Paper\s+(\d+)\s+Title:\s*(.+)$", line, re.IGNORECASE)
        if title_match:
            idx = int(title_match.group(1))
            title = title_match.group(2).strip()
            papers.setdefault(idx, {"title": title, "url": None, "doi": None})
            papers[idx]["title"] = title
            current_idx = idx
            continue

        if current_idx is None:
            continue
        if line.lower().startswith("url:"):
            papers[current_idx]["url"] = line.split(":", 1)[1].strip() or None
        elif line.lower().startswith("doi:"):
            papers[current_idx]["doi"] = line.split(":", 1)[1].strip() or None

    items: List[Dict[str, Optional[str]]] = []
    for idx in sorted(papers.keys()):
        info = papers[idx]
        doi = (info.get("doi") or "").strip()
        url = (info.get("url") or "").strip()
        if (not url or url.lower() == "n/a") and doi and doi.lower() != "n/a":
            clean = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
            if clean:
                url = f"https://doi.org/{clean}"
        items.append(
            {
                "paper": f"Paper {idx}",
                "title": info.get("title") or f"Paper {idx}",
                "url": url or None,
            }
        )
    return items


def _paper_links_section_from_prompt(prompt: str) -> str:
    papers = _extract_prompt_papers(prompt)
    if not papers:
        return ""
    rows: List[str] = ["## Paper Links"]
    for item in papers[:20]:
        paper_label = item["paper"] or "Paper"
        title = item["title"] or paper_label
        url = item["url"]
        if url:
            rows.append(f"- {paper_label}: [{title}]({url})")
        else:
            rows.append(f"- {paper_label}: {title} (Link unavailable)")
    return "\n".join(rows)


@router.post("/analyze")
async def analyze(req: AnalyzeRequest, current_user: User = Depends(get_current_user)):
    """
    Direct AI analysis endpoint.
    Frontend can pass a fully prepared prompt; this endpoint adds robust analysis instructions.
    """
    if not client:
        status = groq_client_status()
        detail = status.get("error") or "AI service is currently unavailable."
        if not status.get("configured"):
            detail = "AI service is not configured. Set GROQ_API_KEY in backend/.env and restart backend."
        raise HTTPException(status_code=503, detail=str(detail))

    trimmed = (req.prompt or "").strip()[:36000]
    if not trimmed:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    mode = req.mode if req.mode in ANALYZE_SYSTEM_PROMPTS else "general"
    detail_level = req.detail_level if req.detail_level in DETAIL_LEVEL_TOKEN_MULTIPLIER else "balanced"
    focus = req.focus if req.focus in FOCUS_INSTRUCTIONS else "broad"
    scaled_tokens = int(ANALYZE_MAX_TOKENS.get(mode, MODEL_CONFIG.get("max_tokens", 3000)) * DETAIL_LEVEL_TOKEN_MULTIPLIER[detail_level])
    target_tokens = max(1800, min(7600, scaled_tokens))

    system_prompt = (
        f"{ANALYZE_SYSTEM_PROMPTS[mode]} "
        f"{ANALYZE_OUTPUT_TARGETS[mode]} "
        f"Focus mode: {focus}. {FOCUS_INSTRUCTIONS[focus]} "
        f"Detail level: {detail_level}. "
        "When evidence is missing, explicitly say 'Insufficient evidence in provided papers.' "
        "Use section headers and concrete bullet points instead of generic paragraphs."
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
                task="pipeline",
                longform=mode in {"summaries", "insights", "review"},
                max_tokens=target_tokens,
                temperature=0.16 if mode in {"summaries", "insights", "review"} else 0.18,
            ),
        )
        content = (response.choices[0].message.content or "").strip()
        content = _normalize_paper_refs(content, req.reference_style)

        # Recovery pass: expand thin answers for long-form analysis modes.
        min_len = {"quick": 700, "balanced": 1100, "deep": 1600}.get(detail_level, 1100)
        if mode in {"summaries", "insights", "review"} and len(content) < min_len:
            expand = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": trimmed},
                    {"role": "assistant", "content": content or "Draft was too brief."},
                    {
                        "role": "user",
                        "content": (
                            "Expand this into a substantially more detailed analysis. "
                            "Keep all claims evidence-grounded and cite using Paper N notation."
                        ),
                    },
                ],
                **model_config(
                    task="pipeline",
                    longform=True,
                    max_tokens=min(3600, max(2200, target_tokens // 2 + 300)),
                    temperature=0.14,
                ),
            )
            extra = (expand.choices[0].message.content or "").strip()
            if extra:
                content = f"{content}\n\n{extra}".strip()
            content = _normalize_paper_refs(content, req.reference_style)

        if req.include_paper_links:
            links_section = _paper_links_section_from_prompt(trimmed)
            if links_section and "## Paper Links" not in content:
                content = f"{content}\n\n{links_section}".strip()

        return {
            "response": content,
            "mode": mode,
            "detail_level": detail_level,
            "focus": focus,
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI API error: {str(exc)}")
