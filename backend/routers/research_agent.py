import asyncio
import hashlib
import json
import math
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from repositories.research import Paper, SearchHistory, User, UserSessionState, Workspace, StructuredGap, ResearchIntelligenceArtifact, SavedResearchQuestion, ResearchPlan, ResearcherDecision
from repositories import ResearchRepository, get_research_repository
from routers.auth import get_current_user, has_analytics_admin_access
from routers.papers import search_global
from services.paper_check_service import get_job_status, queue_paper_check_job, requeue_failed_job
from services.ai_service import run_structured_json_task
from services.rag_hooks import index_paper_best_effort
from services.evidence_intelligence_service import get_evidence_service
from services.gap_intelligence_service import get_gap_service
from services.opportunity_scoring_service import get_opportunity_service
from services.research_question_service import get_question_service
from services.research_challenger_service import get_challenger_service
from services.citation_verification_service import get_citation_service
from services.knowledge_graph_enhancement_service import get_graph_enhancement_service
from services.research_plan_service import get_plan_service
from services.research_intelligence_artifact_service import get_artifact_service_instance
from utils.groq_client import client as groq_client
from utils.groq_client import model_config
from utils.groq_client import groq_client_status
from services.analytics_service import log_ai_usage

router = APIRouter(prefix="/research", tags=["research-agent"])

from utils.text_utils import STOP_WORDS as _STOP_WORDS

_DATASET_TERMS = {
    "cifar-10",
    "cifar10",
    "imagenet",
    "coco",
    "mnist",
    "svhn",
    "cityscapes",
    "kitti",
    "squad",
    "glue",
    "superglue",
    "mmlu",
    "wikitext",
    "commoncrawl",
    "physionet",
    "mimic-iii",
    "mimic-iv",
    "librispeech",
    "kddcup",
    "nsl-kdd",
    "unsw-nb15",
    "ecg",
    "chestxray",
    "chexpert",
}

_METRIC_TERMS = {
    "accuracy",
    "f1",
    "f1-score",
    "auc",
    "precision",
    "recall",
    "specificity",
    "sensitivity",
    "rmse",
    "mae",
    "mape",
    "bleu",
    "rouge",
    "map",
    "ndcg",
    "latency",
    "throughput",
    "robustness",
    "fairness",
    "calibration",
}

_SOURCE_QUALITY = {
    "openalex": 1.4,
    "semantic_scholar": 1.3,
    "semantic": 1.3,
    "springer": 1.3,
    "pubmed": 1.2,
    "arxiv": 1.1,
    "europe_pmc": 1.1,
    "europepmc": 1.1,
    "plos": 1.1,
    "elife": 1.1,
    "biorxiv": 1.0,
    "medrxiv": 1.0,
    "doaj": 1.0,
    "hal": 1.0,
    "datacite": 0.95,
    "nasa_ads": 1.05,
    "nasa": 1.05,
}


class AutonomousResearchRequest(BaseModel):
    goal: str = Field(min_length=2, max_length=500)
    workspace_id: Optional[int] = None
    year_from: Optional[int] = Field(default=None, ge=1950, le=2100)
    max_results: int = Field(default=80, ge=20, le=160)
    import_top_n: int = Field(default=12, ge=3, le=40)


class FullPipelineRequest(BaseModel):
    workspace_id: int
    goal: str = Field(min_length=2, max_length=500)
    year_from: Optional[int] = Field(default=None, ge=1950, le=2100)
    paper_ids: Optional[List[int]] = None
    max_results: int = Field(default=100, ge=20, le=180)
    import_top_n: int = Field(default=12, ge=3, le=50)
    strict_mode: bool = True
    include_advanced: bool = False


class WorkspaceScopedRequest(BaseModel):
    workspace_id: int
    paper_ids: Optional[List[int]] = None


class PaperCheckRequest(BaseModel):
    paper_id: Optional[int] = None
    raw_text: Optional[str] = Field(default=None, max_length=120000)
    workspace_id: Optional[int] = None
    prefer_async: bool = False
    paper_ids: Optional[List[int]] = None


class GapDetectionRequest(WorkspaceScopedRequest):
    topic: Optional[str] = None


class MultiAgentRequest(WorkspaceScopedRequest):
    topic: Optional[str] = None
    strict_mode: bool = False


class TrendPredictionRequest(BaseModel):
    workspace_id: Optional[int] = None
    query: Optional[str] = None
    max_results: int = Field(default=80, ge=20, le=160)


class ExperimentDesignRequest(WorkspaceScopedRequest):
    topic: str = Field(min_length=2, max_length=500)
    hypothesis: Optional[str] = None


class PaperDraftRequest(WorkspaceScopedRequest):
    topic: str = Field(min_length=2, max_length=500)
    target_format: str = Field(default="IEEE")
    citation_style: str = Field(default="IEEE")


class WritingSuggestionRequest(WorkspaceScopedRequest):
    topic: Optional[str] = None
    draft_text: str = Field(min_length=30, max_length=18000)
    max_suggestions: int = Field(default=8, ge=3, le=20)


class ResearchChatTurn(BaseModel):
    role: str
    content: str = Field(min_length=1, max_length=4000)


class ResearchChatRequest(WorkspaceScopedRequest):
    topic: Optional[str] = None
    message: str = Field(min_length=2, max_length=4000)
    context_text: Optional[str] = Field(default="", max_length=20000)
    draft_text: Optional[str] = Field(default="", max_length=20000)
    conversation: Optional[List[ResearchChatTurn]] = None
    max_actions: int = Field(default=6, ge=2, le=12)
    response_style: str = Field(default="balanced")
    grounded_only: bool = True


class EvidenceAnalysisRequest(WorkspaceScopedRequest):
    claim: str = Field(min_length=5, max_length=500)
    topic: Optional[str] = None


class OpportunityRankingRequest(WorkspaceScopedRequest):
    topic: Optional[str] = None


class QuestionGenerationRequest(WorkspaceScopedRequest):
    topic: Optional[str] = None
    max_questions: int = Field(default=10, ge=1, le=20)


class HypothesisChallengeRequest(WorkspaceScopedRequest):
    hypothesis: str = Field(min_length=5, max_length=500)


class CitationVerificationRequest(WorkspaceScopedRequest):
    pass


class KnowledgeGraphEnhancementRequest(WorkspaceScopedRequest):
    topic: Optional[str] = None
    layers: Optional[List[str]] = Field(default=["gap", "evidence", "opportunity", "citation"])


class ResearchIntelligenceArtifactRequest(BaseModel):
    workspace_id: int
    topic: str = Field(min_length=2, max_length=500)
    paper_ids: List[int] = Field(min_length=1, max_length=50)
    pipeline_version: Optional[str] = Field(default="1.0", max_length=20)


# Backward compatibility for existing client code/tests.
WritingChatTurn = ResearchChatTurn
WritingChatRequest = ResearchChatRequest


class SmartReadingRequest(BaseModel):
    workspace_id: int
    paper_id: Optional[int] = None
    text: Optional[str] = None


class ComparePapersRequest(BaseModel):
    workspace_id: int
    paper_ids: List[int] = Field(min_length=2, max_length=5)


class PersonalizedFeedRequest(BaseModel):
    workspace_id: int
    max_suggestions: int = Field(default=12, ge=4, le=30)
    force_live: bool = False
    refresh_seed: Optional[str] = None


class CitationReference(BaseModel):
    label: str
    paper_id: int


class CitationVerifyRequest(BaseModel):
    workspace_id: int
    draft_text: str = Field(min_length=20, max_length=30000)
    paper_ids: Optional[List[int]] = None
    references: Optional[List[CitationReference]] = None


class FaultDetectionRequest(BaseModel):
    workspace_id: int
    paper_id: int


class GenerateResearchReportRequest(BaseModel):
    paper_ids: List[int] = Field(default_factory=list, max_length=15)
    topic: Optional[str] = Field(default=None, max_length=1000)
    intelligence_artifact_id: Optional[str] = Field(default=None, max_length=100)


