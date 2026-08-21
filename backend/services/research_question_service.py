"""
research_question_service.py
────────────────────────────
Research Question Generation Service for Soyog AI

Generates research questions from gaps and opportunities.
Integrates with Gap Intelligence and Opportunity Scoring to provide actionable research questions.

This service provides:
- Research question generation from gaps
- Question categorization (exploratory, confirmatory, comparative, causal)
- Question complexity scoring
- Evidence-based question grounding
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from repositories.research import StructuredGap, Paper
from utils.text_utils import tokenize as _tokenize

logger = logging.getLogger(__name__)

# Feature flag
RESEARCH_QUESTION_GENERATION_ENABLED = os.getenv(
    "RESEARCH_QUESTION_GENERATION_ENABLED", "1"
).strip().lower() in {"1", "true", "yes"}

# Question templates
_EXPLORATORY_TEMPLATES = [
    "What are the {aspect} of {topic}?",
    "How does {aspect} influence {topic}?",
    "What factors contribute to {aspect} in {topic}?",
    "To what extent does {aspect} affect {topic}?",
]

_CONFIRMATORY_TEMPLATES = [
    "Does {aspect} improve {topic}?",
    "Is there a relationship between {aspect} and {topic}?",
    "Can {aspect} be used to enhance {topic}?",
    "Does {aspect} significantly impact {topic}?",
]

_COMPARATIVE_TEMPLATES = [
    "How does {aspect} compare to {alternative} in {topic}?",
    "What are the differences between {aspect} and {alternative} for {topic}?",
    "Is {aspect} superior to {alternative} in {topic}?",
    "How do {aspect} and {alternative} differ in their effect on {topic}?",
]

_CAUSAL_TEMPLATES = [
    "What causes {aspect} in {topic}?",
    "How does {aspect} lead to {outcome} in {topic}?",
    "What are the causal mechanisms linking {aspect} and {topic}?",
    "Under what conditions does {aspect} cause {outcome} in {topic}?",
]

# Question complexity indicators
_COMPLEXITY_INDICATORS = {
    "simple": ["what", "how", "does", "is"],
    "moderate": ["to what extent", "under what conditions", "factors contribute"],
    "complex": ["mechanisms", "interactions", "moderators", "mediators", "causal pathways"],
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ResearchQuestion:
    id: str
    question: str
    category: str  # exploratory, confirmatory, comparative, causal
    complexity: str  # simple, moderate, complex
    confidence: int  # 0-100
    novelty: int  # 0-100
    feasibility: int  # 0-100
    impact: int  # 0-100
    source_gap_id: str
    source_gap_description: str
    supporting_papers: List[int]
    rationale: str


@dataclass
class QuestionGenerationResult:
    topic: str
    questions: List[ResearchQuestion]
    total_questions: int
    top_questions: List[ResearchQuestion]
    summary: str
    generated_at: datetime = field(default_factory=_utcnow)


class ResearchQuestionService:
    """Service for research question generation."""
    
    def __init__(self):
        self._cache: Dict[str, QuestionGenerationResult] = {}
        self._cache_ttl_seconds = 10 * 60  # 10 minutes
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        if cache_key not in self._cache:
            return False
        cached = self._cache[cache_key]
        age = (datetime.now(timezone.utc) - cached.generated_at).total_seconds()
        return age < self._cache_ttl_seconds
    
    def _get_cache_key(self, topic: str, gap_ids: List[str]) -> str:
        gap_ids_sorted = tuple(sorted(gap_ids))
        return f"{topic}:{gap_ids_sorted}"
    
    def _extract_aspect_from_gap(self, gap: StructuredGap) -> str:
        """Extract the main aspect from a gap description."""
        # Simple extraction: take first few meaningful words
        words = gap.description.split()
        aspect_words = []
        
        for word in words[:5]:
            if len(word) > 3 and word.lower() not in {"the", "and", "for", "with", "from"}:
                aspect_words.append(word)
        
        return " ".join(aspect_words) if aspect_words else gap.category
    
    def _determine_question_category(self, gap: StructuredGap) -> str:
        """Determine the category of question based on gap type."""
        if gap.category == "contradiction":
            return "confirmatory"
        elif gap.category == "dataset":
            return "comparative"
        elif gap.category == "generalization":
            return "causal"
        elif gap.category == "methodological":
            return "exploratory"
        else:
            return "exploratory"
    
    def _generate_question_from_gap(
        self, gap: StructuredGap, topic: str, idx: int
    ) -> ResearchQuestion:
        """Generate a research question from a gap."""
        aspect = self._extract_aspect_from_gap(gap)
        category = self._determine_question_category(gap)
        
        # Select template based on category
        if category == "exploratory":
            template = _EXPLORATORY_TEMPLATES[idx % len(_EXPLORATORY_TEMPLATES)]
        elif category == "confirmatory":
            template = _CONFIRMATORY_TEMPLATES[idx % len(_CONFIRMATORY_TEMPLATES)]
        elif category == "comparative":
            template = _COMPARATIVE_TEMPLATES[idx % len(_COMPARATIVE_TEMPLATES)]
        else:  # causal
            template = _CAUSAL_TEMPLATES[idx % len(_CAUSAL_TEMPLATES)]
        
        # Fill template
        question = template.format(
            aspect=aspect,
            topic=topic,
            alternative="alternative approaches",
            outcome="outcomes"
        )
        
        # Determine complexity
        complexity = "simple"
        if any(indicator in question.lower() for indicator in _COMPLEXITY_INDICATORS["moderate"]):
            complexity = "moderate"
        elif any(indicator in question.lower() for indicator in _COMPLEXITY_INDICATORS["complex"]):
            complexity = "complex"
        
        # Calculate scores based on gap
        confidence = gap.confidence
        novelty = gap.novelty_potential
        feasibility = gap.feasibility
        impact = gap.research_impact
        
        # Generate rationale
        rationale = (
            f"This question addresses the identified gap: {gap.description}. "
            f"Category: {category}, Complexity: {complexity}. "
            f"Based on {gap.evidence_count} papers."
        )
        
        return ResearchQuestion(
            id=f"q_{idx}",
            question=question,
            category=category,
            complexity=complexity,
            confidence=confidence,
            novelty=novelty,
            feasibility=feasibility,
            impact=impact,
            source_gap_id=f"gap_{idx}",
            source_gap_description=gap.description,
            supporting_papers=gap.supporting_papers,
            rationale=rationale
        )
    
    def _rank_questions(self, questions: List[ResearchQuestion]) -> List[ResearchQuestion]:
        """Rank questions by overall potential."""
        # Calculate overall score
        for q in questions:
            q.novelty = min(100, q.novelty)
            q.impact = min(100, q.impact)
            q.feasibility = min(100, q.feasibility)
        
        # Sort by weighted score (novelty 40%, impact 40%, feasibility 20%)
        questions.sort(
            key=lambda q: (q.novelty * 0.4 + q.impact * 0.4 + q.feasibility * 0.2),
            reverse=True
        )
        
        return questions
    
    def generate_questions(
        self,
        topic: str,
        gaps: List[StructuredGap],
        max_questions: int = 10,
        use_cache: bool = True
    ) -> QuestionGenerationResult:
        """Generate research questions from gaps."""
        if not RESEARCH_QUESTION_GENERATION_ENABLED:
            raise RuntimeError(
                "Research Question Generation is disabled. "
                "Set RESEARCH_QUESTION_GENERATION_ENABLED=1 in .env"
            )
        
        if not gaps:
            return QuestionGenerationResult(
                topic=topic,
                questions=[],
                total_questions=0,
                top_questions=[],
                summary="No gaps detected to generate research questions"
            )
        
        gap_ids = [f"gap_{i}" for i in range(len(gaps))]
        cache_key = self._get_cache_key(topic, gap_ids)
        
        if use_cache and self._is_cache_valid(cache_key):
            return self._cache[cache_key]
        
        # Generate questions from gaps
        questions: List[ResearchQuestion] = []
        for idx, gap in enumerate(gaps[:max_questions]):
            question = self._generate_question_from_gap(gap, topic, idx)
            questions.append(question)
        
        # Rank questions
        questions = self._rank_questions(questions)
        
        # Generate summary
        total = len(questions)
        top_questions = questions[:5]
        
        summary = (
            f"Generated {total} research questions from {len(gaps)} gaps. "
            f"Top question: {top_questions[0].question if top_questions else 'N/A'}"
        )
        
        result = QuestionGenerationResult(
            topic=topic,
            questions=questions,
            total_questions=total,
            top_questions=top_questions,
            summary=summary
        )
        
        # Cache the result
        self._cache[cache_key] = result
        
        return result


# Global service instance
_question_service: Optional[ResearchQuestionService] = None


def get_question_service() -> ResearchQuestionService:
    """Get the global research question service instance."""
    global _question_service
    if _question_service is None:
        _question_service = ResearchQuestionService()
    return _question_service