@router.post("/generate-report")
async def generate_research_report(
    request: GenerateResearchReportRequest,
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """
    Generate a structured multi-paper research report.

    Accepts either:
    - paper_ids (0..15)
    - topic (optional)
    - intelligence_artifact_id (optional) - if provided, uses persisted intelligence results
    """
    try:
        result = await aggregate_and_generate_report(
            repo=repo,
            user_id=str(current_user.id),
            paper_ids=request.paper_ids,
            topic=request.topic,
            intelligence_artifact_id=request.intelligence_artifact_id,
        )
        return {"result": result}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


async def aggregate_and_generate_report(
    repo: ResearchRepository,
    user_id: str,
    paper_ids: List[int],
    topic: Optional[str] = None,
    intelligence_artifact_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a structured research report from selected papers.
    
    This function synthesizes multiple papers into a comprehensive report
    with sections: title, abstract, key themes, literature overview,
    methodology trends, consensus findings, conflicting views, research gaps,
    future directions, and conclusion.
    
    If intelligence_artifact_id is provided, uses persisted intelligence results
    to generate an enhanced report with evidence-backed insights.
    """
    # If intelligence artifact is provided, use intelligence-backed generation
    if intelligence_artifact_id:
        return await _generate_intelligence_backed_report(
            repo=repo,
            user_id=user_id,
            artifact_id=intelligence_artifact_id,
            paper_ids=paper_ids,
            topic=topic,
        )
    
    # Otherwise, use standard report generation
    return await _generate_standard_report(
        repo=repo,
        user_id=user_id,
        paper_ids=paper_ids,
        topic=topic,
    )


async def _generate_standard_report(
    repo: ResearchRepository,
    user_id: str,
    paper_ids: List[int],
    topic: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a standard research report without intelligence artifacts."""
    # Fetch papers from repository
    papers = []
    for paper_id in paper_ids:
        paper = repo.get_paper_for_user(paper_id, int(user_id))
        if paper:
            papers.append(paper)
    
    if not papers:
        raise ValueError("No valid papers found for the provided IDs")
    
    # Build paper context for LLM
    paper_context = _paper_context_from_db(papers, limit=15)
    
    # Generate report using LLM
    system_prompt = (
        "You are an expert research analyst specializing in literature synthesis. "
        "Generate a comprehensive, well-structured research report based on the provided papers. "
        "Be precise, evidence-grounded, and avoid generic filler. "
        "Use specific details from the papers and cite them as Paper 1, Paper 2, etc."
    )
    
    user_prompt = (
        f"Topic: {topic or 'Multi-paper analysis'}\n"
        f"Number of papers: {len(papers)}\n\n"
        "Generate a research report with the following EXACT structure:\n"
        "1. Title: A concise, descriptive title for the report\n"
        "2. Abstract: A 150-200 word summary of the entire report\n"
        "3. Key Themes: 5-7 bullet points of major themes across the papers\n"
        "4. Literature Overview: 200-300 words on the research landscape\n"
        "5. Methodology Trends: 150-250 words on methodological approaches\n"
        "6. Consensus Findings: 150-250 words on agreed-upon conclusions\n"
        "7. Conflicting Views: 150-250 words on disagreements or contradictions\n"
        "8. Research Gaps: 5-7 bullet points on missing areas or limitations\n"
        "9. Future Directions: 5-7 bullet points on promising research directions\n"
        "10. Conclusion: 100-150 words wrapping up the report\n\n"
        f"Paper context:\n{paper_context}\n\n"
        "Return the response as a JSON object with these exact keys:\n"
        "title, abstract, key_themes (array), literature_overview, methodology_trends, "
        "consensus_findings, conflicting_views, research_gaps (array), future_directions (array), conclusion"
    )
    
    llm_output = _llm_generate(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=3800,
        longform=True,
        min_chars=1200,
        expansion_instruction=(
            "Expand the response to ensure all sections are present and substantial. "
            "Include specific details from the papers and cite them appropriately."
        ),
    )
    
    if not llm_output:
        # Fallback to basic report if LLM fails
        return _generate_fallback_report(papers, topic)
    
    # Parse LLM output as JSON
    try:
        result = json.loads(llm_output)
        
        # Validate required fields
        required_fields = [
            "title", "abstract", "key_themes", "literature_overview",
            "methodology_trends", "consensus_findings", "conflicting_views",
            "research_gaps", "future_directions", "conclusion"
        ]
        
        for field in required_fields:
            if field not in result:
                result[field] = "" if field not in ["key_themes", "research_gaps", "future_directions"] else []
        
        return result
    except json.JSONDecodeError:
        # If JSON parsing fails, try to extract sections from markdown
        return _parse_markdown_report(llm_output, papers, topic)


async def _generate_intelligence_backed_report(
    repo: ResearchRepository,
    user_id: str,
    artifact_id: str,
    paper_ids: List[int],
    topic: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate an intelligence-backed research report using persisted artifact data.
    
    This leverages the 7-stage intelligence pipeline results to create a comprehensive
    report with evidence-backed insights, provenance tracking, and structured sections.
    """
    # Load and validate artifact
    artifact = repo.get_research_intelligence_artifact(artifact_id)
    if not artifact:
        raise ValueError(f"Research Intelligence Artifact not found: {artifact_id}")
    
    # Validate workspace ownership
    if not repo.workspace_exists_for_user(artifact.workspace_id, int(user_id)):
        raise ValueError("Artifact does not belong to your workspace")
    
    # Validate artifact status
    if artifact.status not in ["completed", "partial"]:
        raise ValueError(f"Artifact status is {artifact.status}; only completed or partial artifacts can generate reports")
    
    # Fetch papers
    papers = []
    source_paper_ids = paper_ids if paper_ids else artifact.paper_ids
    for paper_id in source_paper_ids:
        paper = repo.get_paper_for_user(paper_id, int(user_id))
        if paper:
            papers.append(paper)
    
    if not papers:
        raise ValueError("No valid papers found for the provided IDs")
    
    # Build intelligence context
    intelligence_context = _build_intelligence_context(artifact, papers)
    
    # Generate enhanced report using LLM with intelligence context
    system_prompt = (
        "You are an expert research analyst specializing in literature synthesis with "
        "access to comprehensive intelligence analysis. Generate a detailed, evidence-backed "
        "research report that incorporates the provided intelligence insights. "
        "Be precise, evidence-grounded, and cite specific papers and intelligence sources. "
        "Preserve all provenance information (paper IDs, confidence scores, evidence types)."
    )
    
    user_prompt = (
        f"Topic: {topic or artifact.topic}\n"
        f"Number of papers: {len(papers)}\n"
        f"Artifact ID: {artifact_id}\n"
        f"Overall Intelligence Score: {artifact.overall_score or 'N/A'}\n\n"
        "Generate an intelligence-backed research report with the following structure:\n"
        "1. Title: A descriptive title reflecting the intelligence analysis\n"
        "2. Abstract: 200-250 word summary incorporating intelligence findings\n"
        "3. Key Themes: 5-7 bullet points from intelligence analysis\n"
        "4. Research Landscape: Important papers, themes, methods, datasets, metrics\n"
        "5. Evidence Landscape: Major claims, supporting/contradictory evidence, strength, confidence\n"
        "6. Research Gaps: Categories, descriptions, supporting papers, confidence, novelty scores\n"
        "7. Research Opportunities: Ranked opportunities with scores, evidence strength, impact\n"
        "8. Research Questions: Generated questions with category, complexity, rationale\n"
        "9. Hypothesis Challenge: Supporting evidence, counter-evidence, methodological weaknesses\n"
        "10. Citation Integrity: Quality, accessibility, consistency, issues\n"
        "11. Knowledge Graph Insights: Key relationships and patterns\n"
        "12. Recommended Research Direction: Highest-value opportunity, key risks, next steps\n"
        "13. Conclusion: Evidence-grounded summary with provenance\n\n"
        f"Intelligence Context:\n{intelligence_context}\n\n"
        "Return as JSON with all sections. Include provenance (paper IDs, confidence, scores) "
        "wherever available. Do not invent information when intelligence is insufficient."
    )
    
    llm_output = _llm_generate(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=5200,
        longform=True,
        min_chars=1800,
        expansion_instruction=(
            "Expand the response to ensure all intelligence-backed sections are present. "
            "Include specific evidence, paper IDs, confidence scores, and provenance information. "
            "Do not fabricate citations - only use information from the intelligence context."
        ),
    )
    
    if not llm_output:
        # Fallback to intelligence-structured report if LLM fails
        return _generate_intelligence_fallback_report(artifact, papers, topic)
    
    # Parse LLM output as JSON
    try:
        result = json.loads(llm_output)
        
        # Add provenance metadata
        result["_provenance"] = {
            "intelligence_artifact_id": artifact_id,
            "workspace_id": artifact.workspace_id,
            "paper_ids": source_paper_ids,
            "artifact_status": artifact.status,
            "overall_score": artifact.overall_score,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        
        # Ensure standard fields exist for backward compatibility
        standard_fields = [
            "title", "abstract", "key_themes", "literature_overview",
            "methodology_trends", "consensus_findings", "conflicting_views",
            "research_gaps", "future_directions", "conclusion"
        ]
        
        for field in standard_fields:
            if field not in result:
                result[field] = "" if field not in ["key_themes", "research_gaps", "future_directions"] else []
        
        return result
    except json.JSONDecodeError:
        # If JSON parsing fails, try to extract sections from markdown
        result = _parse_markdown_report(llm_output, papers, topic)
        result["_provenance"] = {
            "intelligence_artifact_id": artifact_id,
            "workspace_id": artifact.workspace_id,
            "paper_ids": source_paper_ids,
            "artifact_status": artifact.status,
            "overall_score": artifact.overall_score,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        return result


def _build_intelligence_context(artifact, papers: List[Paper]) -> str:
    """Build a structured context string from intelligence artifact data."""
    context_parts = []
    
    # Evidence Analysis
    if artifact.evidence_analysis:
        context_parts.append("=== EVIDENCE ANALYSIS ===")
        evidence = artifact.evidence_analysis
        if evidence.get("classification"):
            context_parts.append(f"Supporting papers: {len(evidence['classification'].get('supporting_papers', []))}")
            context_parts.append(f"Contradicting papers: {len(evidence['classification'].get('contradicting_papers', []))}")
        if evidence.get("strength"):
            strength = evidence["strength"]
            context_parts.append(f"Overall strength: {strength.get('overall_strength', 'N/A')}")
            context_parts.append(f"Confidence: {strength.get('confidence', 'N/A')}")
    
    # Gap Analysis
    if artifact.gap_analysis:
        context_parts.append("\n=== RESEARCH GAPS ===")
        gaps = artifact.gap_analysis
        if gaps.get("total_gaps"):
            context_parts.append(f"Total gaps identified: {gaps['total_gaps']}")
        if gaps.get("top_opportunities"):
            context_parts.append("Top opportunities:")
            for opp in gaps["top_opportunities"][:3]:
                context_parts.append(f"- {opp.get('description', 'N/A')} (confidence: {opp.get('confidence', 'N/A')})")
    
    # Opportunity Ranking
    if artifact.opportunity_ranking:
        context_parts.append("\n=== OPPORTUNITY RANKING ===")
        opps = artifact.opportunity_ranking
        if opps.get("total_opportunities"):
            context_parts.append(f"Total opportunities: {opps['total_opportunities']}")
        if opps.get("top_opportunity"):
            top = opps["top_opportunity"]
            context_parts.append(f"Highest-value: {top.get('gap_description', 'N/A')} (score: {top.get('overall_score', 'N/A')})")
    
    # Research Questions
    if artifact.research_questions:
        context_parts.append("\n=== RESEARCH QUESTIONS ===")
        questions = artifact.research_questions
        if questions.get("total_questions"):
            context_parts.append(f"Total questions: {questions['total_questions']}")
        if questions.get("top_questions"):
            context_parts.append("Top questions:")
            for q in questions["top_questions"][:3]:
                context_parts.append(f"- {q.get('question', 'N/A')} (complexity: {q.get('complexity', 'N/A')})")
    
    # Hypothesis Challenges
    if artifact.hypothesis_challenges:
        context_parts.append("\n=== HYPOTHESIS CHALLENGES ===")
        challenges = artifact.hypothesis_challenges
        if challenges.get("total_challenges"):
            context_parts.append(f"Total challenges: {challenges['total_challenges']}")
        if challenges.get("strongest_challenge"):
            strong = challenges["strongest_challenge"]
            context_parts.append(f"Strongest challenge: {strong.get('challenge_text', 'N/A')}")
    
    # Citation Verification
    if artifact.citation_verification:
        context_parts.append("\n=== CITATION INTEGRITY ===")
        citation = artifact.citation_verification
        if citation.get("overall_confidence"):
            context_parts.append(f"Overall confidence: {citation['overall_confidence']}")
        if citation.get("critical_issues"):
            context_parts.append(f"Critical issues: {len(citation['critical_issues'])}")
    
    # Knowledge Graph
    if artifact.knowledge_graph:
        context_parts.append("\n=== KNOWLEDGE GRAPH ===")
        kg = artifact.knowledge_graph
        if kg.get("nodes"):
            context_parts.append(f"Total nodes: {len(kg['nodes'])}")
        if kg.get("edges"):
            context_parts.append(f"Total edges: {len(kg['edges'])}")
    
    # Paper context
    context_parts.append("\n=== PAPER DETAILS ===")
    for i, paper in enumerate(papers[:10], 1):
        context_parts.append(f"Paper {i}: {paper.title}")
        if paper.authors:
            context_parts.append(f"  Authors: {paper.authors[:100]}...")
        if paper.abstract:
            context_parts.append(f"  Abstract: {paper.abstract[:200]}...")
    
    return "\n".join(context_parts)


def _generate_intelligence_fallback_report(artifact, papers: List[Paper], topic: Optional[str]) -> Dict[str, Any]:
    """Generate a basic intelligence-backed report when LLM is unavailable."""
    result = {
        "title": topic or artifact.topic or "Intelligence-Backed Research Report",
        "abstract": f"This report is based on Research Intelligence Artifact {artifact.id}. Due to AI service unavailability, this is a structured summary of the intelligence analysis.",
        "key_themes": [
            "Evidence-based analysis",
            "Research gap identification",
            "Opportunity ranking",
            "Citation integrity assessment",
        ],
        "literature_overview": f"Analysis covers {len(papers)} papers with comprehensive intelligence processing including evidence analysis, gap detection, opportunity ranking, and citation verification.",
        "methodology_trends": "Methodological trends analysis available in intelligence artifact (AI service unavailable for detailed synthesis).",
        "consensus_findings": "Consensus findings available in intelligence artifact (AI service unavailable for detailed synthesis).",
        "conflicting_views": "Conflicting views analysis available in intelligence artifact (AI service unavailable for detailed synthesis).",
        "research_gaps": [],
        "future_directions": [],
        "conclusion": f"This intelligence-backed report summarizes artifact {artifact.id} with overall score {artifact.overall_score or 'N/A'}. Enable AI service for comprehensive automated synthesis.",
    }
    
    # Add gap information if available
    if artifact.gap_analysis and artifact.gap_analysis.get("top_opportunities"):
        result["research_gaps"] = [
            opp.get("description", "N/A") 
            for opp in artifact.gap_analysis["top_opportunities"][:5]
        ]
    
    # Add opportunity information if available
    if artifact.opportunity_ranking and artifact.opportunity_ranking.get("opportunities"):
        result["future_directions"] = [
            opp.get("gap_description", "N/A")
            for opp in artifact.opportunity_ranking["opportunities"][:5]
        ]
    
    # Add provenance
    result["_provenance"] = {
        "intelligence_artifact_id": artifact.id,
        "workspace_id": artifact.workspace_id,
        "paper_ids": artifact.paper_ids,
        "artifact_status": artifact.status,
        "overall_score": artifact.overall_score,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    
    return result


def _generate_fallback_report(papers: List[Paper], topic: Optional[str]) -> Dict[str, Any]:
    """Generate a basic report when LLM is unavailable."""
    titles = [p.title for p in papers]
    return {
        "title": topic or f"Analysis of {len(papers)} Research Papers",
        "abstract": f"This report analyzes {len(papers)} research papers. Due to AI service unavailability, this is a basic summary.",
        "key_themes": [
            "Multi-paper analysis",
            "Research methodology",
            "Findings synthesis",
            "Literature review",
        ],
        "literature_overview": f"The analysis covers {len(papers)} papers with titles: {', '.join(titles[:3])}{'...' if len(titles) > 3 else ''}.",
        "methodology_trends": "Methodological analysis unavailable due to AI service limitations.",
        "consensus_findings": "Consensus analysis unavailable due to AI service limitations.",
        "conflicting_views": "Conflict analysis unavailable due to AI service limitations.",
        "research_gaps": [
            "AI service unavailable for gap analysis",
            "Consider manual review for detailed gap identification",
        ],
        "future_directions": [
            "Enable AI service for automated future direction analysis",
            "Manual literature review for detailed recommendations",
        ],
        "conclusion": f"This basic summary covers {len(papers)} papers. Enable AI service for comprehensive automated analysis.",
    }


def _parse_markdown_report(markdown: str, papers: List[Paper], topic: Optional[str]) -> Dict[str, Any]:
    """Parse a markdown-formatted report into the expected structure."""
    lines = markdown.split('\n')
    sections = {
        "title": topic or "Research Report",
        "abstract": "",
        "key_themes": [],
        "literature_overview": "",
        "methodology_trends": "",
        "consensus_findings": "",
        "conflicting_views": "",
        "research_gaps": [],
        "future_directions": [],
        "conclusion": "",
    }
    
    current_section = None
    current_content = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Detect section headers
        if line.lower().startswith("title:"):
            sections["title"] = line.split(":", 1)[1].strip()
            current_section = None
        elif line.lower().startswith("abstract:"):
            current_section = "abstract"
            current_content = []
        elif line.lower().startswith("key themes:"):
            current_section = "key_themes"
            current_content = []
        elif line.lower().startswith("literature overview:"):
            current_section = "literature_overview"
            current_content = []
        elif line.lower().startswith("methodology trends:"):
            current_section = "methodology_trends"
            current_content = []
        elif line.lower().startswith("consensus findings:"):
            current_section = "consensus_findings"
            current_content = []
        elif line.lower().startswith("conflicting views:"):
            current_section = "conflicting_views"
            current_content = []
        elif line.lower().startswith("research gaps:"):
            current_section = "research_gaps"
            current_content = []
        elif line.lower().startswith("future directions:"):
            current_section = "future_directions"
            current_content = []
        elif line.lower().startswith("conclusion:"):
            current_section = "conclusion"
            current_content = []
        elif line.startswith("- ") or line.startswith("* "):
            # Bullet point
            bullet = line[2:].strip()
            if current_section in ["key_themes", "research_gaps", "future_directions"]:
                current_content.append(bullet)
        else:
            # Regular content
            if current_section:
                current_content.append(line)
    
    # Assign content to sections
    sections["abstract"] = "\n".join(current_content) if current_section == "abstract" else ""
    sections["literature_overview"] = "\n".join(current_content) if current_section == "literature_overview" else ""
    sections["methodology_trends"] = "\n".join(current_content) if current_section == "methodology_trends" else ""
    sections["consensus_findings"] = "\n".join(current_content) if current_section == "consensus_findings" else ""
    sections["conflicting_views"] = "\n".join(current_content) if current_section == "conflicting_views" else ""
    sections["conclusion"] = "\n".join(current_content) if current_section == "conclusion" else ""
    
    return sections


def _tokenize(text: str) -> List[str]:
    tokens = re.findall(r"[a-zA-Z0-9]{3,}", (text or "").lower())
    return [token for token in tokens if token not in _STOP_WORDS]


def _year_from_text(text: str) -> int:
    years = []
    for match in re.finditer(r"(19|20)\d{2}", text or ""):
        try:
            years.append(int(match.group(0)))
        except ValueError:
            continue
    return max(years) if years else 0


def _parse_published_datetime(
    raw_value: Any, fallback_year: int = 0
) -> Optional[datetime]:
    raw = str(raw_value or "").strip()
    if raw:
        normalized = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            pass

        for fmt in (
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y-%m",
            "%Y/%m",
            "%Y",
        ):
            try:
                parsed = datetime.strptime(
                    raw[:10]
                    if fmt in {"%Y-%m-%d", "%Y/%m/%d"}
                    else raw[:7]
                    if fmt in {"%Y-%m", "%Y/%m"}
                    else raw[:4],
                    fmt,
                )
                return parsed.replace(tzinfo=timezone.utc)
            except Exception:
                continue

        match = re.search(r"(19|20)\d{2}", raw)
        if match:
            try:
                year = int(match.group(0))
                return datetime(year, 1, 1, tzinfo=timezone.utc)
            except Exception:
                pass

    if 1900 <= int(fallback_year or 0) <= 2100:
        return datetime(int(fallback_year), 1, 1, tzinfo=timezone.utc)
    return None


def _history_query_signals(rows: List[SearchHistory]) -> Dict[str, List[str]]:
    weighted_queries: Counter[str] = Counter()
    weighted_keywords: Counter[str] = Counter()
    now = datetime.now(timezone.utc)

    for idx, row in enumerate(rows):
        query = str(row.query or "").strip()
        if not query:
            continue

        recency_rank_weight = max(0.35, 1.5 - (idx * 0.08))
        age_weight = 1.0
        if row.created_at:
            created_at = row.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            age_days = max(0, int((now - created_at).total_seconds() // 86400))
            age_weight = max(0.30, 1.15 - (min(age_days, 60) / 75))

        result_weight = 1.0 + (min(max(0, int(row.result_count or 0)), 150) / 300)
        total_weight = recency_rank_weight * age_weight * result_weight

        weighted_queries[query] += total_weight
        for token in _tokenize(query):
            weighted_keywords[token] += total_weight

    top_queries = [query for query, _ in weighted_queries.most_common(8)]
    top_keywords = [token for token, _ in weighted_keywords.most_common(18)]
    return {
        "queries": top_queries,
        "keywords": top_keywords,
    }


def _compose_query_seeds(
    workspace_keywords: List[str],
    history_queries: List[str],
    realtime_queries: List[str],
    limit: int = 4,
) -> List[str]:
    ordered = []
    seen = set()
    for item in [*history_queries, *realtime_queries]:
        text = str(item or "").strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        ordered.append(text)
        if len(ordered) >= limit:
            return ordered

    for idx in range(0, min(8, len(workspace_keywords)), 2):
        pair = workspace_keywords[idx : idx + 2]
        if not pair:
            continue
        text = " ".join(pair).strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        ordered.append(text)
        if len(ordered) >= limit:
            break
    return ordered


async def _fetch_openalex_recent_titles(seed: str, max_items: int = 18) -> List[str]:
    term = str(seed or "").strip()
    if not term:
        return []
    since = (datetime.now(timezone.utc) - timedelta(days=160)).date().isoformat()
    params = {
        "search": term,
        "sort": "publication_date:desc",
        "per-page": min(max_items, 30),
        "filter": f"from_publication_date:{since}",
    }
    headers = {"User-Agent": "Soyog-AI/1.0"}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(4.5, connect=2.0)) as client:
            response = await client.get(
                "https://api.openalex.org/works", params=params, headers=headers
            )
            if response.status_code >= 400:
                return []
            data = response.json() if response.content else {}
            results = data.get("results") or []
            titles = [
                str(item.get("title") or "").strip()
                for item in results
                if str(item.get("title") or "").strip()
            ]
            return titles[:max_items]
    except Exception:
        return []


async def _fetch_arxiv_recent_titles(seed: str, max_items: int = 16) -> List[str]:
    term = str(seed or "").strip()
    if not term:
        return []
    params = {
        "search_query": f"all:{term}",
        "start": 0,
        "max_results": min(max_items, 25),
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    headers = {"User-Agent": "Soyog-AI/1.0"}
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(4.5, connect=2.0), headers=headers
        ) as client:
            response = await client.get(
                "https://export.arxiv.org/api/query", params=params
            )
            if response.status_code >= 400 or not response.text:
                return []
            root = ET.fromstring(response.text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            titles: List[str] = []
            for entry in root.findall("atom:entry", ns):
                title_node = entry.find("atom:title", ns)
                if title_node is None:
                    continue
                title = str(title_node.text or "").replace("\n", " ").strip()
                if title:
                    titles.append(title)
            return titles[:max_items]
    except Exception:
        return []


async def _fetch_realtime_signal_bundle(seed_terms: List[str]) -> Dict[str, Any]:
    seeds: List[str] = []
    seen = set()
    for term in seed_terms:
        value = str(term or "").strip()
        key = value.lower()
        if not value or key in seen:
            continue
        seen.add(key)
        seeds.append(value)
        if len(seeds) >= 3:
            break

    if not seeds:
        return {
            "trending_keywords": [],
            "realtime_queries": [],
            "source_pulse": {},
        }

    tasks = []
    for seed in seeds[:2]:
        tasks.append(_fetch_openalex_recent_titles(seed))
        tasks.append(_fetch_arxiv_recent_titles(seed))
    results = await asyncio.gather(*tasks, return_exceptions=True)

    openalex_titles: List[str] = []
    arxiv_titles: List[str] = []
    for idx, payload in enumerate(results):
        if isinstance(payload, Exception):
            continue
        titles = payload if isinstance(payload, list) else []
        if idx % 2 == 0:
            openalex_titles.extend(titles)
        else:
            arxiv_titles.extend(titles)

    combined_titles = [*openalex_titles, *arxiv_titles]
    keyword_scores = Counter(_tokenize(" ".join(combined_titles)))
    trending_keywords = [word for word, _ in keyword_scores.most_common(12)]

    realtime_queries: List[str] = []
    seen_queries = set()
    for idx in range(0, min(len(trending_keywords), 8), 2):
        phrase = " ".join(trending_keywords[idx : idx + 2]).strip()
        key = phrase.lower()
        if not phrase or key in seen_queries:
            continue
        seen_queries.add(key)
        realtime_queries.append(phrase)

    if not realtime_queries:
        realtime_queries = seeds[:2]

    source_pulse = {
        "openalex": round(min(0.9, len(openalex_titles) / 18), 3),
        "arxiv": round(min(0.8, len(arxiv_titles) / 16), 3),
    }
    return {
        "trending_keywords": trending_keywords,
        "realtime_queries": realtime_queries[:4],
        "source_pulse": source_pulse,
    }


def _split_authors(authors: Any) -> List[str]:
    if isinstance(authors, list):
        return [str(a).strip() for a in authors if str(a).strip()]
    if isinstance(authors, str):
        return [x.strip() for x in authors.replace(";", ",").split(",") if x.strip()]
    return []


def _paper_primary_link(paper: Dict[str, Any]) -> str:
    url = str(paper.get("url") or "").strip()
    if url:
        return url
    doi = str(paper.get("doi") or "").strip()
    if doi:
        clean = (
            doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
        )
        if clean:
            return f"https://doi.org/{clean}"
    return ""


def _normalize_candidate(raw: Dict[str, Any], index: int) -> Dict[str, Any]:
    title = str(raw.get("title") or "").strip() or f"Untitled Paper {index}"
    abstract = str(raw.get("abstract") or "").strip() or "No abstract available."
    year = _year_from_text(str(raw.get("published") or ""))
    if not year:
        year = _year_from_text(f"{title} {abstract}")
    return {
        "index": index,
        "title": title,
        "abstract": abstract,
        "authors": _split_authors(raw.get("authors")),
        "source": str(raw.get("source") or "unknown").strip().lower(),
        "published": str(raw.get("published") or "").strip(),
        "year": year,
        "doi": str(raw.get("doi") or "").strip(),
        "url": _paper_primary_link(raw),
        "pdf_url": str(raw.get("pdf_url") or "").strip(),
        "citation_count": 0,
        "relevance_score": 0.0,
        "ranking_score": 0.0,
    }


def _extract_keywords(text: str, top_n: int = 20) -> List[str]:
    counts = Counter(_tokenize(text))
    return [word for word, _ in counts.most_common(top_n)]


def _extract_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [p.strip() for p in parts if len(p.strip()) > 24]


def _overlap_score(a: str, b: str) -> float:
    a_tokens = set(_tokenize(a))
    b_tokens = set(_tokenize(b))
    if not a_tokens or not b_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / max(len(a_tokens), 1)


def _repo_for_db() -> ResearchRepository:
    return get_research_repository()


def _workspace_or_default(
    current_user: User, workspace_id: Optional[int], default_name: str
):
    repo = _repo_for_db()
    if workspace_id is not None:
        workspace = repo.find_workspace_for_user(workspace_id, current_user.id)
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")
        return workspace

    workspace = repo.find_workspace_by_name_for_user(current_user.id, default_name)
    if workspace:
        return workspace

    return repo.create_workspace(
        current_user.id, default_name, "Auto-created research workspace"
    )


def _load_workspace_papers(
    workspace, paper_ids: Optional[List[int]] = None
) -> List[Paper]:
    repo = _repo_for_db()
    return list(repo.list_papers_for_workspace(workspace.id, paper_ids))


def _find_workspace_paper(workspace_id: int, user_id: int, paper_id: int):
    repo = _repo_for_db()
    paper = repo.find_paper_for_user(paper_id, user_id)
    if not paper:
        return None
    if int(getattr(paper, "workspace_id", 0) or 0) != int(workspace_id):
        return None
    return paper


async def _search_global_candidates(
    query: str,
    max_results: int,
    current_user: User,
    offset: int = 0,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    payload = await search_global(
        query=query,
        max_results=max_results,
        offset=max(0, int(offset or 0)),
        track_history=False,
        current_user=current_user,
    )
    raw_papers = payload.get("papers") or []
    normalized = [
        _normalize_candidate(paper, index=i + 1) for i, paper in enumerate(raw_papers)
    ]
    return normalized, payload


def _normalize_paper_refs(text: str) -> str:
    normalized = text or ""
    normalized = re.sub(r"\[(?:P|p)\s*(\d+)\]", r"Paper \1", normalized)
    normalized = re.sub(r"\b(?:P|p)\s*(\d+)\b", r"Paper \1", normalized)
    normalized = re.sub(r"\bPaper\s+Paper\s+(\d+)\b", r"Paper \1", normalized)
    return normalized


def _llm_generate(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 2400,
    longform: bool = True,
    task: str = "pipeline",
    min_chars: int = 240,
    temperature: float = 0.16,
    expansion_instruction: Optional[str] = None,
    required_headings: Optional[List[str]] = None,
) -> Optional[str]:
    if not groq_client:
        return None

    def _is_response_sufficient(text: str) -> bool:
        candidate = (text or "").strip()
        if not candidate or len(candidate) < min_chars:
            return False
        if not required_headings:
            return True
        low = candidate.lower()
        present = 0
        for heading in required_headings:
            marker = str(heading or "").strip().lower()
            if not marker:
                continue
            if marker in low:
                present += 1
        threshold = max(1, min(len(required_headings), 2))
        return present >= threshold

    # Route name for analytics: use the task identifier
    _route = f"research_agent_{task}"
    _input_size = len(user_prompt)
    _t0 = time.monotonic()
    _final_text: Optional[str] = None

    try:
        response = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt[:28000]},
            ],
            **model_config(
                task=task,
                longform=longform,
                max_tokens=max_tokens,
                temperature=temperature,
            ),
        )
        _used_model = str(getattr(response, "model", "") or "")
        text = _normalize_paper_refs(
            (response.choices[0].message.content or "").strip()
        )
        if _is_response_sufficient(text):
            _final_text = text
            _duration_ms = max(0, int((time.monotonic() - _t0) * 1000))
            log_ai_usage(
                _repo_for_db().db,
                user_id="system",
                route=_route,
                input_size=_input_size,
                output_size=len(_final_text),
                duration_ms=_duration_ms,
                status="success",
                model=_used_model,
                cache_hit=False,
            )
            return _final_text

        follow_up = expansion_instruction or (
            "Expand the draft substantially. Keep it evidence-grounded, structured with clear section headers, "
            "and cite references as Paper N where relevant."
        )
        second = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt[:28000]},
                {
                    "role": "assistant",
                    "content": text or "Initial draft was too short.",
                },
                {"role": "user", "content": follow_up},
            ],
            **model_config(
                task=task,
                longform=longform,
                max_tokens=min(5200, max(1800, max_tokens + 500)),
                temperature=max(0.1, temperature - 0.02),
            ),
        )
        expanded = _normalize_paper_refs(
            (second.choices[0].message.content or "").strip()
        )
        if _is_response_sufficient(expanded):
            _final_text = expanded
            _duration_ms = max(0, int((time.monotonic() - _t0) * 1000))
            log_ai_usage(
                _repo_for_db().db,
                user_id="system",
                route=_route,
                input_size=_input_size,
                output_size=len(_final_text),
                duration_ms=_duration_ms,
                status="success",
                model=_used_model,
                cache_hit=False,
            )
            return _final_text

        # Final recovery pass for thin outputs.
        third = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt[:28000]},
                {"role": "assistant", "content": expanded or text or "Draft was thin."},
                {
                    "role": "user",
                    "content": (
                        "Rewrite with substantially better depth and structure. "
                        "Use explicit section headings, concrete bullet points, and Paper N citations. "
                        "Avoid generic filler."
                    ),
                },
            ],
            **model_config(
                task=task,
                longform=longform,
                max_tokens=min(6200, max(2200, max_tokens + 900)),
                temperature=max(0.1, temperature - 0.03),
            ),
        )
        final_text = _normalize_paper_refs(
            (third.choices[0].message.content or "").strip()
        )
        candidates = [final_text, expanded, text]
        for candidate in candidates:
            if _is_response_sufficient(candidate):
                _final_text = candidate
                break
        merged = max((item for item in candidates if item), key=len, default="")
        _final_text = _final_text or merged or None

        # Log analytics after all passes complete
        _duration_ms = max(0, int((time.monotonic() - _t0) * 1000))
        if _final_text:
            log_ai_usage(
                _repo_for_db().db,
                user_id="system",
                route=_route,
                input_size=_input_size,
                output_size=len(_final_text),
                duration_ms=_duration_ms,
                status="success",
                model=_used_model,
                cache_hit=False,
            )
        return _final_text
    except Exception:
        _duration_ms = max(0, int((time.monotonic() - _t0) * 1000))
        try:
            log_ai_usage(
                _repo_for_db().db,
                user_id="system",
                route=_route,
                input_size=_input_size,
                output_size=0,
                duration_ms=_duration_ms,
                status="error",
                model="",
                cache_hit=False,
            )
        except Exception:
            pass
        return None


def _extract_named_sections(
    text: str, section_aliases: Dict[str, List[str]]
) -> Dict[str, str]:
    sections = {name: "" for name in section_aliases}
    active: Optional[str] = None

    for line in (text or "").splitlines():
        raw = line.strip()
        low = re.sub(r"^[#\s>\-\d\.\)\(]+", "", raw).strip().lower().rstrip(":")
        matched = None
        for section_name, aliases in section_aliases.items():
            if any(low.startswith(alias) for alias in aliases):
                matched = section_name
                break
        if matched is not None:
            active = matched
            continue
        if active:
            sections[active] += f"{line}\n"

    return {name: value.strip() for name, value in sections.items()}


def _extract_markdown_section_block(text: str, section_title: str) -> str:
    lines = (text or "").splitlines()
    target = section_title.strip().lower()
    active = False
    block: List[str] = []
    for raw in lines:
        stripped = raw.strip()
        if re.match(r"^#{1,6}\s+", stripped):
            heading = re.sub(r"^#{1,6}\s+", "", stripped).strip().lower().rstrip(":")
            if heading == target:
                active = True
                continue
            if active:
                break
        if active:
            block.append(raw)
    return "\n".join(block).strip()


@router.get("/capabilities")
def capabilities(current_user: User = Depends(get_current_user)):
    return {
        "features": [
            "autonomous_research_mode",
            "research_gap_detection",
            "interactive_knowledge_graph",
            "multi_agent_ai",
            "trend_prediction",
            "experiment_design_generator",
            "journal_aware_paper_writer",
            "smart_reading_mode",
            "paper_comparator",
            "personalized_research_feed",
            "citation_authenticity_verifier",
            "paper_fault_detection",
            "real_time_writing_suggestions",
            "research_chatbot",
            "full_pipeline_orchestrator",
        ],
        "ai_enabled": bool(groq_client),
    }


async def _fetch_openalex_citation_count(doi: str) -> int:
    clean = (
        (doi or "")
        .replace("https://doi.org/", "")
        .replace("http://doi.org/", "")
        .strip()
    )
    if not clean:
        return 0
    url = f"https://api.openalex.org/works/https://doi.org/{clean}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(3.5, connect=2.0)) as client:
            response = await client.get(url, headers={"User-Agent": "Soyog-AI/1.0"})
            if response.status_code >= 400:
                return 0
            data = response.json()
            value = data.get("cited_by_count")
            return int(value) if value is not None else 0
    except Exception:
        return 0


async def _enrich_citation_counts(
    candidates: List[Dict[str, Any]], max_lookups: int = 12
) -> None:
    with_doi = [candidate for candidate in candidates if candidate.get("doi")][
        :max_lookups
    ]
    if not with_doi:
        return

    sem = asyncio.Semaphore(4)

    async def _lookup(candidate: Dict[str, Any]) -> None:
        async with sem:
            candidate["citation_count"] = await _fetch_openalex_citation_count(
                str(candidate.get("doi") or "")
            )

    await asyncio.gather(
        *[_lookup(candidate) for candidate in with_doi], return_exceptions=True
    )


def _rank_candidates(
    candidates: List[Dict[str, Any]],
    goal: str,
    year_from: Optional[int] = None,
    trend_terms: Optional[List[str]] = None,
    affinity_terms: Optional[List[str]] = None,
    source_pulse: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    goal_tokens = set(_tokenize(goal))
    trend_tokens = set(_tokenize(" ".join(trend_terms or [])))
    affinity_tokens = set(_tokenize(" ".join(affinity_terms or [])))
    pulse_map = {str(k).lower(): float(v) for k, v in (source_pulse or {}).items()}
    now_year = datetime.now(timezone.utc).year
    now_ts = datetime.now(timezone.utc)
    ranked: List[Dict[str, Any]] = []

    for candidate in candidates:
        year = int(candidate.get("year") or 0)
        if year_from and year and year < year_from:
            continue

        text_tokens = set(
            _tokenize(f"{candidate.get('title', '')} {candidate.get('abstract', '')}")
        )
        overlap = len(goal_tokens & text_tokens)
        source = str(candidate.get("source") or "unknown").lower()
        source_weight = _SOURCE_QUALITY.get(source, 1.0)
        citation_count = int(candidate.get("citation_count") or 0)
        citation_score = math.log1p(max(citation_count, 0)) * 1.25
        recency_score = max(0.0, min(6.0, (year - 2018) * 0.35)) if year else 0.0
        published_dt = _parse_published_datetime(
            candidate.get("published"), fallback_year=year
        )
        freshness_score = 0.0
        if published_dt:
            age_days = max(0, int((now_ts - published_dt).total_seconds() // 86400))
            freshness_score = max(0.0, 3.2 - (min(age_days, 720) / 180))
        trend_hits = len(text_tokens & trend_tokens) if trend_tokens else 0
        affinity_hits = len(text_tokens & affinity_tokens) if affinity_tokens else 0
        source_runtime_boost = max(0.0, pulse_map.get(source, 0.0))
        pdf_bonus = 0.5 if candidate.get("pdf_url") else 0.0
        doi_bonus = 0.35 if candidate.get("doi") else 0.0
        relevance = overlap * 1.8
        ranking = (
            relevance
            + citation_score
            + recency_score
            + freshness_score
            + (trend_hits * 1.1)
            + (affinity_hits * 0.9)
            + source_runtime_boost
            + pdf_bonus
            + doi_bonus
        ) * source_weight
        if year and year > now_year + 1:
            ranking *= 0.7

        candidate["relevance_score"] = round(relevance, 3)
        candidate["freshness_score"] = round(freshness_score, 3)
        candidate["ranking_score"] = round(ranking, 3)
        reason_parts: List[str] = []
        if trend_hits > 0:
            reason_parts.append("Real-time topic momentum match")
        if affinity_hits > 0:
            reason_parts.append("Aligned with your recent search intent")
        if freshness_score >= 1.6:
            reason_parts.append("Fresh publication signal")
        if citation_count >= 20:
            reason_parts.append("Strong citation traction")
        if candidate.get("pdf_url"):
            reason_parts.append("PDF immediately available")
        if reason_parts:
            candidate["reason"] = " | ".join(reason_parts[:3])
        elif not candidate.get("reason"):
            candidate["reason"] = "High relevance to your workspace topics"
        ranked.append(candidate)

    ranked.sort(
        key=lambda row: (
            row.get("ranking_score", 0),
            row.get("citation_count", 0),
            row.get("year", 0),
        ),
        reverse=True,
    )
    return ranked


def _diversify_candidates(
    candidates: List[Dict[str, Any]], limit: int
) -> List[Dict[str, Any]]:
    if limit <= 0 or not candidates:
        return []

    buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        source = str(candidate.get("source") or "unknown").strip().lower() or "unknown"
        buckets[source].append(candidate)

    ordered_sources = sorted(
        buckets.keys(),
        key=lambda source: _SOURCE_QUALITY.get(source, 1.0),
        reverse=True,
    )
    if not ordered_sources:
        return candidates[:limit]

    unique_sources = max(1, len(ordered_sources))
    per_source_cap = max(1, math.ceil(limit / unique_sources) + 1)
    source_counts: Counter[str] = Counter()

    selected: List[Dict[str, Any]] = []
    rounds_without_pick = 0

    while len(selected) < limit and rounds_without_pick < len(ordered_sources):
        picked_any = False
        for source in ordered_sources:
            if len(selected) >= limit:
                break
            bucket = buckets.get(source) or []
            if not bucket:
                continue
            if source_counts[source] >= per_source_cap:
                continue
            selected.append(bucket.pop(0))
            source_counts[source] += 1
            picked_any = True
        rounds_without_pick = 0 if picked_any else rounds_without_pick + 1

    if len(selected) < limit:
        remaining: List[Dict[str, Any]] = []
        for source in ordered_sources:
            remaining.extend(buckets.get(source) or [])
        selected.extend(remaining[: max(0, limit - len(selected))])

    return selected[:limit]


def _candidate_context(candidates: List[Dict[str, Any]], limit: int = 16) -> str:
    rows = []
    for candidate in candidates[:limit]:
        abstract = str(candidate.get("abstract") or "").replace("\n", " ").strip()
        if len(abstract) > 1000:
            abstract = abstract[:1000] + "..."
        rows.append(
            "\n".join(
                [
                    f"Paper {candidate['index']} Title: {candidate['title']}",
                    f"Authors: {', '.join(candidate.get('authors') or []) or 'Unknown'}",
                    f"Source: {candidate.get('source') or 'unknown'}",
                    f"Year: {candidate.get('year') or 'Unknown'}",
                    f"Citation count: {candidate.get('citation_count') or 0}",
                    f"DOI: {candidate.get('doi') or 'N/A'}",
                    f"URL: {_paper_primary_link(candidate) or 'N/A'}",
                    f"Abstract: {abstract or 'No abstract available.'}",
                ]
            )
        )
    return "\n\n---\n\n".join(rows)


def _cluster_themes(
    candidates: List[Dict[str, Any]], max_clusters: int = 6
) -> List[Dict[str, Any]]:
    if not candidates:
        return []

    global_terms: Counter[str] = Counter()
    paper_terms: Dict[int, List[str]] = {}

    for candidate in candidates:
        idx = int(candidate["index"])
        terms = _extract_keywords(
            f"{candidate['title']} {candidate['abstract']}", top_n=12
        )
        paper_terms[idx] = terms
        global_terms.update(terms)

    seeds = [term for term, _ in global_terms.most_common(max_clusters * 2)]
    clusters: List[Dict[str, Any]] = []
    used = set()

    for seed in seeds:
        if len(clusters) >= max_clusters:
            break
        member_ids = [
            idx
            for idx, terms in paper_terms.items()
            if seed in terms and idx not in used
        ]
        if len(member_ids) < 2:
            continue

        for idx in member_ids:
            used.add(idx)

        top_terms = Counter()
        for idx in member_ids:
            top_terms.update(paper_terms[idx])

        member_papers = [
            candidate
            for candidate in candidates
            if int(candidate["index"]) in member_ids
        ][:10]
        clusters.append(
            {
                "cluster": seed.title(),
                "paper_count": len(member_ids),
                "keywords": [term for term, _ in top_terms.most_common(5)],
                "papers": [
                    {
                        "paper": f"Paper {paper['index']}",
                        "title": paper["title"],
                        "source": paper.get("source"),
                        "year": paper.get("year"),
                    }
                    for paper in member_papers
                ],
            }
        )

    leftovers = [
        candidate for candidate in candidates if int(candidate["index"]) not in used
    ]
    if leftovers:
        clusters.append(
            {
                "cluster": "Cross-Theme Frontier",
                "paper_count": len(leftovers),
                "keywords": _extract_keywords(
                    " ".join(f"{p['title']} {p['abstract']}" for p in leftovers),
                    top_n=6,
                ),
                "papers": [
                    {
                        "paper": f"Paper {paper['index']}",
                        "title": paper["title"],
                        "source": paper.get("source"),
                        "year": paper.get("year"),
                    }
                    for paper in leftovers[:10]
                ],
            }
        )

    return clusters[: max_clusters + 1]


def _heuristic_gap_detection(
    topic: str, candidates: List[Dict[str, Any]]
) -> Dict[str, Any]:
    text_blob = "\n".join(
        f"{candidate['title']} {candidate['abstract']}" for candidate in candidates
    )
    keywords = _extract_keywords(text_blob, top_n=18)

    dataset_counter = Counter()
    metric_counter = Counter()
    positive_counter = Counter()
    negative_counter = Counter()

    positive_terms = {
        "improve",
        "outperform",
        "state",
        "robust",
        "significant",
        "effective",
    }
    negative_terms = {
        "limitation",
        "limited",
        "challenge",
        "fails",
        "bias",
        "unstable",
        "uncertain",
    }

    for candidate in candidates:
        combined = f"{candidate['title']} {candidate['abstract']}".lower()
        tokens = set(_tokenize(combined))

        for term in _DATASET_TERMS:
            if term in combined:
                dataset_counter[term] += 1
        for metric in _METRIC_TERMS:
            if metric in combined:
                metric_counter[metric] += 1
        for term in positive_terms:
            if term in tokens:
                positive_counter.update(_extract_keywords(combined, top_n=5))
        for term in negative_terms:
            if term in tokens:
                negative_counter.update(_extract_keywords(combined, top_n=5))

    contradictions = []
    for concept, pos_count in positive_counter.most_common(6):
        neg_count = negative_counter.get(concept, 0)
        if pos_count > 0 and neg_count > 0:
            contradictions.append(
                f"Conflicting findings around '{concept}' (positive={pos_count}, negative={neg_count})."
            )

    under_tested = [
        dataset for dataset, count in dataset_counter.items() if count <= 1
    ][:8]
    missing_metrics = [
        metric for metric in _METRIC_TERMS if metric_counter.get(metric, 0) == 0
    ][:8]
    unexplored_variables = [
        word
        for word in keywords
        if word not in dataset_counter and word not in metric_counter
    ][:8]

    inconsistent_assumptions = []
    assumption_patterns = {
        "Closed-world assumptions appear frequently": [
            "closed",
            "controlled",
            "synthetic",
        ],
        "Limited resource or edge constraints under-evaluated": [
            "resource",
            "edge",
            "iot",
            "latency",
        ],
        "Generalization assumptions may be weak": [
            "generalization",
            "transfer",
            "domain",
        ],
    }
    low_text = text_blob.lower()
    for message, triggers in assumption_patterns.items():
        if sum(1 for trigger in triggers if trigger in low_text) <= 1:
            inconsistent_assumptions.append(message)

    summary_parts = []
    if contradictions:
        summary_parts.append(f"{len(contradictions)} contradiction signal(s) detected")
    if under_tested:
        summary_parts.append(f"{len(under_tested)} under-tested dataset signal(s)")
    if missing_metrics:
        summary_parts.append(f"{len(missing_metrics)} missing metric signal(s)")

    return {
        "contradictions": contradictions,
        "under_tested_datasets": under_tested,
        "unexplored_variables": unexplored_variables,
        "missing_metrics": missing_metrics,
        "inconsistent_assumptions": inconsistent_assumptions,
        "summary": ", ".join(summary_parts)
        if summary_parts
        else "No strong gap signal found from current evidence.",
    }


def _trend_projection(candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    year_counts: Counter[int] = Counter()
    keyword_by_year: Dict[int, Counter[str]] = defaultdict(Counter)

    for candidate in candidates:
        year = int(candidate.get("year") or 0)
        if year <= 0:
            continue
        year_counts[year] += 1
        keyword_by_year[year].update(
            _extract_keywords(
                f"{candidate.get('title', '')} {candidate.get('abstract', '')}",
                top_n=10,
            )
        )

    sorted_years = sorted(year_counts.keys())
    series = [{"year": year, "count": int(year_counts[year])} for year in sorted_years]
    forecast = []

    if len(sorted_years) >= 2:
        x_values = list(range(len(sorted_years)))
        y_values = [year_counts[year] for year in sorted_years]
        x_mean = sum(x_values) / len(x_values)
        y_mean = sum(y_values) / len(y_values)
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values))
        denominator = sum((x - x_mean) ** 2 for x in x_values) or 1.0
        slope = numerator / denominator
        intercept = y_mean - slope * x_mean
        last_index = x_values[-1]
        last_year = sorted_years[-1]
        for step in range(1, 4):
            projected = max(0, int(round(intercept + slope * (last_index + step))))
            forecast.append({"year": last_year + step, "predicted_count": projected})

    momentum_scores: Dict[str, float] = {}
    if len(sorted_years) >= 2:
        last_year = sorted_years[-1]
        prev_years = sorted_years[:-1]
        prev_total = max(1, len(prev_years))
        latest = keyword_by_year[last_year]
        historical = Counter()
        for year in prev_years:
            historical.update(keyword_by_year[year])
        for keyword, latest_count in latest.items():
            momentum_scores[keyword] = latest_count - (
                historical.get(keyword, 0) / prev_total
            )

    trend_signals = [
        f"{keyword}: momentum {score:+.2f}"
        for keyword, score in sorted(
            momentum_scores.items(), key=lambda item: item[1], reverse=True
        )[:8]
        if score > 0
    ]

    growth_pct = None
    if len(series) >= 2 and series[0]["count"] > 0:
        growth_pct = round(
            ((series[-1]["count"] - series[0]["count"]) / series[0]["count"]) * 100.0, 2
        )

    return {
        "year_series": series,
        "forecast": forecast,
        "overall_growth_pct": growth_pct,
        "trend_signals": trend_signals,
    }


def _build_knowledge_graph(candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    concept_counts = Counter()
    paper_keywords: Dict[int, List[str]] = {}

    for candidate in candidates:
        idx = int(candidate["index"])
        keywords = _extract_keywords(
            f"{candidate['title']} {candidate['abstract']}", top_n=8
        )
        paper_keywords[idx] = keywords
        concept_counts.update(keywords)

    top_concepts = [word for word, _ in concept_counts.most_common(24)]

    for candidate in candidates:
        idx = int(candidate["index"])
        keywords = paper_keywords.get(idx, [])
        nodes.append(
            {
                "id": f"paper:{idx}",
                "type": "paper",
                "label": candidate["title"],
                "metadata": {
                    "year": candidate.get("year") or None,
                    "source": candidate.get("source"),
                    "url": candidate.get("url") or None,
                    "citation_count": candidate.get("citation_count", 0),
                    "doi": candidate.get("doi") or None,
                    "keywords": keywords,
                },
            }
        )

    for concept in top_concepts:
        nodes.append(
            {
                "id": f"concept:{concept}",
                "type": "concept",
                "label": concept,
                "metadata": {"frequency": int(concept_counts.get(concept, 0))},
            }
        )

    author_counter = Counter()
    for candidate in candidates:
        author_counter.update(candidate.get("authors") or [])
    top_authors = [name for name, _ in author_counter.most_common(30)]
    for author in top_authors:
        nodes.append(
            {
                "id": f"author:{author}",
                "type": "author",
                "label": author,
                "metadata": {"paper_count": int(author_counter.get(author, 0))},
            }
        )

    year_counts = Counter(
        int(candidate.get("year") or 0)
        for candidate in candidates
        if int(candidate.get("year") or 0) > 0
    )
    for year, count in sorted(year_counts.items()):
        nodes.append(
            {
                "id": f"year:{year}",
                "type": "year",
                "label": str(year),
                "metadata": {"count": int(count)},
            }
        )

    for candidate in candidates:
        idx = int(candidate["index"])
        paper_node_id = f"paper:{idx}"
        keywords = set(paper_keywords.get(idx, []))
        for concept in top_concepts:
            if concept in keywords:
                edges.append(
                    {
                        "source": paper_node_id,
                        "target": f"concept:{concept}",
                        "type": "mentions",
                        "relation": "mentions",
                        "weight": 1,
                    }
                )

    author_set = set(top_authors)
    for candidate in candidates:
        idx = int(candidate["index"])
        for author in candidate.get("authors") or []:
            if author in author_set:
                edges.append(
                    {
                        "source": f"author:{author}",
                        "target": f"paper:{idx}",
                        "type": "authored",
                        "relation": "authored",
                        "weight": 1,
                    }
                )

    for candidate in candidates:
        idx = int(candidate["index"])
        year = int(candidate.get("year") or 0)
        if year > 0:
            edges.append(
                {
                    "source": f"year:{year}",
                    "target": f"paper:{idx}",
                    "type": "published",
                    "relation": "published",
                    "weight": 1,
                }
            )

    max_pair_edges = 180
    pair_added = 0
    for i in range(len(candidates)):
        if pair_added >= max_pair_edges:
            break
        for j in range(i + 1, len(candidates)):
            if pair_added >= max_pair_edges:
                break
            a = candidates[i]
            b = candidates[j]
            overlap = len(
                set(paper_keywords.get(int(a["index"]), []))
                & set(paper_keywords.get(int(b["index"]), []))
            )
            if overlap < 2:
                continue
            a_year = int(a.get("year") or 0)
            b_year = int(b.get("year") or 0)
            relation = "semantic_similarity"
            source = f"paper:{a['index']}"
            target = f"paper:{b['index']}"
            if a_year and b_year and a_year != b_year:
                relation = "citation_likely"
                if a_year < b_year:
                    source = f"paper:{b['index']}"
                    target = f"paper:{a['index']}"
            edges.append(
                {
                    "source": source,
                    "target": target,
                    "type": relation,
                    "relation": relation,
                    "weight": overlap,
                }
            )
            pair_added += 1

    collaboration_counts = Counter()
    for candidate in candidates:
        authors = [
            name for name in candidate.get("authors") or [] if name in author_set
        ]
        for i in range(len(authors)):
            for j in range(i + 1, len(authors)):
                collaboration_counts[tuple(sorted((authors[i], authors[j])))] += 1
    for (a_name, b_name), count in collaboration_counts.most_common(80):
        edges.append(
            {
                "source": f"author:{a_name}",
                "target": f"author:{b_name}",
                "type": "collaborates",
                "relation": "collaborates",
                "weight": count,
            }
        )

    degree_map: Counter[str] = Counter()
    for edge in edges:
        degree_map[str(edge.get("source") or "")] += 1
        degree_map[str(edge.get("target") or "")] += 1
    for node in nodes:
        node_id = str(node.get("id") or "")
        metadata = node.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
            node["metadata"] = metadata
        metadata["degree"] = int(degree_map.get(node_id, 0))

    top_concepts_summary = [
        {"label": concept, "frequency": int(freq)}
        for concept, freq in concept_counts.most_common(8)
    ]
    top_authors_summary = [
        {"label": author, "paper_count": int(count)}
        for author, count in author_counter.most_common(8)
    ]
    top_years_summary = [
        {"year": int(year), "count": int(count)}
        for year, count in sorted(
            year_counts.items(), key=lambda item: item[1], reverse=True
        )[:8]
    ]

    return {
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "papers": len([node for node in nodes if node["type"] == "paper"]),
            "concepts": len([node for node in nodes if node["type"] == "concept"]),
            "authors": len([node for node in nodes if node["type"] == "author"]),
            "years": len([node for node in nodes if node["type"] == "year"]),
            "total_edges": len(edges),
            "top_concepts": top_concepts_summary,
            "top_authors": top_authors_summary,
            "top_years": top_years_summary,
        },
    }


def _paper_context_from_db(
    papers: List[Paper], limit: int = 18, abstract_chars: int = 700
) -> str:
    rows = []
    for idx, paper in enumerate(papers[:limit], start=1):
        abstract = (paper.abstract or "").replace("\n", " ").strip()
        if len(abstract) > abstract_chars:
            abstract = abstract[:abstract_chars] + "..."
        link = paper.url or (f"https://doi.org/{paper.doi}" if paper.doi else "N/A")
        rows.append(
            "\n".join(
                [
                    f"Paper {idx} Title: {paper.title}",
                    f"Authors: {paper.authors or 'Unknown'}",
                    f"DOI: {paper.doi or 'N/A'}",
                    f"URL: {link}",
                    f"Abstract: {abstract or 'No abstract available.'}",
                ]
            )
        )
    return "\n\n---\n\n".join(rows)


def _paper_link_from_db(paper: Paper) -> str:
    if paper.url:
        return str(paper.url).strip()
    doi = str(paper.doi or "").strip()
    if doi:
        clean = (
            doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
        )
        if clean:
            return f"https://doi.org/{clean}"
    return ""


def _paper_digest_from_db(papers: List[Paper], limit: int = 16) -> str:
    rows: List[str] = []
    for idx, paper in enumerate(papers[:limit], start=1):
        title = (paper.title or "").strip() or f"Paper {idx}"
        abstract = (paper.abstract or "").replace("\n", " ").strip()
        first_sentence = (
            _extract_sentences(abstract)[0]
            if abstract
            else "No abstract summary available."
        )
        if len(first_sentence) > 220:
            first_sentence = first_sentence[:220] + "..."
        rows.append(
            f"Paper {idx}: {title}\n"
            f"Evidence: {first_sentence}\n"
            f"DOI: {paper.doi or 'N/A'} | URL: {paper.url or (f'https://doi.org/{paper.doi}' if paper.doi else 'N/A')}"
        )
    return "\n\n".join(rows)


def _rank_workspace_papers_for_question(
    papers: List[Paper],
    question: str,
    limit: int = 14,
) -> List[Paper]:
    if not papers:
        return []

    q_tokens = set(_tokenize(question))
    scored: List[Tuple[int, int, int, Paper]] = []
    for paper in papers:
        title_tokens = set(_tokenize(paper.title or ""))
        abstract_tokens = set(_tokenize(paper.abstract or ""))
        title_hits = len(q_tokens & title_tokens)
        abstract_hits = len(q_tokens & abstract_tokens)
        coverage_score = (title_hits * 4) + (abstract_hits * 2)
        metadata_score = int(bool(paper.doi)) + int(bool(paper.url))
        length_score = len((paper.abstract or ""))
        scored.append((coverage_score, metadata_score, length_score, paper))

    scored.sort(key=lambda row: (row[0], row[1], row[2]), reverse=True)
    ranked = [row[3] for row in scored[: max(4, limit)]]
    if not any(row[0] > 0 for row in scored[: max(4, limit)]):
        return papers[: max(4, limit)]
    return ranked


def _extract_chat_actions(analysis: str, max_actions: int) -> List[str]:
    next_actions_block = _extract_markdown_section_block(analysis, "Next Actions")
    action_source = next_actions_block or analysis
    actions = [
        re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", line.strip())
        for line in action_source.splitlines()
        if re.match(r"^\s*(?:[-*]|\d+\.)\s+\S+", line)
    ]
    cleaned = [item for item in actions if item]
    return cleaned[:max_actions]


def _extract_chat_citations(
    text: str, ranked_papers: List[Paper], max_items: int = 10
) -> List[Dict[str, Any]]:
    citations: List[Dict[str, Any]] = []
    seen = set()
    for match in re.finditer(r"\bPaper\s+(\d{1,2})\b", text or "", flags=re.IGNORECASE):
        try:
            idx = int(match.group(1))
        except Exception:
            continue
        if idx < 1 or idx > len(ranked_papers) or idx in seen:
            continue
        seen.add(idx)
        paper = ranked_papers[idx - 1]
        citations.append(
            {
                "label": f"Paper {idx}",
                "paper_id": paper.id,
                "title": paper.title,
                "doi": paper.doi or "",
                "url": _paper_link_from_db(paper),
            }
        )
        if len(citations) >= max_items:
            break
    return citations


def _fallback_chatbot_reply(
    question: str,
    ranked_papers: List[Paper],
    max_actions: int,
) -> Tuple[str, List[str]]:
    if not ranked_papers:
        return (
            (
                "I cannot answer from papers yet because no paper context is selected.\n\n"
                "Add papers to this workspace (or select paper context) and ask again."
            ),
            [
                "Import relevant papers into your workspace first.",
                "Select the papers you want this chat to use.",
                "Retry the same question after papers are selected.",
            ][:max_actions],
        )

    top_lines: List[str] = []
    for idx, paper in enumerate(ranked_papers[:4], start=1):
        abstract = (paper.abstract or "").replace("\n", " ").strip()
        first = (
            _extract_sentences(abstract)[0] if abstract else "No abstract available."
        )
        if len(first) > 260:
            first = first[:260] + "..."
        top_lines.append(f"- Paper {idx}: {paper.title} -> {first}")

    reply = (
        f'AI model is unavailable right now. Here is an evidence snapshot for: "{question}"\n\n'
        "Top relevant papers from your selected context:\n"
        f"{chr(10).join(top_lines)}\n\n"
        "Ask again after AI is available for a deeper synthesis."
    )
    actions = [
        "Ask a narrower follow-up question on one of the listed papers.",
        "Request a comparison between Paper 1 and Paper 2.",
        "Ask for gaps, contradictions, or limitations from the selected set.",
    ]
    return reply, actions[:max_actions]


def _to_db_paper_payload(
    candidate: Dict[str, Any], workspace_id: int
) -> Dict[str, Any]:
    return {
        "title": str(candidate.get("title") or "").strip(),
        "authors": ", ".join(candidate.get("authors") or []),
        "abstract": str(candidate.get("abstract") or "").strip(),
        "url": _paper_primary_link(candidate),
        "doi": str(candidate.get("doi") or "").strip() or None,
        "bibcode": None,
        "workspace_id": workspace_id,
    }


def _import_top_candidates(
    workspace: Workspace, ranked: List[Dict[str, Any]], top_n: int
) -> Dict[str, Any]:
    selected = ranked[:top_n]
    if not selected:
        return {"imported": 0, "skipped": 0, "imported_titles": []}

    repo = _repo_for_db()
    existing = repo.list_papers_for_workspace(workspace.id)
    existing_dois = {
        str((paper.doi or "")).lower().strip() for paper in existing if paper.doi
    }
    existing_titles = {str((paper.title or "")).lower().strip() for paper in existing}

    imported_count = 0
    skipped_count = 0
    imported_titles: List[str] = []

    for candidate in selected:
        doi_key = str(candidate.get("doi") or "").lower().strip()
        title_key = str(candidate.get("title") or "").lower().strip()
        if (doi_key and doi_key in existing_dois) or (
            title_key and title_key in existing_titles
        ):
            skipped_count += 1
            continue

        payload = _to_db_paper_payload(candidate, workspace.id)
        row = repo.create_paper(
            workspace_id=workspace.id,
            title=payload["title"],
            authors=payload["authors"],
            abstract=payload["abstract"],
            url=payload.get("url"),
            pdf_url=payload.get("pdf_url"),
        )
        row.doi = payload.get("doi")
        row.bibcode = payload.get("bibcode")
        repo.save(row)
        index_paper_best_effort(repo=repo, paper=row)
        imported_count += 1
        imported_titles.append(payload["title"])
        if doi_key:
            existing_dois.add(doi_key)
        if title_key:
            existing_titles.add(title_key)
    return {
        "imported": imported_count,
        "skipped": skipped_count,
        "imported_titles": imported_titles,
    }


def _autonomous_fallback(
    goal: str, ranked: List[Dict[str, Any]], trend: Dict[str, Any], gaps: Dict[str, Any]
) -> Dict[str, Any]:
    top = ranked[:10]
    lines = [
        f"Autonomous review for '{goal}' generated from {len(ranked)} ranked papers.",
        "",
        "Evidence-backed paper shortlist:",
    ]
    for row in top:
        lines.append(
            f"- Paper {row['index']}: {row['title']} ({row.get('source')}, {row.get('year') or 'n/a'}, citations: {row.get('citation_count', 0)})"
        )
    lines.extend(
        [
            "",
            "Synthesis:",
            "- Recent work trends toward stronger benchmark performance, but cross-domain robustness is still uneven.",
            "- Many papers optimize isolated metrics; fewer provide comprehensive failure analysis and deployment constraints.",
            "- Prioritize papers with explicit evaluation setup, reproducibility notes, and open artifacts when available.",
        ]
    )

    gap_lines: List[str] = []
    contradictions = gaps.get("contradictions") or []
    missing_metrics = gaps.get("missing_metrics") or []
    under_tested = gaps.get("under_tested_datasets") or []
    if contradictions:
        gap_lines.append(f"- Contradictions: {contradictions[0]}")
    if under_tested:
        gap_lines.append(f"- Under-tested datasets: {', '.join(under_tested[:5])}")
    if missing_metrics:
        gap_lines.append(f"- Missing metrics: {', '.join(missing_metrics[:5])}")
    if not gap_lines:
        gap_lines.append(
            "- No strong structured gap signal found; collect more diverse papers for better contrast."
        )

    return {
        "literature_review": "\n".join(lines),
        "research_gaps": "\n".join(gap_lines),
        "open_problems": [
            "Need stronger cross-benchmark comparability and reproducible baselines.",
            "Limited validation under low-resource and real-world deployment constraints.",
            "Insufficient negative-result and failure-mode reporting in current studies.",
        ],
        "emerging_trends": trend.get("trend_signals")
        or [
            "Recent publication momentum suggests fast-evolving methods and benchmarks."
        ],
    }


def _smart_read_extract(text: str) -> Dict[str, List[str]]:
    sentences = _extract_sentences(text)
    lower_text = text.lower()

    contributions = [
        sentence
        for sentence in sentences
        if any(
            phrase in sentence.lower()
            for phrase in [
                "we propose",
                "we present",
                "our contribution",
                "we introduce",
                "this paper proposes",
            ]
        )
    ][:8]

    datasets = [term for term in sorted(_DATASET_TERMS) if term in lower_text][:12]

    equations = []
    for line in text.splitlines():
        cleaned = line.strip()
        if len(cleaned) < 8:
            continue
        # Heuristic equation detector: equations often include assignment or
        # mathematical operators. Keep broad but avoid false positives.
        if (
            any(symbol in cleaned for symbol in ("=", "->", "<=", ">=", "*", "/", "^"))
            or "lambda" in cleaned.lower()
        ):
            equations.append(cleaned[:220])
    equations = equations[:10]

    limitations = [
        sentence
        for sentence in sentences
        if any(
            term in sentence.lower()
            for term in [
                "limitation",
                "however",
                "challenge",
                "future work",
                "constraint",
                "risk",
            ]
        )
    ][:10]

    key_claims = [
        sentence
        for sentence in sentences
        if any(
            term in sentence.lower()
            for term in [
                "achieve",
                "improve",
                "outperform",
                "result",
                "demonstrate",
                "state-of-the-art",
            ]
        )
    ][:10]

    return {
        "contributions": contributions,
        "datasets": datasets,
        "equations": equations,
        "limitations": limitations,
        "key_claims": key_claims,
    }


def _extract_dataset_from_text(text: str) -> str:
    low = (text or "").lower()
    for term in _DATASET_TERMS:
        if term in low:
            return term
    return "Not explicitly reported"


def _extract_metric_result(text: str) -> str:
    match = re.search(r"(\d{2,3}(?:\.\d+)?\s*%)", text or "")
    if match:
        return match.group(1)
    hits = [metric for metric in _METRIC_TERMS if metric in (text or "").lower()]
    return ", ".join(hits[:2]) if hits else "Not explicitly reported"


def _citation_verdict(score: float) -> str:
    if score >= 0.26:
        return "high"
    if score >= 0.14:
        return "medium"
    return "low"


def _section_lines(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        lines = []
        for raw in value.splitlines():
            cleaned = raw.strip()
            if not cleaned:
                continue
            cleaned = re.sub(r"^[\-\*\d\.\)\s]+", "", cleaned).strip()
            if cleaned:
                lines.append(cleaned)
        return lines
    return []


def _dedupe_keep_order(items: List[str], max_items: Optional[int] = None) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for item in items:
        cleaned = str(item or "").strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(cleaned)
        if max_items and len(ordered) >= max_items:
            break
    return ordered


def _parse_sentence_edit_lines(
    lines: List[str], max_items: int = 8
) -> List[Dict[str, str]]:
    edits: List[Dict[str, str]] = []
    pattern = re.compile(
        r"(?i)original\s*:\s*(.*?)\s*\|\|\s*improved\s*:\s*(.*?)\s*\|\|\s*why\s*:\s*(.*?)\s*(?:\|\|\s*evidence\s*:\s*(.*))?$"
    )
    fallback_pattern = re.compile(r"^\s*(.*?)\s*->\s*(.*?)\s*(?:\((.*?)\))?\s*$")

    for raw in lines:
        line = str(raw or "").strip()
        if not line:
            continue
        match = pattern.match(line)
        if match:
            original = match.group(1).strip()
            improved = match.group(2).strip()
            why = match.group(3).strip()
            evidence = (match.group(4) or "").strip()
            if original and improved:
                edits.append(
                    {
                        "original": original,
                        "improved": improved,
                        "why": why or "Improve clarity and evidence grounding.",
                        "evidence": evidence or "",
                    }
                )
        else:
            fallback = fallback_pattern.match(line)
            if fallback:
                original = fallback.group(1).strip()
                improved = fallback.group(2).strip()
                why = (fallback.group(3) or "").strip()
                if original and improved:
                    edits.append(
                        {
                            "original": original,
                            "improved": improved,
                            "why": why or "Improve clarity and precision.",
                            "evidence": "",
                        }
                    )
        if len(edits) >= max_items:
            break

    return edits


def _quality_score(text: str, expected_sections: int = 3) -> Dict[str, Any]:
    body = (text or "").strip()
    if not body:
        return {
            "score": 0,
            "label": "weak",
            "stats": {
                "chars": 0,
                "headings": 0,
                "bullets": 0,
                "paper_refs": 0,
                "sentences": 0,
                "lexical_diversity": 0.0,
            },
            "notes": ["No output generated."],
        }

    chars = len(body)
    headings = len(re.findall(r"(?m)^\s*#{1,6}\s+\S+", body))
    bullets = len(re.findall(r"(?m)^\s*(?:[-*]|\d+\.)\s+\S+", body))
    paper_refs = len(re.findall(r"\bPaper\s+\d+\b", body, flags=re.IGNORECASE))
    sentences = len(_extract_sentences(body))
    tokens = re.findall(r"[a-zA-Z0-9]{3,}", body.lower())
    lexical_diversity = (len(set(tokens)) / max(1, len(tokens))) if tokens else 0.0
    has_limitations = bool(
        re.search(
            r"\b(limitations?|failure modes?|risks?|threats?)\b",
            body,
            flags=re.IGNORECASE,
        )
    )
    has_next_steps = bool(
        re.search(
            r"\b(next actions?|future work|roadmap|recommendations?)\b",
            body,
            flags=re.IGNORECASE,
        )
    )
    generic_penalty = 14 if "fallback output" in body.lower() else 0

    score = 0
    score += min(30, int(chars / 55))
    score += min(16, headings * 3)
    score += min(14, bullets * 2)
    score += min(16, paper_refs * 3)
    score += min(16, sentences * 2)
    score += min(8, int(lexical_diversity * 20))
    if has_limitations:
        score += 4
    if has_next_steps:
        score += 4
    score -= generic_penalty
    score = max(0, min(100, score))

    if score >= 82:
        label = "excellent"
    elif score >= 67:
        label = "strong"
    elif score >= 46:
        label = "fair"
    else:
        label = "weak"

    notes: List[str] = []
    if headings < max(1, expected_sections - 1):
        notes.append("Add clearer section headings.")
    if bullets < 4:
        notes.append("Add more concrete bullet-point actions.")
    if paper_refs < 2:
        notes.append("Increase evidence grounding with Paper N references.")
    if sentences < 5:
        notes.append(
            "Expand with more complete argument flow across multiple sentences."
        )
    if chars < 520:
        notes.append("Output is brief; expand depth and specifics.")
    if generic_penalty:
        notes.append("Avoid fallback/generic phrasing.")
    if not has_limitations:
        notes.append("Add a limitations or risk paragraph.")
    if not has_next_steps:
        notes.append("Add explicit next actions or future work.")

    return {
        "score": score,
        "label": label,
        "stats": {
            "chars": chars,
            "headings": headings,
            "bullets": bullets,
            "paper_refs": paper_refs,
            "sentences": sentences,
            "lexical_diversity": round(lexical_diversity, 3),
        },
        "notes": _dedupe_keep_order(notes, max_items=8),
    }


@router.post("/autonomous-research")
async def autonomous_research(
    request: AutonomousResearchRequest,
current_user: User = Depends(get_current_user),
):
    goal = request.goal.strip()
    if len(goal) < 4:
        raise HTTPException(status_code=400, detail="Goal is too short.")

    workspace = _workspace_or_default(
        current_user, request.workspace_id, "Autonomous Research Lab"
    )
    candidates, raw_payload = await _search_global_candidates(
        goal, request.max_results, current_user
    )

    if request.year_from:
        candidates = [
            candidate
            for candidate in candidates
            if not candidate.get("year")
            or int(candidate.get("year") or 0) >= request.year_from
        ]

    await _enrich_citation_counts(candidates)
    ranked = _rank_candidates(candidates, goal=goal, year_from=request.year_from)
    clusters = _cluster_themes(ranked[:60], max_clusters=6)
    gap_result = _heuristic_gap_detection(goal, ranked[:50])
    trend_result = _trend_projection(ranked[:70])
    import_result = _import_top_candidates(workspace, ranked, request.import_top_n)
    ai_status = groq_client_status()

    llm_output = _llm_generate(
        system_prompt=(
            "You are an autonomous research strategist for graduate-level literature planning. "
            "Write precise, evidence-grounded analysis with explicit Paper N references. "
            "Do not use vague claims."
        ),
        user_prompt=(
            f"Goal: {goal}\n"
            f"Year filter: {request.year_from or 'none'}\n"
            f"Detected clusters: {clusters}\n"
            f"Gap signals: {gap_result}\n"
            f"Trend signals: {trend_result}\n\n"
            "Return EXACT markdown sections:\n"
            "## Literature Review\n"
            "## Research Gaps\n"
            "## Open Problems\n"
            "## Emerging Trends\n\n"
            "Rules:\n"
            "- Mention at least 8 papers in the review where context supports it.\n"
            "- In Research Gaps, include contradictions, weak assumptions, and missing metrics.\n"
            "- In Open Problems, output 5-8 bullets with clear rationale.\n"
            "- In Emerging Trends, output 5-8 bullets with confidence notes.\n"
            "- Keep all statements tied to provided evidence.\n\n"
            f"Paper context:\n{_candidate_context(ranked, limit=18)}"
        ),
        max_tokens=4600,
        longform=True,
        min_chars=1400,
        expansion_instruction=(
            "Expand the response. Ensure all four required sections are present, increase depth, and "
            "add stronger evidence linking claims to Paper N citations."
        ),
    )

    fallback = _autonomous_fallback(goal, ranked, trend_result, gap_result)
    sections: Dict[str, Any] = {
        "literature_review": str(fallback.get("literature_review") or "").strip(),
        "research_gaps": str(fallback.get("research_gaps") or "").strip(),
        "open_problems": _section_lines(fallback.get("open_problems")),
        "emerging_trends": _section_lines(fallback.get("emerging_trends")),
    }

    if llm_output:
        llm_sections = _extract_named_sections(
            llm_output,
            {
                "literature_review": ["literature review"],
                "research_gaps": ["research gaps", "gap analysis"],
                "open_problems": ["open problems", "open research problems"],
                "emerging_trends": ["emerging trends", "trend outlook"],
            },
        )

        if llm_sections["literature_review"].strip():
            sections["literature_review"] = llm_sections["literature_review"].strip()
        if llm_sections["research_gaps"].strip():
            sections["research_gaps"] = llm_sections["research_gaps"].strip()

        llm_open_problems = _section_lines(llm_sections.get("open_problems"))
        llm_trends = _section_lines(llm_sections.get("emerging_trends"))
        if llm_open_problems:
            sections["open_problems"] = llm_open_problems
        if llm_trends:
            sections["emerging_trends"] = llm_trends

    return {
        "goal": goal,
        "workspace": {"id": workspace.id, "name": workspace.name},
        "search_returned": len(candidates),
        "ranked_count": len(ranked),
        "import_result": import_result,
        "top_papers": ranked[: min(20, request.import_top_n + 8)],
        "clusters": clusters,
        "gap_signals": gap_result,
        "trend_signals": trend_result,
        "literature_review": sections.get("literature_review", "").strip(),
        "research_gaps": sections.get("research_gaps", "").strip(),
        "open_problems": sections.get("open_problems", []),
        "emerging_trends": sections.get("emerging_trends", []),
        "source_status": raw_payload.get("source_status") or {},
        "ai": {
            "enabled": bool(ai_status.get("enabled")),
            "active_model": ai_status.get("active_model"),
            "active_longform_model": ai_status.get("active_longform_model"),
        },
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def _step_error_payload(step: str, exc: Exception) -> Dict[str, Any]:
    detail = str(exc)
    if isinstance(exc, HTTPException):
        if isinstance(exc.detail, str):
            detail = exc.detail
        elif exc.detail is not None:
            detail = str(exc.detail)
    return {"step": step, "error": detail[:400]}


@router.post("/full-pipeline")
async def full_pipeline(
    request: FullPipelineRequest,
current_user: User = Depends(get_current_user),
):
    workspace = _workspace_or_default(
        current_user, request.workspace_id, "Autonomous Research Lab"
    )
    goal = request.goal.strip()
    if len(goal) < 4:
        raise HTTPException(status_code=400, detail="Goal is too short.")

    steps: List[str] = []
    errors: List[Dict[str, Any]] = []
    results: Dict[str, Any] = {}
    planned_steps: List[str] = ["autonomous"]

    try:
        autonomous_result = await autonomous_research(
            AutonomousResearchRequest(
                goal=goal,
                workspace_id=workspace.id,
                year_from=request.year_from,
                max_results=request.max_results,
                import_top_n=request.import_top_n,
            ),
            current_user=current_user,
        )
        results["autonomous"] = autonomous_result
        steps.append("autonomous")
    except Exception as exc:
        errors.append(_step_error_payload("autonomous", exc))

    papers = _load_workspace_papers(workspace, request.paper_ids)
    if not papers:
        papers = _load_workspace_papers(workspace)

    if request.paper_ids:
        active_paper_ids = [paper.id for paper in papers]
    else:
        active_paper_ids = [paper.id for paper in papers[:10]]

    if not active_paper_ids:
        completion_ratio = round(len(steps) / max(len(planned_steps), 1), 3)
        return {
            "workspace": {"id": workspace.id, "name": workspace.name},
            "goal": goal,
            "steps_completed": steps,
            "planned_steps": planned_steps,
            "completion_ratio": completion_ratio,
            "errors": errors,
            "paper_ids_used": [],
            "results": results,
            "message": "Pipeline partially completed, but no workspace papers are available for downstream steps.",
        }

    draft_seed_lines = [
        f"- Paper {idx + 1}: {paper.title}" for idx, paper in enumerate(papers[:8])
    ]
    draft_seed_text = (
        f"## Research Goal\n{goal}\n\n"
        "## Candidate Evidence Papers\n"
        + (
            "\n".join(draft_seed_lines)
            if draft_seed_lines
            else "- Paper evidence will be imported from connected sources."
        )
        + "\n\n## Draft Notes\nPrioritize reproducibility, explicit metrics, and constraints."
    )

    step_calls: List[Tuple[str, Any]] = [
        (
            "gap_detection",
            lambda: gap_detection(
                GapDetectionRequest(
                    workspace_id=workspace.id, paper_ids=active_paper_ids, topic=goal
                ),
                current_user=current_user,
            ),
        ),
        (
            "multi_agent",
            lambda: multi_agent_analysis(
                MultiAgentRequest(
                    workspace_id=workspace.id,
                    paper_ids=active_paper_ids,
                    topic=goal,
                    strict_mode=request.strict_mode,
                ),
                current_user=current_user,
            ),
        ),
        (
            "trend_prediction",
            lambda: trend_prediction(
                TrendPredictionRequest(
                    workspace_id=workspace.id,
                    query=goal,
                    max_results=request.max_results,
                ),
                current_user=current_user,
            ),
        ),
        (
            "experiment_design",
            lambda: experiment_design(
                ExperimentDesignRequest(
                    workspace_id=workspace.id, paper_ids=active_paper_ids, topic=goal
                ),
                current_user=current_user,
            ),
        ),
        (
            "paper_draft",
            lambda: paper_draft(
                PaperDraftRequest(
                    workspace_id=workspace.id,
                    paper_ids=active_paper_ids,
                    topic=goal,
                    target_format="IEEE",
                    citation_style="IEEE",
                ),
                current_user=current_user,
            ),
        ),
        (
            "writing_suggestions",
            lambda: writing_suggestions(
                WritingSuggestionRequest(
                    workspace_id=workspace.id,
                    paper_ids=active_paper_ids[:12],
                    topic=goal,
                    draft_text=draft_seed_text,
                    max_suggestions=10,
                ),
                current_user=current_user,
            ),
        ),
        (
            "chatbot",
            lambda: research_chatbot(
                ResearchChatRequest(
                    workspace_id=workspace.id,
                    paper_ids=active_paper_ids[:12],
                    topic=goal,
                    message="Provide a concise evidence-grounded synthesis, top contradictions, and next experiments.",
                    draft_text=draft_seed_text,
                    response_style="balanced",
                    grounded_only=True,
                    max_actions=8,
                ),
                current_user=current_user,
            ),
        ),
        (
            "knowledge_graph",
            lambda: knowledge_graph(
                workspace_id=workspace.id,
                paper_limit=90,
                current_user=current_user,
            ),
        ),
    ]

    if request.include_advanced:
        step_calls.append(
            (
                "fault_detection",
                lambda: fault_detection(
                    FaultDetectionRequest(
                        workspace_id=workspace.id, paper_id=active_paper_ids[0]
                    ),
                    current_user=current_user,
                ),
            )
        )
        if len(active_paper_ids) >= 2:
            step_calls.append(
                (
                    "compare",
                    lambda: compare_papers(
                        ComparePapersRequest(
                            workspace_id=workspace.id, paper_ids=active_paper_ids[:5]
                        ),
                        current_user=current_user,
                    ),
                )
            )
        step_calls.append(
            (
                "citations",
                lambda: verify_citations(
                    CitationVerifyRequest(
                        workspace_id=workspace.id,
                        draft_text=" ".join(
                            [
                                goal,
                                " ".join(
                                    [
                                        f"Paper {idx + 1}"
                                        for idx in range(min(4, len(active_paper_ids)))
                                    ]
                                ),
                            ]
                        ),
                        paper_ids=active_paper_ids,
                    ),
                    current_user=current_user,
                ),
            )
        )
        step_calls.append(
            (
                "feed",
                lambda: personalized_feed(
                    PersonalizedFeedRequest(
                        workspace_id=workspace.id,
                        max_suggestions=12,
                        force_live=True,
                        refresh_seed=datetime.now(timezone.utc).isoformat(),
                    ),
                    current_user=current_user,
                ),
            )
        )

    planned_steps.extend([step_name for step_name, _ in step_calls])

    for step_name, fn in step_calls:
        try:
            value = fn()
            if asyncio.iscoroutine(value):
                value = await value
            results[step_name] = value
            steps.append(step_name)
        except Exception as exc:
            errors.append(_step_error_payload(step_name, exc))

    completion_ratio = round(len(steps) / max(len(planned_steps), 1), 3)
    return {
        "workspace": {"id": workspace.id, "name": workspace.name},
        "goal": goal,
        "strict_mode": bool(request.strict_mode),
        "include_advanced": bool(request.include_advanced),
        "paper_ids_used": active_paper_ids,
        "steps_completed": steps,
        "planned_steps": planned_steps,
        "completion_ratio": completion_ratio,
        "errors": errors,
        "results": results,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


@router.post("/gap-detection")
def gap_detection(
    request: GapDetectionRequest,
    current_user: User = Depends(get_current_user),
):
    workspace = _workspace_or_default(
        current_user, request.workspace_id, "Autonomous Research Lab"
    )
    papers = _load_workspace_papers(workspace, request.paper_ids)
    if not papers:
        raise HTTPException(
            status_code=400, detail="No papers found in workspace selection."
        )

    topic = (request.topic or workspace.name or "Research topic").strip()
    
    # Try to use Gap Intelligence service if enabled
    try:
        gap_service = get_gap_service()
        gap_result = gap_service.analyze_gaps(topic, papers, use_cache=True)
        
        # Convert to serializable format
        return {
            "workspace": {"id": workspace.id, "name": workspace.name},
            "topic": topic,
            "paper_count": len(papers),
            "gaps_by_category": {
                category: [
                    {
                        "category": g.category,
                        "description": g.description,
                        "confidence": g.confidence,
                        "evidence_count": g.evidence_count,
                        "novelty_potential": g.novelty_potential,
                        "research_impact": g.research_impact,
                        "feasibility": g.feasibility,
                        "recency": g.recency,
                        "supporting_papers": g.supporting_papers,
                        "counter_evidence": g.counter_evidence,
                        "affected_papers": g.affected_papers,
                        "explanation": g.explanation,
                    }
                    for g in gaps
                ]
                for category, gaps in gap_result.gaps_by_category.items()
            },
            "total_gaps": gap_result.total_gaps,
            "top_opportunities": [
                {
                    "category": g.category,
                    "description": g.description,
                    "confidence": g.confidence,
                    "novelty_potential": g.novelty_potential,
                    "research_impact": g.research_impact,
                    "feasibility": g.feasibility,
                    "recency": g.recency,
                    "explanation": g.explanation,
                }
                for g in gap_result.top_opportunities
            ],
            "summary": gap_result.summary,
            "analysis": gap_result.summary,
            "generated_at": gap_result.generated_at.isoformat().replace("+00:00", "Z"),
        }
    except RuntimeError:
        # Fallback to original heuristic gap detection if service disabled
        candidates = [
            {
                "index": i + 1,
                "title": paper.title,
                "abstract": paper.abstract or "",
                "authors": _split_authors(paper.authors),
                "source": "workspace",
                "year": _year_from_text(f"{paper.title} {paper.abstract or ''}"),
                "doi": paper.doi or "",
                "url": paper.url or "",
                "citation_count": 0,
            }
            for i, paper in enumerate(papers)
        ]

        heuristic = _heuristic_gap_detection(topic, candidates)
        llm_text = _llm_generate(
            system_prompt=(
                "You are a PhD-level research gap analyst. Return concise, evidence-grounded findings and explicitly address "
                "contradictions, under-tested datasets, unexplored variables, missing metrics, and assumptions."
            ),
            user_prompt=(
                f"Topic: {topic}\n"
                f"Heuristic gap signals: {heuristic}\n\n"
                "Return markdown sections: Contradictions, Under-tested Datasets, Missing Metrics, "
                "Weak Assumptions, and Priority Next Experiments.\n\n"
                f"Papers:\n{_paper_context_from_db(papers, limit=20)}"
            ),
            max_tokens=2400,
            longform=True,
            min_chars=700,
            expansion_instruction="Expand with more concrete evidence and practical next experiments.",
        )

        return {
            "workspace": {"id": workspace.id, "name": workspace.name},
            "topic": topic,
            "paper_count": len(papers),
            "gaps": heuristic,
            "analysis": llm_text or heuristic["summary"],
        }


@router.post("/evidence-analysis")
def evidence_analysis(
    request: EvidenceAnalysisRequest,
    current_user: User = Depends(get_current_user),
):
    """Analyze a research claim against workspace papers to determine evidence strength."""
    workspace = _workspace_or_default(
        current_user, request.workspace_id, "Autonomous Research Lab"
    )
    papers = _load_workspace_papers(workspace, request.paper_ids)
    if not papers:
        raise HTTPException(
            status_code=400, detail="No papers found in workspace selection."
        )

    try:
        evidence_service = get_evidence_service()
        analysis = evidence_service.analyze_claim(
            claim=request.claim,
            papers=papers,
            use_cache=True
        )
        
        # Convert to serializable format
        return {
            "workspace": {"id": workspace.id, "name": workspace.name},
            "claim": analysis.claim,
            "classification": {
                "supporting_count": len(analysis.classification.supporting_papers),
                "contradicting_count": len(analysis.classification.contradicting_papers),
                "neutral_count": len(analysis.classification.neutral_papers),
                "insufficient_evidence": analysis.classification.insufficient_evidence,
                "supporting_papers": [
                    {"id": p.id, "title": p.title, "authors": p.authors}
                    for p in analysis.classification.supporting_papers
                ],
                "contradicting_papers": [
                    {"id": p.id, "title": p.title, "authors": p.authors}
                    for p in analysis.classification.contradicting_papers
                ],
            },
            "strength": {
                "support_count": analysis.strength.support_count,
                "contradiction_count": analysis.strength.contradiction_count,
                "neutral_count": analysis.strength.neutral_count,
                "source_quality_score": analysis.strength.source_quality_score,
                "recency_score": analysis.strength.recency_score,
                "replication_signal": analysis.strength.replication_signal,
                "overall_strength": analysis.strength.overall_strength,
                "confidence": analysis.strength.confidence,
                "explanation": analysis.strength.explanation,
            },
            "passages": [
                {
                    "paper_id": p.paper_id,
                    "paper_title": p.paper_title,
                    "passage_text": p.passage_text,
                    "relevance_score": p.relevance_score,
                    "evidence_type": p.evidence_type,
                }
                for p in analysis.passages
            ],
            "evidence_type": analysis.evidence_type,
            "generated_at": analysis.generated_at.isoformat().replace("+00:00", "Z"),
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Evidence analysis failed: {str(exc)}")


@router.post("/opportunity-ranking")
def opportunity_ranking(
    request: OpportunityRankingRequest,
    current_user: User = Depends(get_current_user),
):
    """Rank research opportunities from gap intelligence analysis."""
    workspace = _workspace_or_default(
        current_user, request.workspace_id, "Autonomous Research Lab"
    )
    papers = _load_workspace_papers(workspace, request.paper_ids)
    if not papers:
        raise HTTPException(
            status_code=400, detail="No papers found in workspace selection."
        )

    topic = (request.topic or workspace.name or "Research topic").strip()
    
    try:
        # First run gap intelligence to get gaps
        gap_service = get_gap_service()
        gap_result = gap_service.analyze_gaps(topic, papers, use_cache=True)
        
        # Flatten all gaps
        all_gaps: List[StructuredGap] = []
        for category_gaps in gap_result.gaps_by_category.values():
            all_gaps.extend(category_gaps)
        
        # Then rank opportunities
        opportunity_service = get_opportunity_service()
        ranking_result = opportunity_service.rank_opportunities(topic, all_gaps, use_cache=True)
        
        # Convert to serializable format
        return {
            "workspace": {"id": workspace.id, "name": workspace.name},
            "topic": topic,
            "paper_count": len(papers),
            "opportunities": [
                {
                    "gap_id": o.gap_id,
                    "gap_description": o.gap_description,
                    "category": o.category,
                    "evidence_strength": o.evidence_strength,
                    "novelty": o.novelty,
                    "impact": o.impact,
                    "feasibility": o.feasibility,
                    "recency": o.recency,
                    "overall_score": o.overall_score,
                    "rank": o.rank,
                    "explanation": o.explanation,
                    "supporting_papers": o.supporting_papers,
                    "affected_papers": o.affected_papers,
                }
                for o in ranking_result.opportunities
            ],
            "total_opportunities": ranking_result.total_opportunities,
            "top_opportunity": {
                "gap_id": ranking_result.top_opportunity.gap_id,
                "gap_description": ranking_result.top_opportunity.gap_description,
                "category": ranking_result.top_opportunity.category,
                "overall_score": ranking_result.top_opportunity.overall_score,
                "rank": ranking_result.top_opportunity.rank,
                "explanation": ranking_result.top_opportunity.explanation,
            } if ranking_result.top_opportunity else None,
            "comparison_matrix": [
                {
                    "opportunity_1": c.opportunity_1.gap_description,
                    "opportunity_2": c.opportunity_2.gap_description,
                    "comparison": c.comparison,
                    "recommendation": c.recommendation,
                }
                for c in ranking_result.comparison_matrix
            ],
            "summary": ranking_result.summary,
            "generated_at": ranking_result.generated_at.isoformat().replace("+00:00", "Z"),
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Opportunity ranking failed: {str(exc)}")


@router.post("/question-generation")
def question_generation(
    request: QuestionGenerationRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate research questions from gap intelligence analysis."""
    workspace = _workspace_or_default(
        current_user, request.workspace_id, "Autonomous Research Lab"
    )
    papers = _load_workspace_papers(workspace, request.paper_ids)
    if not papers:
        raise HTTPException(
            status_code=400, detail="No papers found in workspace selection."
        )

    topic = (request.topic or workspace.name or "Research topic").strip()
    
    try:
        # First run gap intelligence to get gaps
        gap_service = get_gap_service()
        gap_result = gap_service.analyze_gaps(topic, papers, use_cache=True)
        
        # Flatten all gaps
        all_gaps: List[StructuredGap] = []
        for category_gaps in gap_result.gaps_by_category.values():
            all_gaps.extend(category_gaps)
        
        # Then generate questions
        question_service = get_question_service()
        question_result = question_service.generate_questions(
            topic, all_gaps, request.max_questions, use_cache=True
        )
        
        # Convert to serializable format
        return {
            "workspace": {"id": workspace.id, "name": workspace.name},
            "topic": topic,
            "paper_count": len(papers),
            "questions": [
                {
                    "id": q.id,
                    "question": q.question,
                    "category": q.category,
                    "complexity": q.complexity,
                    "confidence": q.confidence,
                    "novelty": q.novelty,
                    "feasibility": q.feasibility,
                    "impact": q.impact,
                    "source_gap_id": q.source_gap_id,
                    "source_gap_description": q.source_gap_description,
                    "supporting_papers": q.supporting_papers,
                    "rationale": q.rationale,
                }
                for q in question_result.questions
            ],
            "total_questions": question_result.total_questions,
            "top_questions": [
                {
                    "id": q.id,
                    "question": q.question,
                    "category": q.category,
                    "complexity": q.complexity,
                    "novelty": q.novelty,
                    "impact": q.impact,
                    "rationale": q.rationale,
                }
                for q in question_result.top_questions
            ],
            "summary": question_result.summary,
            "generated_at": question_result.generated_at.isoformat().replace("+00:00", "Z"),
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Question generation failed: {str(exc)}")


@router.post("/hypothesis-challenge")
def hypothesis_challenge(
    request: HypothesisChallengeRequest,
    current_user: User = Depends(get_current_user),
):
    """Challenge a research hypothesis with counter-evidence and alternative explanations."""
    workspace = _workspace_or_default(
        current_user, request.workspace_id, "Autonomous Research Lab"
    )
    papers = _load_workspace_papers(workspace, request.paper_ids)
    if not papers:
        raise HTTPException(
            status_code=400, detail="No papers found in workspace selection."
    )
    
    try:
        challenger_service = get_challenger_service()
        challenge_result = challenger_service.challenge_hypothesis(
            hypothesis=request.hypothesis,
            papers=papers,
            use_cache=True
        )
        
        # Convert to serializable format
        return {
            "workspace": {"id": workspace.id, "name": workspace.name},
            "hypothesis": challenge_result.hypothesis,
            "challenges": [
                {
                    "id": c.id,
                    "hypothesis": c.hypothesis,
                    "challenge_type": c.challenge_type,
                    "challenge_text": c.challenge_text,
                    "counter_evidence": c.counter_evidence,
                    "strength": c.strength,
                    "confidence": c.confidence,
                    "supporting_papers": c.supporting_papers,
                    "rationale": c.rationale,
                }
                for c in challenge_result.challenges
            ],
            "total_challenges": challenge_result.total_challenges,
            "strongest_challenge": {
                "id": challenge_result.strongest_challenge.id,
                "challenge_type": challenge_result.strongest_challenge.challenge_type,
                "challenge_text": challenge_result.strongest_challenge.challenge_text,
                "strength": challenge_result.strongest_challenge.strength,
                "confidence": challenge_result.strongest_challenge.confidence,
                "rationale": challenge_result.strongest_challenge.rationale,
            } if challenge_result.strongest_challenge else None,
            "overall_vulnerability": challenge_result.overall_vulnerability,
            "summary": challenge_result.summary,
            "generated_at": challenge_result.generated_at.isoformat().replace("+00:00", "Z"),
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Hypothesis challenge failed: {str(exc)}")


@router.post("/citation-verification")
def citation_verification(
    request: CitationVerificationRequest,
    current_user: User = Depends(get_current_user),
):
    """Verify citations for workspace papers."""
    workspace = _workspace_or_default(
        current_user, request.workspace_id, "Autonomous Research Lab"
    )
    papers = _load_workspace_papers(workspace, request.paper_ids)
    if not papers:
        raise HTTPException(
            status_code=400, detail="No papers found in workspace selection."
    )
    
    try:
        citation_service = get_citation_service()
        verification_result = citation_service.verify_citations(papers, use_cache=True)
        
        # Convert to serializable format
        return {
            "workspace": {"id": workspace.id, "name": workspace.name},
            "total_papers": verification_result.total_papers,
            "verifications": [
                {
                    "paper_id": v.paper_id,
                    "paper_title": v.paper_title,
                    "source": v.source,
                    "doi": v.doi,
                    "url": v.url,
                    "quality_score": v.quality_score,
                    "accessibility_score": v.accessibility_score,
                    "consistency_score": v.consistency_score,
                    "overall_confidence": v.overall_confidence,
                    "issues": v.issues,
                    "recommendations": v.recommendations,
                }
                for v in verification_result.verifications
            ],
            "average_quality": verification_result.average_quality,
            "average_accessibility": verification_result.average_accessibility,
            "average_consistency": verification_result.average_consistency,
            "overall_confidence": verification_result.overall_confidence,
            "critical_issues": verification_result.critical_issues,
            "summary": verification_result.summary,
            "generated_at": verification_result.generated_at.isoformat().replace("+00:00", "Z"),
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Citation verification failed: {str(exc)}")


@router.post("/knowledge-graph-enhancement")
def knowledge_graph_enhancement(
    request: KnowledgeGraphEnhancementRequest,
    current_user: User = Depends(get_current_user),
):
    """Enhance knowledge graph with intelligence layers."""
    workspace = _workspace_or_default(
        current_user, request.workspace_id, "Autonomous Research Lab"
    )
    papers = _load_workspace_papers(workspace, request.paper_ids)
    if not papers:
        raise HTTPException(
            status_code=400, detail="No papers found in workspace selection."
        )

    topic = (request.topic or workspace.name or "Research topic").strip()
    layers = request.layers or ["gap", "evidence", "opportunity", "citation"]
    
    try:
        # First build base knowledge graph
        candidates = [
            {
                "index": i + 1,
                "title": paper.title,
                "abstract": paper.abstract or "",
                "authors": _split_authors(paper.authors),
                "source": "workspace",
                "year": _year_from_text(f"{paper.title} {paper.abstract or ''}"),
                "doi": paper.doi or "",
                "url": paper.url or "",
                "citation_count": 0,
            }
            for i, paper in enumerate(papers)
        ]
        
        base_graph = _build_knowledge_graph(candidates)
        base_graph["workspace"] = {"id": workspace.id, "name": workspace.name}
        
        # Then enhance with intelligence layers
        graph_service = get_graph_enhancement_service()
        enhanced_result = graph_service.enhance_knowledge_graph(
            base_graph=base_graph,
            papers=papers,
            topic=topic,
            layers=layers,
            use_cache=True
        )
        
        # Convert to serializable format
        return {
            "workspace": {"id": workspace.id, "name": workspace.name},
            "topic": topic,
            "paper_count": len(papers),
            "base_graph": enhanced_result.base_graph,
            "intelligence_layers": [
                {
                    "layer_type": layer.layer_type,
                    "enabled": layer.enabled,
                    "data": layer.data,
                    "summary": layer.summary,
                }
                for layer in enhanced_result.intelligence_layers
            ],
            "total_layers": enhanced_result.total_layers,
            "enhanced_nodes": enhanced_result.enhanced_nodes,
            "enhanced_edges": enhanced_result.enhanced_edges,
            "summary": enhanced_result.summary,
            "generated_at": enhanced_result.generated_at.isoformat().replace("+00:00", "Z"),
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Knowledge graph enhancement failed: {str(exc)}")


@router.get("/knowledge-graph")
def knowledge_graph(
    workspace_id: int,
    paper_limit: int = 60,
current_user: User = Depends(get_current_user),
):
    workspace = _workspace_or_default(
        current_user, workspace_id, "Autonomous Research Lab"
    )
    papers = _load_workspace_papers(workspace)[: max(10, min(paper_limit, 120))]
    if not papers:
        raise HTTPException(
            status_code=400, detail="No papers available to build knowledge graph."
        )

    candidates = [
        {
            "index": i + 1,
            "title": paper.title,
            "abstract": paper.abstract or "",
            "authors": _split_authors(paper.authors),
            "source": "workspace",
            "year": _year_from_text(f"{paper.title} {paper.abstract or ''}"),
            "doi": paper.doi or "",
            "url": paper.url or "",
            "citation_count": 0,
        }
        for i, paper in enumerate(papers)
    ]

    graph = _build_knowledge_graph(candidates)
    graph["workspace"] = {"id": workspace.id, "name": workspace.name}
    return graph


@router.post("/multi-agent-analysis")
def multi_agent_analysis(
    request: MultiAgentRequest,
current_user: User = Depends(get_current_user),
):
    workspace = _workspace_or_default(
        current_user, request.workspace_id, "Autonomous Research Lab"
    )
    papers = _load_workspace_papers(workspace, request.paper_ids)
    if not papers:
        raise HTTPException(
            status_code=400, detail="No papers found in workspace selection."
        )

    topic = (request.topic or workspace.name or "Research topic").strip()
    context = _paper_digest_from_db(papers, limit=18)
    strict_mode = bool(request.strict_mode)
    strict_label = "STRICT" if strict_mode else "STANDARD"
    agent_prompts = {
        "literature_agent": (
            "Output sections: Core Themes, Strongest Evidence, Landmark Papers. "
            "Use Paper N references in every section."
        ),
        "insight_agent": (
            "Output sections: High-Value Insights, Contradictions, Confidence Notes. "
            "Include confidence labels (High/Medium/Low)."
        ),
        "gap_agent": (
            "Output sections: Missing Areas, Under-tested Variables, Weak Assumptions, Metric Gaps."
        ),
        "methodology_agent": (
            "Output sections: Suggested Datasets, Metrics, Baselines, Ablation Plan, Risk Controls."
        ),
        "writing_agent": (
            "Output sections: Abstract Draft, Introduction Draft, Methodology Draft. "
            "Keep each section publication-ready and concise."
        ),
        "reviewer_agent": (
            "Output sections: Evidence Quality Risks, Reproducibility Risks, Publication Readiness, Fix Plan."
        ),
    }

    outputs: Dict[str, str] = {}
    agent_quality: Dict[str, Dict[str, Any]] = {}
    agent_max_tokens = 3000 if strict_mode else 2200
    agent_min_chars = 900 if strict_mode else 520
    for agent, prompt in agent_prompts.items():
        text = _llm_generate(
            system_prompt=(
                "You are a specialized research AI agent. Produce specific and actionable output. "
                "Avoid generic advice and tie claims to Paper N evidence."
            ),
            user_prompt=(
                f"Mode: {strict_label}\n"
                f"Topic: {topic}\n"
                f"Agent task: {prompt}\n\n"
                "Rules: use markdown headings, include concrete bullets, and cite Paper N references.\n"
                f"- Expected depth: {'8+' if strict_mode else '5+'} actionable bullets.\n"
                f"- Minimum evidence references: {'6' if strict_mode else '3'} Paper N citations.\n\n"
                f"Paper digest:\n{context}"
            ),
            max_tokens=agent_max_tokens,
            longform=True,
            min_chars=agent_min_chars,
            expansion_instruction=(
                "Expand with stronger depth and explicit evidence. "
                "Ensure sectioned output and a concrete action list with Paper N references."
            ),
        )
        outputs[agent] = text or (
            f"{agent.replace('_', ' ').title()} fallback output for '{topic}'. "
            "AI service unavailable, using heuristic summary from available workspace papers."
        )
        agent_quality[agent] = _quality_score(outputs[agent], expected_sections=4)

    executive = _llm_generate(
        system_prompt="You are the orchestration agent. Merge specialized agent outputs into one prioritized execution plan.",
        user_prompt=(
            f"Mode: {strict_label}\n"
            f"Topic: {topic}\n"
            f"Agent outputs: {outputs}\n\n"
            "Return sections: Unified Strategy, 30-Day Execution Plan, Key Risks, Publication Path, and Decision Gates.\n"
            f"- In {strict_label} mode, include measurable milestones and decision criteria."
        ),
        max_tokens=3600 if strict_mode else 2800,
        longform=True,
        min_chars=1300 if strict_mode else 900,
        expansion_instruction="Expand with more specific milestones, dependencies, owners, and risk mitigation actions.",
    )

    orchestrated_plan = (
        executive
        or "Orchestration fallback: combine agent outputs into a single prioritized execution plan."
    )
    plan_quality = _quality_score(orchestrated_plan, expected_sections=5)
    avg_agent_score = 0
    if agent_quality:
        avg_agent_score = round(
            sum(item.get("score", 0) for item in agent_quality.values())
            / len(agent_quality),
            1,
        )

    return {
        "workspace": {"id": workspace.id, "name": workspace.name},
        "topic": topic,
        "strict_mode": strict_mode,
        "agents": outputs,
        "agent_quality": agent_quality,
        "orchestrated_plan": orchestrated_plan,
        "orchestrated_plan_quality": plan_quality,
        "overall_quality": {
            "avg_agent_score": avg_agent_score,
            "orchestrated_score": plan_quality.get("score", 0),
            "grade": (
                "excellent"
                if avg_agent_score >= 85
                else "strong"
                if avg_agent_score >= 70
                else "fair"
                if avg_agent_score >= 50
                else "weak"
            ),
        },
    }


@router.post("/trend-prediction")
async def trend_prediction(
    request: TrendPredictionRequest,
current_user: User = Depends(get_current_user),
):
    candidates: List[Dict[str, Any]] = []
    source = "workspace"

    if request.query:
        source = "global_search"
        remote_candidates, _payload = await _search_global_candidates(
            request.query.strip(), request.max_results, current_user
        )
        await _enrich_citation_counts(remote_candidates)
        candidates = remote_candidates
    else:
        workspace = _workspace_or_default(
            current_user, request.workspace_id, "Autonomous Research Lab"
        )
        papers = _load_workspace_papers(workspace)
        candidates = [
            {
                "index": i + 1,
                "title": paper.title,
                "abstract": paper.abstract or "",
                "authors": _split_authors(paper.authors),
                "source": "workspace",
                "year": _year_from_text(f"{paper.title} {paper.abstract or ''}"),
                "doi": paper.doi or "",
                "url": paper.url or "",
                "citation_count": 0,
            }
            for i, paper in enumerate(papers)
        ]

    if not candidates:
        raise HTTPException(
            status_code=400, detail="No papers available for trend prediction."
        )

    trends = _trend_projection(candidates)
    llm_text = _llm_generate(
        system_prompt="You are a research trend forecaster. Give grounded, conservative forecasts and include uncertainty language.",
        user_prompt=(
            f"Trend data: {trends}\n"
            "Provide markdown sections: Summary, Top Momentum Areas, 3-Year Forecast, and Practical Implications.\n\n"
            f"Paper context:\n{_candidate_context(candidates, limit=16)}"
        ),
        max_tokens=1600,
        longform=False,
        min_chars=420,
        expansion_instruction="Expand each section with concrete interpretation of the trend series.",
    )

    return {
        "source": source,
        "trend_data": trends,
        "forecast_narrative": llm_text
        or "Trend projection computed from publication volume and keyword momentum.",
    }


@router.post("/experiment-design")
def experiment_design(
    request: ExperimentDesignRequest,
current_user: User = Depends(get_current_user),
):
    workspace = _workspace_or_default(
        current_user, request.workspace_id, "Autonomous Research Lab"
    )
    papers = _load_workspace_papers(workspace, request.paper_ids)
    if not papers:
        raise HTTPException(
            status_code=400, detail="No papers found for experiment design."
        )

    topic = request.topic.strip()
    llm_text = _llm_generate(
        system_prompt=(
            "You are a principal ML researcher. Create practical experiment plans with datasets, metrics, baselines, "
            "evaluation protocol, implementation stack, and compute requirements."
        ),
        user_prompt=(
            f"Topic: {topic}\n"
            f"Hypothesis: {request.hypothesis or 'Not provided'}\n"
            "Return sections: Datasets, Metrics, Baselines, Evaluation Flow, Tool Stack, Hardware Requirements, Risk Controls.\n\n"
            f"Paper context:\n{_paper_context_from_db(papers, limit=18)}"
        ),
        max_tokens=2400,
        longform=True,
        min_chars=850,
        expansion_instruction="Expand with stronger ablation design, validation protocol, and failure-mode checks.",
    )

    if not llm_text:
        llm_text = (
            f"Experiment plan for topic: {topic}\n\n"
            "Datasets:\n- Use one in-domain and one out-of-domain benchmark.\n\n"
            "Metrics:\n- Primary: accuracy/F1 or RMSE/MAE.\n- Secondary: latency and robustness.\n\n"
            "Baselines:\n- Classical baseline\n- Lightweight neural baseline\n- Current SOTA variant\n\n"
            "Evaluation flow:\n- Leakage checks\n- Hyperparameter sweeps\n- Ablation study\n- Stress testing\n\n"
            "Tool stack:\n- PyTorch + Lightning, scikit-learn, Weights & Biases\n\n"
            "Hardware:\n- 1x 24GB+ GPU for prototyping, multi-GPU for scale tests\n"
        )

    return {
        "workspace": {"id": workspace.id, "name": workspace.name},
        "topic": topic,
        "experiment_design": llm_text,
    }


@router.post("/paper-draft")
def paper_draft(
    request: PaperDraftRequest,
current_user: User = Depends(get_current_user),
):
    workspace = _workspace_or_default(
        current_user, request.workspace_id, "Autonomous Research Lab"
    )
    papers = _load_workspace_papers(workspace, request.paper_ids)
    if not papers:
        raise HTTPException(status_code=400, detail="No papers found for drafting.")

    topic = request.topic.strip()
    target_format = request.target_format.strip() or "IEEE"
    citation_style = request.citation_style.strip() or "IEEE"

    llm_text = _llm_generate(
        system_prompt="You are an academic writing assistant for journal-quality drafts.",
        user_prompt=(
            f"Topic: {topic}\n"
            f"Target format: {target_format}\n"
            f"Citation style: {citation_style}\n"
            "Return sections in order: Abstract, Introduction, Related Work, Methodology Draft, Results Plan, Conclusion, References.\n"
            "Use paper labels like Paper 1, Paper 2 in references.\n\n"
            f"Context:\n{_paper_context_from_db(papers, limit=20)}"
        ),
        max_tokens=3600,
        longform=True,
        min_chars=1300,
        expansion_instruction="Increase technical depth and improve citation grounding with Paper N references.",
    )

    if not llm_text:
        llm_text = (
            f"# Draft Manuscript ({target_format})\n\n"
            f"## Abstract\nThis manuscript addresses {topic} with an evidence-driven methodology and reproducibility focus.\n\n"
            "## Introduction\nThe problem space is rapidly evolving with strong demand for robust and deployable solutions.\n\n"
            "## Related Work\nPrior works highlight strong benchmark performance but mixed transferability and incomplete robustness checks.\n\n"
            "## Methodology Draft\nWe propose a comparative pipeline with controlled ablations, standardized metrics, and robustness stress tests.\n\n"
            "## Results Plan\nReport primary metrics, confidence intervals, failure cases, and domain-shift behavior.\n\n"
            "## Conclusion\nThe paper should emphasize reproducibility, practical impact, and unresolved gaps.\n\n"
            "## References\n- Paper 1\n- Paper 2\n"
        )

    return {
        "workspace": {"id": workspace.id, "name": workspace.name},
        "topic": topic,
        "target_format": target_format,
        "citation_style": citation_style,
        "draft": llm_text,
    }


@router.post("/chatbot")
@router.post("/writing-chat")
def research_chatbot(
    request: ResearchChatRequest,
current_user: User = Depends(get_current_user),
):
    workspace = _workspace_or_default(
        current_user, request.workspace_id, "Autonomous Research Lab"
    )
    papers = _load_workspace_papers(workspace, request.paper_ids)

    message = request.message.strip()
    if len(message) < 2:
        raise HTTPException(status_code=400, detail="Message is too short.")

    context_text = (
        (request.context_text or "").strip() or (request.draft_text or "").strip()
    )[:18000]
    topic = (request.topic or workspace.name or "Workspace research context").strip()
    quality = _quality_score(f"{context_text}\n{message}", expected_sections=3)

    style = (request.response_style or "balanced").strip().lower()
    if style not in {"concise", "balanced", "deep"}:
        style = "balanced"

    turns = request.conversation or []
    sanitized_turns: List[Tuple[str, str]] = []
    for turn in turns[-10:]:
        role = str(turn.role or "").strip().lower()
        content = str(turn.content or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        sanitized_turns.append((role, content[:2600]))

    chat_history_block = "\n".join(
        [f"{role.title()}: {content}" for role, content in sanitized_turns]
    )[:14000]
    ranked_papers = _rank_workspace_papers_for_question(papers, message, limit=14)
    context_block = (
        _paper_context_from_db(ranked_papers, limit=14, abstract_chars=760)
        if ranked_papers
        else "No workspace paper context available."
    )

    style_instruction = {
        "concise": "Keep answers compact with direct bullets.",
        "balanced": "Provide a clear answer with moderate detail.",
        "deep": "Provide deep technical detail with explicit assumptions.",
    }[style]

    grounding_instruction = (
        "Ground every non-trivial claim in Paper N evidence from the selected context. "
        'If evidence is missing, explicitly say: "Insufficient evidence in selected papers."'
        if request.grounded_only
        else "Prioritize Paper N evidence first, then add cautious general reasoning if needed."
    )

    llm_text = _llm_generate(
        system_prompt=(
            "You are Soyog AI Chatbot, a full-spectrum research assistant. "
            "Behave like a conversational AI for any research question, while staying evidence-first."
        ),
        user_prompt=(
            f"Workspace: {workspace.name}\n"
            f"Topic: {topic}\n"
            f"Response style: {style}\n"
            f"Grounded mode: {'strict' if request.grounded_only else 'hybrid'}\n"
            f"Context quality score: {quality}\n\n"
            f"Additional user context (optional):\n{context_text or 'None'}\n\n"
            f"Recent conversation:\n{chat_history_block or 'None'}\n\n"
            f"User message: {message}\n\n"
            f"Selected paper context:\n{context_block}\n\n"
            f"Rules:\n- {grounding_instruction}\n- {style_instruction}\n"
            "- Keep output readable and actionable.\n"
            "Return markdown with sections:\n"
            "## Direct Answer\n"
            "## Evidence From Papers\n"
            "## Critical Caveats\n"
            "## Next Actions\n"
            "## Follow-up Questions\n"
        ),
        max_tokens=2900 if style == "deep" else 2350 if style == "balanced" else 1900,
        longform=False,
        min_chars=380 if style == "deep" else 300,
        expansion_instruction="Increase evidence quality with explicit Paper N references and stronger reasoning.",
        required_headings=["Direct Answer", "Evidence From Papers", "Next Actions"],
    )

    if not llm_text:
        fallback_reply, fallback_actions = _fallback_chatbot_reply(
            message, ranked_papers, request.max_actions
        )
        return {
            "workspace": {"id": workspace.id, "name": workspace.name},
            "topic": topic,
            "reply": fallback_reply,
            "actions": fallback_actions,
            "draft_quality": quality,
            "revised_excerpt": "",
            "analysis": fallback_reply,
            "citations": _extract_chat_citations(fallback_reply, ranked_papers),
            "papers_used": len(ranked_papers),
            "mode": "fallback",
            "response_style": style,
            "confidence": 0.24,
            "suggested_queries": [],
            "evidence_map": [],
        }

    analysis = llm_text.strip()
    direct_answer = (
        _extract_markdown_section_block(analysis, "Direct Answer")
        or _extract_markdown_section_block(analysis, "Answer")
        or _extract_markdown_section_block(analysis, "Response")
        or analysis
    )
    evidence_block = _extract_markdown_section_block(analysis, "Evidence From Papers")
    caveats_block = _extract_markdown_section_block(analysis, "Critical Caveats")
    next_actions_block = _extract_markdown_section_block(analysis, "Next Actions")
    follow_ups = _extract_markdown_section_block(analysis, "Follow-up Questions")
    actions = _extract_chat_actions(analysis, request.max_actions)

    merged_reply_parts = [direct_answer.strip()]
    if evidence_block:
        merged_reply_parts.append(f"Evidence from papers:\n{evidence_block.strip()}")
    if caveats_block:
        merged_reply_parts.append(f"Critical caveats:\n{caveats_block.strip()}")
    elif request.grounded_only:
        merged_reply_parts.append(
            "Critical caveats:\n- Insufficient evidence in selected papers for parts of the query."
        )
    if follow_ups:
        merged_reply_parts.append(
            f"Suggested follow-up questions:\n{follow_ups.strip()}"
        )
    reply = "\n\n".join([part for part in merged_reply_parts if part]).strip()

    citations = _extract_chat_citations(analysis, ranked_papers)
    evidence_map = _section_lines(evidence_block)
    suggested_queries = _section_lines(follow_ups)
    paper_signal = min(1.0, len(citations) / max(1, min(len(ranked_papers), 6)))
    quality_signal = min(1.0, max(0.0, float(quality.get("score", 0)) / 100.0))
    confidence = round(
        min(0.98, 0.34 + (paper_signal * 0.44) + (quality_signal * 0.22)), 2
    )

    return {
        "workspace": {"id": workspace.id, "name": workspace.name},
        "topic": topic,
        "reply": reply,
        "actions": actions,
        "next_actions_block": next_actions_block,
        "draft_quality": quality,
        "revised_excerpt": "",
        "analysis": analysis,
        "citations": citations,
        "evidence_map": evidence_map[:12],
        "suggested_queries": suggested_queries[:10],
        "confidence": confidence,
        "papers_used": len(ranked_papers),
        "mode": "chatbot",
        "response_style": style,
    }


@router.post("/writing-suggestions")
def writing_suggestions(
    request: WritingSuggestionRequest,
current_user: User = Depends(get_current_user),
):
    workspace = _workspace_or_default(
        current_user, request.workspace_id, "Autonomous Research Lab"
    )
    papers = _load_workspace_papers(workspace, request.paper_ids)

    draft = request.draft_text.strip()
    topic = (request.topic or workspace.name or "Research topic").strip()
    refs = re.findall(r"\bPaper\s+\d+\b", draft, flags=re.IGNORECASE)
    has_headings = bool(re.search(r"(?m)^\s*#{1,6}\s+\S+", draft))
    draft_sentences = _extract_sentences(draft)
    ranked_papers = _rank_workspace_papers_for_question(
        papers, f"{topic}\n{draft[:2400]}", limit=12
    )
    context_papers = ranked_papers or papers
    paper_context = _paper_context_from_db(context_papers, limit=12)

    paper_brief_lines: List[str] = []
    for idx, paper in enumerate(context_papers[:8], start=1):
        paper_brief_lines.append(
            f"Paper {idx}: {paper.title} | Authors: {(paper.authors or 'Unknown')[:100]} | Year: {_year_from_text(paper.title + ' ' + (paper.abstract or '')) or 'N/A'}"
        )

    heuristic_suggestions: List[str] = []
    if len(draft) < 380:
        heuristic_suggestions.append(
            "Expand motivation and prior-work positioning before method details."
        )
    if len(draft_sentences) < 3:
        heuristic_suggestions.append(
            "Build a stronger narrative arc: context -> method -> evidence -> limitation -> next step."
        )
    if not has_headings:
        heuristic_suggestions.append(
            "Add explicit section headings (Introduction, Related Work, Method, Evaluation, Conclusion)."
        )
    if len(refs) < 2:
        heuristic_suggestions.append(
            "Ground key claims with explicit Paper N references from workspace evidence."
        )
    if "limitation" not in draft.lower():
        heuristic_suggestions.append(
            "Add a limitations paragraph with at least two concrete failure modes."
        )
    if not re.search(r"\b\d+(?:\.\d+)?\s*%|\b\d+(?:\.\d+)?\b", draft):
        heuristic_suggestions.append(
            "Add at least one concrete quantitative result (metric or percentage) with Paper references."
        )
    if not re.search(
        r"\b(dataset|benchmark|evaluation|ablation|baseline)\b",
        draft,
        flags=re.IGNORECASE,
    ):
        heuristic_suggestions.append(
            "State the dataset, baseline, and evaluation protocol explicitly for reproducibility."
        )
    heuristic_suggestions = _dedupe_keep_order(heuristic_suggestions, max_items=10)

    draft_quality = _quality_score(draft, expected_sections=5)

    llm_text = _llm_generate(
        system_prompt=(
            "You are a senior academic writing editor. Return dense, practical, and evidence-grounded revision guidance. "
            "Use Paper N labels exactly, avoid generic statements, and improve technical precision."
        ),
        user_prompt=(
            f"Topic: {topic}\n"
            f"Current quality snapshot: {json.dumps(draft_quality)}\n"
            f"Draft text:\n{draft[:14000]}\n\n"
            f"Workspace evidence context:\n{paper_context}\n\n"
            f"Prioritized paper brief:\n{chr(10).join(paper_brief_lines) or 'No papers selected'}\n\n"
            f"Heuristic suggestions:\n{chr(10).join('- ' + item for item in heuristic_suggestions)}\n\n"
            "Return markdown with sections:\n"
            "## Priority Revisions\n"
            "## Evidence Mapping\n"
            "## Sentence-Level Edits\n"
            "## Rewrite Excerpt\n"
            "## Revision Checklist\n\n"
            "Rules:\n"
            "- Priority Revisions: 8 to 12 bullet points.\n"
            '- Evidence Mapping: 4 to 8 bullets in the format "Claim -> Paper N (why)".\n'
            "- Sentence-Level Edits: 3 to 6 bullets using this exact format:\n"
            "  Original: <text> || Improved: <text> || Why: <reason> || Evidence: Paper N\n"
            "- Rewrite Excerpt: produce a clean improved paragraph (180-320 words).\n"
            "- Revision Checklist: 6 to 10 concise checkboxes as bullets.\n"
            "- Keep every item actionable and evidence-aware."
        ),
        max_tokens=2800,
        longform=False,
        min_chars=850,
        expansion_instruction="Increase specificity with sentence-level edits, stronger evidence mapping, and a cleaner rewrite excerpt.",
        required_headings=[
            "Priority Revisions",
            "Sentence-Level Edits",
            "Rewrite Excerpt",
        ],
    )

    combined = (llm_text or "").strip()
    if not combined:
        first_sentence = (
            draft_sentences[0]
            if draft_sentences
            else "This draft introduces the core research problem."
        )
        improved_first_sentence = (
            re.sub(r"\s+", " ", first_sentence).strip().rstrip(".")
            + " while grounding the claim with measurable evidence from Paper 1 and Paper 2."
        )
        second_sentence = (
            draft_sentences[1]
            if len(draft_sentences) > 1
            else "The evaluation setup should define datasets, baselines, and reproducibility constraints explicitly."
        )
        improved_second_sentence = (
            re.sub(r"\s+", " ", second_sentence).strip().rstrip(".")
            + " Include benchmark details and uncertainty limits with direct Paper citations."
        )
        combined = (
            "## Priority Revisions\n"
            + "\n".join(f"- {item}" for item in heuristic_suggestions[:6])
            + "\n\n## Evidence Mapping\n"
            "- Core claim robustness -> Paper 1 (reported gains under constrained setting)\n"
            "- Baseline comparison quality -> Paper 2 (evaluation protocol and trade-offs)\n"
            "- Generalization caveats -> Paper 3 (domain transfer limitations)\n"
            "\n## Sentence-Level Edits\n"
            f"- Original: {first_sentence} || Improved: {improved_first_sentence} || Why: Adds measurable evidence framing. || Evidence: Paper 1\n"
            f"- Original: {second_sentence} || Improved: {improved_second_sentence} || Why: Clarifies reproducibility and benchmarking criteria. || Evidence: Paper 2\n"
            "\n## Rewrite Excerpt\n"
            "This study addresses the challenge of robust graph anomaly detection under constrained deployment settings. "
            "Rather than claiming broad gains without context, we position the contribution against established baselines "
            "and explicitly define the operating regime, evaluation protocol, and expected failure boundaries. "
            "Evidence from Paper 1 indicates that constrained-resource robustness improves when graph structure priors are retained, "
            "while Paper 2 highlights that benchmark sensitivity can hide performance variance across realistic data shifts. "
            "Accordingly, the manuscript should align claims to reported metrics, clarify dataset assumptions, and state limitations "
            "on transferability so that readers can evaluate practical relevance and reproducibility.\n"
            "\n## Revision Checklist\n"
            "- Add explicit section headings and objective statement.\n"
            "- Tie each major claim to at least one Paper N reference.\n"
            "- Report baseline, dataset, and metric for every quantitative statement.\n"
            "- Add limitations with at least two concrete failure modes.\n"
            "- Include reproducibility details (splits, seeds, compute constraints).\n"
            "- End with prioritized next experiments.\n"
        )

    priority_block = _extract_markdown_section_block(combined, "Priority Revisions")
    evidence_block = _extract_markdown_section_block(combined, "Evidence Mapping")
    sentence_edits_block = _extract_markdown_section_block(
        combined, "Sentence-Level Edits"
    )
    checklist_block = _extract_markdown_section_block(combined, "Revision Checklist")
    rewrite_excerpt = _extract_markdown_section_block(
        combined, "Rewrite Excerpt"
    ) or _extract_markdown_section_block(combined, "Suggested Rewrite")

    priority_lines = _section_lines(priority_block or combined)
    evidence_map = _dedupe_keep_order(_section_lines(evidence_block), max_items=10)
    revision_checklist = _dedupe_keep_order(
        _section_lines(checklist_block), max_items=12
    )
    sentence_edits = _parse_sentence_edit_lines(
        _section_lines(sentence_edits_block), max_items=8
    )

    if not sentence_edits and draft_sentences:
        sentence_edits = [
            {
                "original": draft_sentences[0],
                "improved": draft_sentences[0].rstrip(".")
                + " with explicit benchmark evidence from Paper 1.",
                "why": "Makes the claim testable and evidence-linked.",
                "evidence": "Paper 1",
            }
        ]

    suggestions = _dedupe_keep_order(
        priority_lines + heuristic_suggestions + revision_checklist,
        max_items=request.max_suggestions,
    )

    suggestion_groups: Dict[str, List[str]] = {
        "structure": [],
        "evidence": [],
        "clarity": [],
        "risk": [],
    }
    for suggestion in suggestions:
        lower = suggestion.lower()
        if any(
            term in lower
            for term in ["section", "heading", "flow", "structure", "organization"]
        ):
            suggestion_groups["structure"].append(suggestion)
        elif any(
            term in lower
            for term in [
                "paper",
                "evidence",
                "citation",
                "reference",
                "dataset",
                "metric",
            ]
        ):
            suggestion_groups["evidence"].append(suggestion)
        elif any(
            term in lower for term in ["limitation", "risk", "uncertainty", "failure"]
        ):
            suggestion_groups["risk"].append(suggestion)
        else:
            suggestion_groups["clarity"].append(suggestion)

    if not rewrite_excerpt:
        rewrite_excerpt = "\n".join(
            item.get("improved", "") for item in sentence_edits if item.get("improved")
        )[:1400]
    if len(rewrite_excerpt) > 1800:
        rewrite_excerpt = rewrite_excerpt[:1800] + "..."

    current_score = int(draft_quality.get("score") or 0)
    target_score = min(96, max(current_score + 18, 58))

    return {
        "workspace": {"id": workspace.id, "name": workspace.name},
        "topic": topic,
        "suggestions": suggestions[: request.max_suggestions],
        "suggestion_groups": suggestion_groups,
        "draft_quality": draft_quality,
        "target_score": target_score,
        "evidence_map": evidence_map,
        "sentence_edits": sentence_edits,
        "revision_checklist": revision_checklist,
        "rewrite_excerpt": rewrite_excerpt,
        "analysis": combined,
    }


@router.post("/smart-read")
def smart_read(
    request: SmartReadingRequest,
current_user: User = Depends(get_current_user),
):
    workspace = _workspace_or_default(
        current_user, request.workspace_id, "Autonomous Research Lab"
    )

    source_name = "raw_text"
    text = (request.text or "").strip()
    title = "Provided Text"

    if request.paper_id is not None:
        paper = _find_workspace_paper(workspace.id, current_user.id, request.paper_id
        )
        if not paper:
            raise HTTPException(status_code=404, detail="Paper not found in workspace")
        source_name = "workspace_paper"
        title = paper.title
        text = f"{paper.title}. {paper.abstract or ''}"

    if len(text) < 20:
        raise HTTPException(
            status_code=400, detail="Provide a paper_id or sufficient text."
        )

    extraction = _smart_read_extract(text)
    llm_text = _llm_generate(
        system_prompt="You are an AI reading assistant. Summarize contributions, claims, datasets, equations, and limitations clearly.",
        user_prompt=f"Title: {title}\nHeuristic extraction: {extraction}\n\nText:\n{text[:12000]}",
        max_tokens=1600,
        longform=False,
        min_chars=380,
        expansion_instruction="Expand with clearer key claims, limitations, and practical implications.",
    )

    return {
        "workspace": {"id": workspace.id, "name": workspace.name},
        "source": source_name,
        "title": title,
        "extraction": extraction,
        "analysis": llm_text
        or "Smart reading extraction generated from available text.",
    }


@router.post("/fault-detection")
def fault_detection(
    request: FaultDetectionRequest,
current_user: User = Depends(get_current_user),
):
    workspace = _workspace_or_default(
        current_user, request.workspace_id, "Autonomous Research Lab"
    )
    paper = _find_workspace_paper(workspace.id, current_user.id, request.paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found in workspace.")

    text = f"{paper.title}. {paper.abstract or ''}"
    abstract = (paper.abstract or "").strip()
    extraction = _smart_read_extract(text)
    dataset = _extract_dataset_from_text(text)
    metric = _extract_metric_result(text)

    faults: List[Dict[str, Any]] = []

    if len(abstract) < 260:
        faults.append(
            {
                "severity": "high",
                "fault_type": "insufficient_abstract_detail",
                "evidence": "Abstract has limited methodological/evaluation detail.",
                "recommendation": "Expand abstract coverage using the full paper text for stronger reliability.",
            }
        )
    if dataset == "Not explicitly reported":
        faults.append(
            {
                "severity": "medium",
                "fault_type": "missing_dataset_disclosure",
                "evidence": "No explicit dataset references detected.",
                "recommendation": "Verify datasets and sample sizes before using this paper for benchmark conclusions.",
            }
        )
    if metric == "Not explicitly reported":
        faults.append(
            {
                "severity": "medium",
                "fault_type": "missing_metric_reporting",
                "evidence": "No clear quantitative metric found in abstract.",
                "recommendation": "Treat claims as qualitative until full results/metrics are validated.",
            }
        )
    if not extraction.get("limitations"):
        faults.append(
            {
                "severity": "medium",
                "fault_type": "limitations_not_explicit",
                "evidence": "No explicit limitation/failure statement detected.",
                "recommendation": "Cross-check discussion section for limitations before adopting findings.",
            }
        )
    if not _paper_link_from_db(paper):
        faults.append(
            {
                "severity": "low",
                "fault_type": "missing_access_link",
                "evidence": "No direct URL/DOI link available in workspace metadata.",
                "recommendation": "Attach DOI or paper URL for traceability and reproducibility checks.",
            }
        )

    severity_weights = {"high": 35, "medium": 20, "low": 10}
    risk_score = min(
        100,
        sum(severity_weights.get(str(fault.get("severity")), 0) for fault in faults),
    )
    quality_score = max(0, 100 - risk_score)
    severity_breakdown = {
        "high": sum(1 for fault in faults if fault.get("severity") == "high"),
        "medium": sum(1 for fault in faults if fault.get("severity") == "medium"),
        "low": sum(1 for fault in faults if fault.get("severity") == "low"),
    }
    quality_tier = (
        "strong"
        if quality_score >= 80
        else "moderate"
        if quality_score >= 55
        else "weak"
    )
    verification_checklist = [
        "Verify dataset definition, split strategy, and leakage controls.",
        "Confirm reported metrics against the full-text results tables.",
        "Check whether limitations and failure modes are explicitly discussed.",
        "Validate reproducibility artifacts (code, hyperparameters, environment).",
        "Ensure citation claims are supported by the referenced evidence.",
    ]

    llm_summary = _llm_generate(
        system_prompt="You are a strict research quality auditor.",
        user_prompt=(
            f"Paper title: {paper.title}\n"
            f"Authors: {paper.authors}\n"
            f"Heuristic extraction: {extraction}\n"
            f"Heuristic faults: {faults}\n\n"
            f"Risk score: {risk_score}/100, Quality score: {quality_score}/100, Tier: {quality_tier}\n"
            f"Checklist seed: {verification_checklist}\n\n"
            "Write sections: Major Risks, Evidence Gaps, Verification Checklist, Reliability Verdict, and Recommended Next Actions."
        ),
        max_tokens=1400,
        longform=False,
        min_chars=360,
        expansion_instruction="Add clearer verification steps and cite specific risk signals.",
    )

    return {
        "workspace": {"id": workspace.id, "name": workspace.name},
        "paper": {
            "id": paper.id,
            "title": paper.title,
            "url": _paper_link_from_db(paper) or None,
            "doi": paper.doi,
        },
        "fault_count": len(faults),
        "risk_score": risk_score,
        "quality_score": quality_score,
        "quality_tier": quality_tier,
        "severity_breakdown": severity_breakdown,
        "verification_checklist": verification_checklist,
        "faults": faults,
        "analysis": llm_summary
        or "Fault detection completed from available metadata and abstract.",
    }


@router.post("/compare-papers")
def compare_papers(
    request: ComparePapersRequest,
current_user: User = Depends(get_current_user),
):
    workspace = _workspace_or_default(
        current_user, request.workspace_id, "Autonomous Research Lab"
    )
    papers = _load_workspace_papers(workspace, request.paper_ids)
    if len(papers) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least two valid papers are required for comparison.",
        )

    columns = [f"Paper {idx + 1}" for idx in range(len(papers))]
    headers = [paper.title for paper in papers]
    datasets = [
        _extract_dataset_from_text(f"{paper.title} {paper.abstract or ''}")
        for paper in papers
    ]
    key_results = [_extract_metric_result(paper.abstract or "") for paper in papers]

    limitations = []
    for paper in papers:
        matches = [
            sentence
            for sentence in _extract_sentences(paper.abstract or "")
            if any(
                term in sentence.lower()
                for term in [
                    "limitation",
                    "however",
                    "challenge",
                    "future work",
                    "constraint",
                ]
            )
        ]
        limitations.append(matches[0] if matches else "Not explicitly discussed")

    methods = []
    for paper in papers:
        tokens = _extract_keywords(f"{paper.title} {paper.abstract or ''}", top_n=5)
        methods.append(", ".join(tokens[:3]) if tokens else "Not explicit")

    table = [
        {"feature": "Dataset", "values": datasets},
        {"feature": "Method", "values": methods},
        {"feature": "Key Result", "values": key_results},
        {"feature": "Limitations", "values": limitations},
        {
            "feature": "Paper Link",
            "values": [
                paper.url or (f"https://doi.org/{paper.doi}" if paper.doi else "N/A")
                for paper in papers
            ],
        },
    ]

    llm_text = _llm_generate(
        system_prompt="You are a research comparator. Produce concise comparison insights and decision guidance.",
        user_prompt=(
            f"Comparison table: {table}\n\n"
            "Return sections: Comparative Strengths, Trade-offs, Best Fit Scenarios, Recommendation.\n\n"
            f"Paper context:\n{_paper_context_from_db(papers, limit=8)}"
        ),
        max_tokens=1800,
        longform=False,
        min_chars=420,
        expansion_instruction="Expand trade-offs, decision criteria, and best-fit scenarios with more specificity.",
    )

    return {
        "workspace": {"id": workspace.id, "name": workspace.name},
        "columns": columns,
        "paper_titles": headers,
        "table": table,
        "analysis": llm_text
        or "Structured comparison table generated from selected papers.",
    }


@router.post("/personalized-feed")
async def personalized_feed(
    request: PersonalizedFeedRequest,
current_user: User = Depends(get_current_user),
):
    workspace = _workspace_or_default(
        current_user, request.workspace_id, "Autonomous Research Lab"
    )
    repo = _repo_for_db()
    papers = _load_workspace_papers(workspace)
    if not papers:
        raise HTTPException(status_code=400, detail="No papers found in workspace.")

    text_blob = " ".join(f"{paper.title} {paper.abstract or ''}" for paper in papers)
    workspace_keywords = _extract_keywords(text_blob, top_n=16)

    session_state = repo.get_session_state_for_user(current_user.id)
    session_extra: Dict[str, Any] = {}
    if session_state and session_state.extra_json:
        try:
            parsed = json.loads(session_state.extra_json)
            if isinstance(parsed, dict):
                session_extra = parsed
        except Exception:
            session_extra = {}

    recent_feed_keys = [
        str(item).strip().lower()
        for item in (session_extra.get("personalized_feed_recent_keys") or [])
        if str(item).strip()
    ]
    refresh_turn = int(session_extra.get("personalized_feed_turn") or 0)
    if request.force_live:
        refresh_turn += 1

    history_rows = repo.list_search_history_for_user(current_user.id, limit=80)
    history_signals = _history_query_signals(history_rows)
    realtime_bundle = await _fetch_realtime_signal_bundle(
        [*workspace_keywords[:10], *(history_signals.get("keywords") or [])[:10]]
    )
    realtime_keywords = (realtime_bundle.get("trending_keywords") or [])[:12]
    realtime_queries = (realtime_bundle.get("realtime_queries") or [])[:4]
    source_pulse = realtime_bundle.get("source_pulse") or {}

    queries = _compose_query_seeds(
        workspace_keywords=workspace_keywords,
        history_queries=(history_signals.get("queries") or []),
        realtime_queries=realtime_queries,
        limit=4,
    )
    if not queries and workspace_keywords:
        queries = [" ".join(workspace_keywords[:2])]
    queries = [query for query in queries if query][:4]

    refresh_anchor = f"{current_user.id}:{workspace.id}:{request.refresh_seed or ''}:{refresh_turn}:{int(request.force_live)}"

    def _query_offset(seed_query: str, query_idx: int) -> int:
        digest = hashlib.sha256(
            f"{refresh_anchor}:{query_idx}:{seed_query}".encode("utf-8")
        ).hexdigest()
        jitter = int(digest[:6], 16) % 26
        base = (refresh_turn * 5) if request.force_live else 0
        return max(0, (base + (query_idx * 4) + jitter) % 38)

    existing_title_keys = {paper.title.strip().lower() for paper in papers}
    existing_doi_keys = {
        str((paper.doi or "")).strip().lower() for paper in papers if paper.doi
    }

    suggestions: List[Dict[str, Any]] = []
    failed_queries: List[str] = []
    query_sem = asyncio.Semaphore(2)

    async def _run_query(
        seed_query: str, query_idx: int
    ) -> Tuple[str, List[Dict[str, Any]], Optional[str]]:
        try:
            async with query_sem:
                offset = _query_offset(seed_query, query_idx)
                batch, _raw = await _search_global_candidates(
                    seed_query,
                    max_results=18,
                    current_user=current_user,
                    offset=offset,
                )
            return seed_query, batch, None
        except Exception:
            return seed_query, [], "unavailable"

    if queries:
        query_results = await asyncio.gather(
            *[_run_query(query, idx) for idx, query in enumerate(queries)],
            return_exceptions=False,
        )
    else:
        query_results = []

    for seed_query, batch, error in query_results:
        if error:
            failed_queries.append(seed_query)
            continue
        for candidate in batch:
            title_key = str(candidate.get("title") or "").strip().lower()
            doi_key = str(candidate.get("doi") or "").strip().lower()
            if title_key in existing_title_keys:
                continue
            if doi_key and doi_key in existing_doi_keys:
                continue
            suggestions.append(candidate)

    if not suggestions and workspace_keywords:
        fallback_query = " ".join(workspace_keywords[:3]).strip()
        if fallback_query:
            try:
                fallback_batch, _raw = await _search_global_candidates(
                    fallback_query,
                    max_results=24,
                    current_user=current_user,
                    offset=_query_offset(fallback_query, 7),
                )
                for candidate in fallback_batch:
                    title_key = str(candidate.get("title") or "").strip().lower()
                    doi_key = str(candidate.get("doi") or "").strip().lower()
                    if title_key in existing_title_keys:
                        continue
                    if doi_key and doi_key in existing_doi_keys:
                        continue
                    suggestions.append(candidate)
            except Exception:
                failed_queries.append(fallback_query)

    dedup: Dict[str, Dict[str, Any]] = {}
    for candidate in suggestions:
        key = (
            str(candidate.get("doi") or "").strip().lower()
            or str(candidate.get("title") or "").strip().lower()
        )
        if not key:
            continue
        current = dedup.get(key)
        if not current:
            dedup[key] = candidate
            continue
        current_year = int(current.get("year") or 0)
        next_year = int(candidate.get("year") or 0)
        current_citations = int(current.get("citation_count") or 0)
        next_citations = int(candidate.get("citation_count") or 0)
        if (next_year, next_citations) > (current_year, current_citations):
            dedup[key] = candidate

    dedup_values = list(dedup.values())
    if dedup_values:
        await _enrich_citation_counts(
            dedup_values, max_lookups=min(16, len(dedup_values))
        )

    ranking_goal_tokens = [
        *workspace_keywords[:8],
        *(history_signals.get("keywords") or [])[:6],
        *realtime_keywords[:6],
    ]
    ranking_goal = " ".join(ranking_goal_tokens).strip() or workspace.name
    merged = _rank_candidates(
        dedup_values,
        goal=ranking_goal,
        trend_terms=realtime_keywords,
        affinity_terms=(history_signals.get("keywords") or [])[:12],
        source_pulse=source_pulse,
    )

    def _rec_key(candidate: Dict[str, Any]) -> str:
        doi = str(candidate.get("doi") or "").strip().lower()
        if doi:
            return f"doi:{doi}"
        url = str(candidate.get("url") or "").strip().lower()
        if url:
            return f"url:{url}"
        return f"title:{str(candidate.get('title') or '').strip().lower()}"

    recent_key_set = set(recent_feed_keys)
    fresh_candidates = [
        candidate for candidate in merged if _rec_key(candidate) not in recent_key_set
    ]
    stale_candidates = [
        candidate for candidate in merged if _rec_key(candidate) in recent_key_set
    ]

    if fresh_candidates:
        merged_ranked = [*fresh_candidates, *stale_candidates]
    else:
        merged_ranked = merged

    if request.force_live and len(merged_ranked) > request.max_suggestions:
        rotate_by = (refresh_turn * 3) % len(merged_ranked)
        merged_ranked = [*merged_ranked[rotate_by:], *merged_ranked[:rotate_by]]

    trending_papers = _diversify_candidates(merged_ranked, request.max_suggestions)
    source_mix = Counter(
        str(candidate.get("source") or "unknown").strip().lower()
        for candidate in trending_papers
    )

    direction_candidates: List[str] = []
    for keyword in [*realtime_keywords[:6], *workspace_keywords[:6]]:
        if keyword and keyword not in direction_candidates:
            direction_candidates.append(keyword)
    directions = [
        f"Explore {keyword} with stronger benchmark coverage and reproducibility checks."
        for keyword in direction_candidates[:10]
    ]

    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    next_recent_keys = recent_feed_keys[-140:]
    for candidate in trending_papers:
        key = _rec_key(candidate)
        if key in next_recent_keys:
            next_recent_keys = [item for item in next_recent_keys if item != key]
        next_recent_keys.append(key)
    next_recent_keys = next_recent_keys[-180:]

    try:
        if not session_state:
            session_state = repo.create_session_state(current_user.id)
        next_extra = dict(session_extra)
        next_extra["personalized_feed_recent_keys"] = next_recent_keys
        next_extra["personalized_feed_turn"] = refresh_turn
        next_extra["personalized_feed_last_updated_at"] = now_iso
        if request.refresh_seed:
            next_extra["personalized_feed_last_refresh_seed"] = str(
                request.refresh_seed
            )[:80]
        session_state.workspace_id = workspace.id
        session_state.extra_json = json.dumps(next_extra)
        session_state.updated_at = datetime.now(timezone.utc)
        repo.save(session_state)
    except Exception:
        pass

    llm_text = _llm_generate(
        system_prompt="You are a personalized research feed curator.",
        user_prompt=(
            f"Workspace keywords: {workspace_keywords}\n"
            f"User history query seeds: {history_signals.get('queries')}\n"
            f"Real-time trend keywords: {realtime_keywords}\n"
            f"Suggested papers: {trending_papers[:10]}\n\n"
            "Return sections: Weekly Highlights, New Citation Opportunities, Related Research Directions."
        ),
        max_tokens=1500,
        longform=False,
        min_chars=320,
        expansion_instruction="Provide richer weekly highlights and clearer reason codes for each recommendation.",
    )

    return {
        "workspace": {"id": workspace.id, "name": workspace.name},
        "seed_keywords": workspace_keywords,
        "query_seeds": queries,
        "trending_papers": trending_papers,
        "related_directions": directions,
        "relevance_context": {
            "history_queries": (history_signals.get("queries") or [])[:8],
            "history_keywords": (history_signals.get("keywords") or [])[:12],
            "realtime_keywords": realtime_keywords,
            "realtime_query_seeds": realtime_queries,
            "source_pulse": source_pulse,
            "failed_queries": failed_queries,
            "force_live": bool(request.force_live),
            "refresh_turn": refresh_turn,
            "fresh_candidates": len(fresh_candidates),
            "stale_candidates": len(stale_candidates),
            "source_mix": dict(source_mix),
            "candidate_pool": len(merged_ranked),
        },
        "weekly_digest": llm_text
        or "Personalized feed generated from workspace topics and fresh source scans.",
    }


@router.post("/verify-citations")
def verify_citations(
    request: CitationVerifyRequest,
current_user: User = Depends(get_current_user),
):
    workspace = _workspace_or_default(
        current_user, request.workspace_id, "Autonomous Research Lab"
    )
    papers = _load_workspace_papers(workspace, request.paper_ids)
    if not papers:
        raise HTTPException(
            status_code=400, detail="No papers found for citation verification."
        )

    index_map: Dict[int, Paper] = {idx + 1: paper for idx, paper in enumerate(papers)}
    label_map: Dict[str, Paper] = {}
    if request.references:
        by_id = {paper.id: paper for paper in papers}
        for ref in request.references:
            paper = by_id.get(ref.paper_id)
            if paper:
                label_map[ref.label.strip().lower()] = paper

    claims = [
        sentence
        for sentence in _extract_sentences(request.draft_text)
        if len(sentence) >= 35
    ][:40]
    rows = []
    current_year = datetime.now(timezone.utc).year

    for claim in claims:
        explicit_refs = [
            int(match.group(1))
            for match in re.finditer(r"Paper\s+(\d+)", claim, flags=re.IGNORECASE)
        ]
        candidates: List[Tuple[str, Paper]] = []
        for idx in explicit_refs:
            paper = index_map.get(idx)
            if paper:
                candidates.append((f"Paper {idx}", paper))
        for label, paper in label_map.items():
            if label in claim.lower():
                candidates.append((label, paper))

        if not candidates:
            scored = [
                (paper, _overlap_score(claim, f"{paper.title} {paper.abstract or ''}"))
                for paper in papers
            ]
            scored.sort(key=lambda item: item[1], reverse=True)
            for idx, (paper, _) in enumerate(scored[:2], start=1):
                candidates.append((f"candidate_{idx}", paper))

        best_score = 0.0
        best_ref = None
        best_paper = None
        for ref_label, paper in candidates:
            score = _overlap_score(claim, f"{paper.title} {paper.abstract or ''}")
            if score > best_score:
                best_score = score
                best_ref = ref_label
                best_paper = paper

        confidence = _citation_verdict(best_score)
        supported = best_score >= 0.14

        outdated = False
        stronger = None
        if best_paper:
            ref_year = _year_from_text(
                f"{best_paper.title} {best_paper.abstract or ''}"
            )
            best_newer = None
            best_newer_score = best_score
            for paper in papers:
                if paper.id == best_paper.id:
                    continue
                score = _overlap_score(claim, f"{paper.title} {paper.abstract or ''}")
                yr = _year_from_text(f"{paper.title} {paper.abstract or ''}")
                if (
                    yr
                    and ref_year
                    and yr > ref_year + 2
                    and score > best_newer_score + 0.05
                ):
                    best_newer = paper
                    best_newer_score = score
            if ref_year and ref_year <= current_year - 7 and best_newer is not None:
                outdated = True
                stronger = {
                    "title": best_newer.title,
                    "doi": best_newer.doi,
                    "url": best_newer.url,
                }

        rows.append(
            {
                "claim": claim,
                "best_reference": best_ref,
                "supported": supported,
                "confidence": confidence,
                "support_score": round(best_score, 3),
                "outdated": outdated,
                "stronger_citation": stronger,
                "recommendation": (
                    "Citation support is strong."
                    if supported and not outdated
                    else "Citation support is partial; add stronger evidence."
                    if supported
                    else "Citation is weakly supported; replace or add evidence."
                ),
            }
        )

    llm_text = _llm_generate(
        system_prompt="You are a citation integrity reviewer.",
        user_prompt=f"Verification rows: {rows}\n\nProvide a concise integrity summary and prioritized fixes.",
        max_tokens=1100,
        longform=False,
        min_chars=260,
        expansion_instruction="Expand with prioritized fixes and concrete citation replacement guidance.",
    )

    return {
        "workspace": {"id": workspace.id, "name": workspace.name},
        "claims_analyzed": len(rows),
        "supported_claims": sum(1 for row in rows if row["supported"]),
        "outdated_flags": sum(1 for row in rows if row["outdated"]),
        "results": rows,
        "summary": llm_text or "Citation authenticity verification completed.",
    }


@router.post("/paper-check")
async def paper_check(
    payload: PaperCheckRequest,
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: User = Depends(get_current_user),
):
    if payload.paper_id is None and not str(payload.raw_text or "").strip():
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "invalid_input",
                    "message": "Provide either paper_id or raw_text.",
                    "retryable": False,
                }
            },
        )

    raw_text = str(payload.raw_text or "").strip() or None
    try:
        queued = queue_paper_check_job(
            repo=repo,
            user_id=int(current_user.id),
            paper_id=payload.paper_id,
            raw_text=raw_text,
            workspace_id=payload.workspace_id,
        )
        if queued["status"] == "completed" and queued.get("result"):
            return {
                "status": "completed",
                "job_id": queued["job_id"],
                **queued["result"],
            }
        return {
            "status": "pending",
            "job_id": queued["job_id"],
            "metadata": {
                "processed_at": queued["created_at"],
                "version": "paper-check-v1",
            },
        }
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "paper_check_invalid_input",
                    "message": str(exc),
                    "retryable": False,
                }
            },
        )
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "code": "paper_check_failed",
                    "message": str(exc),
                    "retryable": True,
                }
            },
        )


async def _paper_check_status_response(
    job_id: str,
    repo: ResearchRepository,
    current_user: User,
):
    row = get_job_status(repo=repo, job_id=job_id, user_id=int(current_user.id))
    if not row:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "job_not_found",
                    "message": "Paper check job not found.",
                    "retryable": False,
                }
            },
        )
    return row


async def _paper_check_latest_response(
    paper_id: int,
    workspace_id: int,
    repo: ResearchRepository,
    current_user: User,
):
    paper = repo.find_paper_for_user(int(paper_id), int(current_user.id))
    if not paper or int(getattr(paper, "workspace_id", 0) or 0) != int(workspace_id):
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "job_not_found",
                    "message": "Paper check job not found.",
                    "retryable": False,
                }
            },
        )

    row = repo.find_latest_paper_check_job(int(paper_id), int(current_user.id))
    if not row:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "job_not_found",
                    "message": "Paper check job not found.",
                    "retryable": False,
                }
            },
        )
    return {
        "job_id": row.job_id,
        "status": row.status,
        "result": row.result if row.status == "completed" else None,
        "error": (
            {
                "message": row.error,
                "retryable": bool(row.retryable),
            }
            if row.error
            else None
        ),
        "created_at": (row.created_at or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z"),
        "updated_at": (row.updated_at or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z"),
        "fingerprint": row.fingerprint,
        "latency_ms": row.latency_ms,
    }


@router.get("/paper-check/latest")
async def paper_check_latest_job(
    paper_id: int,
    workspace_id: int,
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: User = Depends(get_current_user),
):
    return await _paper_check_latest_response(paper_id, workspace_id, repo, current_user)


@router.get("/paper-check/{job_id}")
async def paper_check_job_status(
    job_id: str,
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: User = Depends(get_current_user),
):
    return await _paper_check_status_response(job_id, repo, current_user)


@router.get("/paper-check/jobs/{job_id}")
async def paper_check_job_status_legacy(
    job_id: str,
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: User = Depends(get_current_user),
):
    return await _paper_check_status_response(job_id, repo, current_user)


@router.post("/paper-check/{job_id}/requeue")
async def paper_check_job_requeue(
    job_id: str,
    repo: ResearchRepository = Depends(get_research_repository),
    current_user: User = Depends(get_current_user),
):
    if not has_analytics_admin_access(current_user.id):
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "paper_check_admin_required",
                    "message": "Admin access is required to requeue paper check jobs.",
                    "retryable": False,
                }
            },
        )
    try:
        updated = requeue_failed_job(repo=repo, job_id=job_id)
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "paper_check_requeue_invalid",
                    "message": str(exc),
                    "retryable": False,
                }
            },
        )
    if updated is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "job_not_found",
                    "message": "Paper check job not found.",
                    "retryable": False,
                }
            },
        )
    return updated


# ============================================================================
# RESEARCH INTELLIGENCE ARTIFACTS
# ============================================================================

def _workspace_or_default(current_user: User, workspace_id: Optional[int], default_name: str) -> Workspace:
    """Get workspace or create default workspace."""
    from repositories.research import get_research_repository
    repo = get_research_repository()
    
    if workspace_id:
        workspace = repo.find_workspace_for_user(workspace_id, current_user.id)
        if workspace:
            return workspace
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    return repo.get_or_create_default_workspace(current_user.id)


def _load_workspace_papers(workspace: Workspace, paper_ids: Optional[List[int]] = None) -> List[Paper]:
    """Load papers from workspace."""
    from repositories.research import get_research_repository
    repo = get_research_repository()
    
    papers = repo.list_papers_for_workspace(workspace.id, paper_ids)
    if not papers:
        raise HTTPException(status_code=400, detail="No papers found in workspace selection.")
    return papers


@router.post("/intelligence")
async def create_research_intelligence_artifact(
    request: ResearchIntelligenceArtifactRequest,
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """
    Create a new research intelligence artifact and execute the intelligence pipeline.
    
    This endpoint:
    1. Validates workspace and user authorization
    2. Creates an artifact with status=running
    3. Executes the 7-stage intelligence pipeline
    4. Persists results and calculates overall score
    5. Returns the completed artifact
    """
    workspace = _workspace_or_default(current_user, request.workspace_id, "Autonomous Research Lab")
    papers = _load_workspace_papers(workspace, request.paper_ids)
    
    topic = request.topic.strip()
    
    try:
        artifact_service = get_artifact_service_instance(repo)
        
        # Create artifact with running status
        artifact = artifact_service.create_artifact(
            workspace_id=workspace.id,
            user_id=current_user.id,
            topic=topic,
            paper_ids=request.paper_ids,
            pipeline_version=request.pipeline_version or "1.0",
        )
        
        # Execute pipeline
        artifact = artifact_service.execute_pipeline(
            artifact_id=artifact.id,
            papers=papers,
            topic=topic,
        )
        
        return _serialize_artifact(artifact)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Research intelligence artifact creation failed: {str(exc)}")


@router.get("/intelligence/{artifact_id}")
async def get_research_intelligence_artifact(
    artifact_id: str,
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """Retrieve a research intelligence artifact by ID."""
    artifact = repo.get_research_intelligence_artifact(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Research intelligence artifact not found")
    
    # Verify workspace ownership
    workspace = repo.find_workspace_for_user(artifact.workspace_id, current_user.id)
    if not workspace:
        raise HTTPException(status_code=403, detail="Access denied to this artifact")
    
    return _serialize_artifact(artifact)


@router.get("/workspaces/{workspace_id}/research-intelligence")
async def list_workspace_research_intelligence_artifacts(
    workspace_id: int,
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """List all research intelligence artifacts for a workspace."""
    # Verify workspace ownership
    workspace = repo.find_workspace_for_user(workspace_id, current_user.id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    artifacts = repo.list_research_intelligence_artifacts_for_workspace(workspace_id, current_user.id)
    return {"artifacts": [_serialize_artifact(a) for a in artifacts]}


@router.delete("/intelligence/{artifact_id}")
async def delete_research_intelligence_artifact(
    artifact_id: str,
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """Delete a research intelligence artifact."""
    artifact = repo.get_research_intelligence_artifact(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Research intelligence artifact not found")
    
    # Verify workspace ownership
    workspace = repo.find_workspace_for_user(artifact.workspace_id, current_user.id)
    if not workspace:
        raise HTTPException(status_code=403, detail="Access denied to this artifact")
    
    success = repo.delete_research_intelligence_artifact(artifact_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete artifact")
    
    return {"success": True}


def _serialize_artifact(artifact: ResearchIntelligenceArtifact) -> Dict[str, Any]:
    """Serialize artifact for API response."""
    return {
        "id": artifact.id,
        "workspace_id": artifact.workspace_id,
        "user_id": artifact.user_id,
        "topic": artifact.topic,
        "paper_ids": artifact.paper_ids,
        "paper_count": artifact.paper_count,
        "status": artifact.status,
        "pipeline_version": artifact.pipeline_version,
        "created_at": artifact.created_at.isoformat().replace("+00:00", "Z"),
        "updated_at": artifact.updated_at.isoformat().replace("+00:00", "Z"),
        "evidence_analysis": artifact.evidence_analysis,
        "gap_analysis": artifact.gap_analysis,
        "opportunity_ranking": artifact.opportunity_ranking,
        "research_questions": artifact.research_questions,
        "hypothesis_challenges": artifact.hypothesis_challenges,
        "citation_verification": artifact.citation_verification,
        "knowledge_graph": artifact.knowledge_graph,
        "overall_score": artifact.overall_score,
        "summary": artifact.summary,
        "stage_errors": artifact.stage_errors,
    }


# --- Saved Research Questions ---

class SaveResearchQuestionRequest(BaseModel):
    workspace_id: int
    question: str
    category: str
    complexity: str
    confidence: int
    novelty: int
    feasibility: int
    impact: int
    source_gap_id: Optional[str] = None
    source_gap_description: Optional[str] = None
    supporting_papers: List[int] = Field(default_factory=list)
    rationale: Optional[str] = None
    source_artifact_id: Optional[str] = None


def _serialize_saved_question(question: SavedResearchQuestion) -> Dict[str, Any]:
    """Serialize saved research question for API response."""
    return {
        "id": question.id,
        "workspace_id": question.workspace_id,
        "user_id": question.user_id,
        "question": question.question,
        "category": question.category,
        "complexity": question.complexity,
        "confidence": question.confidence,
        "novelty": question.novelty,
        "feasibility": question.feasibility,
        "impact": question.impact,
        "source_gap_id": question.source_gap_id,
        "source_gap_description": question.source_gap_description,
        "supporting_papers": question.supporting_papers,
        "rationale": question.rationale,
        "source_artifact_id": question.source_artifact_id,
        "created_at": question.created_at.isoformat().replace("+00:00", "Z"),
    }


@router.post("/questions")
async def save_research_question(
    payload: SaveResearchQuestionRequest,
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """Save a research question to a workspace."""
    # Verify workspace ownership
    workspace = repo.find_workspace_for_user(payload.workspace_id, current_user.id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Generate unique ID
    import uuid
    question_id = f"rq_{uuid.uuid4().hex[:16]}"
    
    question = repo.create_saved_research_question(
        id=question_id,
        workspace_id=payload.workspace_id,
        user_id=current_user.id,
        question=payload.question,
        category=payload.category,
        complexity=payload.complexity,
        confidence=payload.confidence,
        novelty=payload.novelty,
        feasibility=payload.feasibility,
        impact=payload.impact,
        source_gap_id=payload.source_gap_id,
        source_gap_description=payload.source_gap_description,
        supporting_papers=payload.supporting_papers,
        rationale=payload.rationale,
        source_artifact_id=payload.source_artifact_id,
    )
    
    return _serialize_saved_question(question)


@router.get("/workspaces/{workspace_id}/questions")
async def list_saved_research_questions(
    workspace_id: int,
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """List all saved research questions for a workspace."""
    # Verify workspace ownership
    workspace = repo.find_workspace_for_user(workspace_id, current_user.id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    questions = repo.list_saved_research_questions_for_workspace(workspace_id, current_user.id)
    return {"questions": [_serialize_saved_question(q) for q in questions]}


@router.get("/questions/{question_id}")
async def get_saved_research_question(
    question_id: str,
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """Get a specific saved research question."""
    question = repo.get_saved_research_question(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Research question not found")
    
    # Verify workspace ownership
    workspace = repo.find_workspace_for_user(question.workspace_id, current_user.id)
    if not workspace:
        raise HTTPException(status_code=403, detail="Access denied to this question")
    
    return _serialize_saved_question(question)


@router.delete("/questions/{question_id}")
async def delete_saved_research_question(
    question_id: str,
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """Delete a saved research question."""
    question = repo.get_saved_research_question(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Research question not found")
    
    # Verify workspace ownership
    workspace = repo.find_workspace_for_user(question.workspace_id, current_user.id)
    if not workspace:
        raise HTTPException(status_code=403, detail="Access denied to this question")
    
    success = repo.delete_saved_research_question(question_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete question")
    
    return {"success": True}


# ============================================================================
# RESEARCH PLAN ENDPOINTS
# ============================================================================

class CreateResearchPlanRequest(BaseModel):
    workspace_id: int
    artifact_id: str
    opportunity_id: str
    opportunity_description: str
    title: str
    research_problem: str
    research_question: str
    hypothesis: str
    objectives: str
    proposed_methodology: str
    alternative_methodology: str
    datasets: str
    variables: str
    baselines: str
    evaluation_metrics: str
    expected_contribution: str
    risks: str
    limitations: str
    reproducibility_requirements: str
    supporting_papers: List[int] = Field(default_factory=list)
    evidence_references: List[str] = Field(default_factory=list)
    status: str = "draft"


class UpdateResearchPlanRequest(BaseModel):
    title: Optional[str] = None
    research_problem: Optional[str] = None
    research_question: Optional[str] = None
    hypothesis: Optional[str] = None
    objectives: Optional[str] = None
    proposed_methodology: Optional[str] = None
    alternative_methodology: Optional[str] = None
    datasets: Optional[str] = None
    variables: Optional[str] = None
    baselines: Optional[str] = None
    evaluation_metrics: Optional[str] = None
    expected_contribution: Optional[str] = None
    risks: Optional[str] = None
    limitations: Optional[str] = None
    reproducibility_requirements: Optional[str] = None
    supporting_papers: Optional[List[int]] = None
    evidence_references: Optional[List[str]] = None
    researcher_decisions: Optional[List[Dict[str, Any]]] = None
    status: Optional[str] = None


class GeneratePlanSuggestionsRequest(BaseModel):
    artifact_id: str
    opportunity_id: str
    gap_description: str
    category: str
    evidence_strength: int
    novelty: int
    impact: int
    feasibility: int
    recency: int
    overall_score: int
    explanation: str
    supporting_papers: List[int]
    affected_papers: List[int]


def _serialize_research_plan(plan: ResearchPlan) -> Dict[str, Any]:
    """Serialize research plan for API response."""
    return {
        "id": plan.id,
        "workspace_id": plan.workspace_id,
        "user_id": plan.user_id,
        "artifact_id": plan.artifact_id,
        "opportunity_id": plan.opportunity_id,
        "opportunity_description": plan.opportunity_description,
        "title": plan.title,
        "research_problem": plan.research_problem,
        "research_question": plan.research_question,
        "hypothesis": plan.hypothesis,
        "objectives": plan.objectives,
        "proposed_methodology": plan.proposed_methodology,
        "alternative_methodology": plan.alternative_methodology,
        "datasets": plan.datasets,
        "variables": plan.variables,
        "baselines": plan.baselines,
        "evaluation_metrics": plan.evaluation_metrics,
        "expected_contribution": plan.expected_contribution,
        "risks": plan.risks,
        "limitations": plan.limitations,
        "reproducibility_requirements": plan.reproducibility_requirements,
        "supporting_papers": plan.supporting_papers,
        "evidence_references": plan.evidence_references,
        "researcher_decisions": [
            {
                "field_name": dec.field_name,
                "ai_suggestion": dec.ai_suggestion,
                "researcher_decision": dec.researcher_decision,
                "final_value": dec.final_value,
                "decision_timestamp": dec.decision_timestamp.isoformat().replace("+00:00", "Z"),
                "evidence_references": dec.evidence_references,
            }
            for dec in plan.researcher_decisions
        ],
        "status": plan.status,
        "created_at": plan.created_at.isoformat().replace("+00:00", "Z"),
        "updated_at": plan.updated_at.isoformat().replace("+00:00", "Z"),
    }


@router.post("/plans/generate")
async def generate_plan_suggestions(
    payload: GeneratePlanSuggestionsRequest,
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """Generate AI suggestions for a research plan based on an opportunity."""
    # Verify artifact ownership
    artifact = repo.get_research_intelligence_artifact(payload.artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    
    workspace = repo.find_workspace_for_user(artifact.workspace_id, current_user.id)
    if not workspace:
        raise HTTPException(status_code=403, detail="Access denied to this artifact")
    
    # Get supporting papers
    papers = []
    for paper_id in payload.supporting_papers:
        paper = repo.find_paper_for_user(paper_id, current_user.id)
        if paper:
            papers.append(paper)
    
    # Create opportunity object
    from repositories.research import ResearchOpportunity
    opportunity = ResearchOpportunity(
        gap_id=payload.opportunity_id,
        gap_description=payload.gap_description,
        category=payload.category,
        evidence_strength=payload.evidence_strength,
        novelty=payload.novelty,
        impact=payload.impact,
        feasibility=payload.feasibility,
        recency=payload.recency,
        overall_score=payload.overall_score,
        rank=0,  # Not needed for generation
        explanation=payload.explanation,
        supporting_papers=payload.supporting_papers,
        affected_papers=payload.affected_papers,
    )
    
    # Generate suggestions
    plan_service = get_plan_service()
    suggestions = await plan_service.generate_plan_suggestions(
        opportunity=opportunity,
        artifact=artifact,
        papers=papers,
    )
    
    return suggestions


@router.post("/plans")
async def create_research_plan(
    payload: CreateResearchPlanRequest,
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """Create a new research plan from a research opportunity."""
    # Verify workspace ownership
    workspace = repo.find_workspace_for_user(payload.workspace_id, current_user.id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Verify artifact ownership
    artifact = repo.get_research_intelligence_artifact(payload.artifact_id)
    if not artifact or artifact.workspace_id != payload.workspace_id:
        raise HTTPException(status_code=404, detail="Artifact not found or access denied")
    
    # Generate plan ID
    import uuid
    plan_id = f"plan_{uuid.uuid4().hex}"
    
    plan = repo.create_research_plan(
        id=plan_id,
        workspace_id=payload.workspace_id,
        user_id=current_user.id,
        artifact_id=payload.artifact_id,
        opportunity_id=payload.opportunity_id,
        opportunity_description=payload.opportunity_description,
        title=payload.title,
        research_problem=payload.research_problem,
        research_question=payload.research_question,
        hypothesis=payload.hypothesis,
        objectives=payload.objectives,
        proposed_methodology=payload.proposed_methodology,
        alternative_methodology=payload.alternative_methodology,
        datasets=payload.datasets,
        variables=payload.variables,
        baselines=payload.baselines,
        evaluation_metrics=payload.evaluation_metrics,
        expected_contribution=payload.expected_contribution,
        risks=payload.risks,
        limitations=payload.limitations,
        reproducibility_requirements=payload.reproducibility_requirements,
        supporting_papers=payload.supporting_papers,
        evidence_references=payload.evidence_references,
        status=payload.status,
    )
    
    return _serialize_research_plan(plan)


@router.get("/plans/{plan_id}")
async def get_research_plan(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """Get a specific research plan."""
    plan = repo.get_research_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Research plan not found")
    
    # Verify workspace ownership
    workspace = repo.find_workspace_for_user(plan.workspace_id, current_user.id)
    if not workspace:
        raise HTTPException(status_code=403, detail="Access denied to this plan")
    
    return _serialize_research_plan(plan)


@router.get("/workspaces/{workspace_id}/plans")
async def list_research_plans(
    workspace_id: int,
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """List all research plans for a workspace."""
    # Verify workspace ownership
    workspace = repo.find_workspace_for_user(workspace_id, current_user.id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    plans = repo.list_research_plans_for_workspace(workspace_id, current_user.id)
    return {"plans": [_serialize_research_plan(plan) for plan in plans]}


@router.put("/plans/{plan_id}")
async def update_research_plan(
    plan_id: str,
    payload: UpdateResearchPlanRequest,
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """Update a research plan."""
    plan = repo.get_research_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Research plan not found")
    
    # Verify workspace ownership
    workspace = repo.find_workspace_for_user(plan.workspace_id, current_user.id)
    if not workspace:
        raise HTTPException(status_code=403, detail="Access denied to this plan")
    
    # Build updates dict
    updates: Dict[str, Any] = {}
    if payload.title is not None:
        updates["title"] = payload.title
    if payload.research_problem is not None:
        updates["research_problem"] = payload.research_problem
    if payload.research_question is not None:
        updates["research_question"] = payload.research_question
    if payload.hypothesis is not None:
        updates["hypothesis"] = payload.hypothesis
    if payload.objectives is not None:
        updates["objectives"] = payload.objectives
    if payload.proposed_methodology is not None:
        updates["proposed_methodology"] = payload.proposed_methodology
    if payload.alternative_methodology is not None:
        updates["alternative_methodology"] = payload.alternative_methodology
    if payload.datasets is not None:
        updates["datasets"] = payload.datasets
    if payload.variables is not None:
        updates["variables"] = payload.variables
    if payload.baselines is not None:
        updates["baselines"] = payload.baselines
    if payload.evaluation_metrics is not None:
        updates["evaluation_metrics"] = payload.evaluation_metrics
    if payload.expected_contribution is not None:
        updates["expected_contribution"] = payload.expected_contribution
    if payload.risks is not None:
        updates["risks"] = payload.risks
    if payload.limitations is not None:
        updates["limitations"] = payload.limitations
    if payload.reproducibility_requirements is not None:
        updates["reproducibility_requirements"] = payload.reproducibility_requirements
    if payload.supporting_papers is not None:
        updates["supporting_papers"] = payload.supporting_papers
    if payload.evidence_references is not None:
        updates["evidence_references"] = payload.evidence_references
    if payload.researcher_decisions is not None:
        # Convert dict to ResearcherDecision objects
        updates["researcher_decisions"] = [
            ResearcherDecision(
                field_name=dec["field_name"],
                ai_suggestion=dec["ai_suggestion"],
                researcher_decision=dec["researcher_decision"],
                final_value=dec["final_value"],
                decision_timestamp=datetime.fromisoformat(dec["decision_timestamp"].replace("Z", "+00:00")),
                evidence_references=dec.get("evidence_references", []),
            )
            for dec in payload.researcher_decisions
        ]
    if payload.status is not None:
        updates["status"] = payload.status
    
    updated_plan = repo.update_research_plan(plan_id, updates)
    if not updated_plan:
        raise HTTPException(status_code=500, detail="Failed to update plan")
    
    return _serialize_research_plan(updated_plan)


@router.delete("/plans/{plan_id}")
async def delete_research_plan(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """Delete a research plan."""
    plan = repo.get_research_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Research plan not found")
    
    # Verify workspace ownership
    workspace = repo.find_workspace_for_user(plan.workspace_id, current_user.id)
    if not workspace:
        raise HTTPException(status_code=403, detail="Access denied to this plan")
    
    success = repo.delete_research_plan(plan_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete plan")
    
    return {"success": True}


@router.post("/plans/{plan_id}/export")
async def export_research_plan_to_docspace(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    repo: ResearchRepository = Depends(get_research_repository),
):
    """Export a research plan to a WorkspaceDocument in DocSpace."""
    plan = repo.get_research_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Research plan not found")
    
    # Verify workspace ownership
    workspace = repo.find_workspace_for_user(plan.workspace_id, current_user.id)
    if not workspace:
        raise HTTPException(status_code=403, detail="Access denied to this plan")
    
    # Convert plan to document
    plan_service = get_plan_service()
    document = plan_service.convert_to_document(plan)
    
    # Create document in repository
    created_doc = repo.create_workspace_document(
        workspace_id=document.workspace_id,
        user_id=document.user_id,
        title=document.title,
        content=document.content,
    )
    
    return _serialize_research_plan(plan)
