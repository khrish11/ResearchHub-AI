"""
query_classification_service.py
───────────────────────────────
Research Query Classification Service for Soyog AI

Classifies research queries into intent categories and detects ambiguity.
Used for the initial research entry experience before workspace selection.

This service provides:
- Query classification (topic exploration, research question, problem investigation, etc.)
- Ambiguity detection
- Clarification question generation
- Research direction summarization
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class QueryClassification:
    """Classification of a research query."""
    category: str  # topic_exploration, research_question, problem_investigation, literature_review, comparison, methodology, trend_analysis, ambiguous
    confidence: float  # 0.0-1.0
    user_friendly_description: str
    requires_clarification: bool


@dataclass
class ClarificationQuestion:
    """A clarification question to disambiguate a research query."""
    id: str
    question: str
    options: List[str]


@dataclass
class ResearchDirection:
    """Summary of the research direction after classification/clarification."""
    topic: str
    focus: Optional[str]
    research_intent: str
    suggested_scope: str


@dataclass
class QueryClassificationResult:
    """Result of query classification."""
    query: str
    classification: QueryClassification
    clarification_questions: List[ClarificationQuestion]
    research_direction: Optional[ResearchDirection]
    generated_at: datetime = field(default_factory=_utcnow)


class QueryClassificationService:
    """Service for research query classification."""
    
    def __init__(self):
        self._cache: Dict[str, QueryClassificationResult] = {}
        self._cache_ttl_seconds = 5 * 60  # 5 minutes
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        if cache_key not in self._cache:
            return False
        cached = self._cache[cache_key]
        age = (datetime.now(timezone.utc) - cached.generated_at).total_seconds()
        return age < self._cache_ttl_seconds
    
    def _get_cache_key(self, query: str) -> str:
        return f"query:{query.lower().strip()}"
    
    def _classify_by_heuristics(self, query: str) -> QueryClassification:
        """
        Classify query using heuristics as a fallback when AI is unavailable.
        This ensures graceful degradation.
        """
        query_lower = query.lower().strip()
        
        # Check for question patterns
        question_patterns = [
            r'^(what|how|why|when|where|who|which|can|does|is|are)\b',
            r'\?$',
        ]
        is_question = any(re.search(pattern, query_lower) for pattern in question_patterns)
        
        # Check for comparison patterns
        comparison_patterns = [
            r'\b(vs\.?|versus|compared to|compare|difference|between)\b',
            r'\bbetter than\b',
            r'\bvs\b',
        ]
        is_comparison = any(re.search(pattern, query_lower) for pattern in comparison_patterns)
        
        # Check for methodology patterns
        methodology_patterns = [
            r'\bmethod|approach|technique|algorithm|framework|protocol\b',
            r'\bhow to\b',
        ]
        is_methodology = any(re.search(pattern, query_lower) for pattern in methodology_patterns)
        
        # Check for trend/state-of-the-art patterns
        trend_patterns = [
            r'\btrend|state of the art|sota|recent|latest|current\b',
            r'\bsurvey|review|overview\b',
        ]
        is_trend = any(re.search(pattern, query_lower) for pattern in trend_patterns)
        
        # Check for literature review patterns
        literature_patterns = [
            r'\bliterature|review|systematic|meta-analysis\b',
        ]
        is_literature = any(re.search(pattern, query_lower) for pattern in literature_patterns)
        
        # Determine category
        if is_comparison:
            category = "comparison"
            description = "This looks like a comparison between different approaches or methods."
        elif is_methodology:
            category = "methodology"
            description = "This seems to be about a specific methodology or approach."
        elif is_trend:
            category = "trend_analysis"
            description = "You appear to be exploring recent trends or state-of-the-art research."
        elif is_literature:
            category = "literature_review"
            description = "This looks like a literature review or survey request."
        elif is_question:
            category = "research_question"
            description = "This appears to be a specific research question."
        else:
            category = "topic_exploration"
            description = "You seem to be exploring a research topic."
        
        # Determine if clarification is needed based on query length and specificity
        word_count = len(query.split())
        requires_clarification = word_count < 5 or len(query) < 30
        
        return QueryClassification(
            category=category,
            confidence=0.7,  # Moderate confidence for heuristics
            user_friendly_description=description,
            requires_clarification=requires_clarification
        )
    
    def _generate_clarification_questions_by_heuristics(
        self, query: str
    ) -> List[ClarificationQuestion]:
        """Generate clarification questions using heuristics."""
        query_lower = query.lower()
        questions = []
        
        # Extract key terms from query
        words = [w for w in query.split() if len(w) > 3 and w.lower() not in {"the", "and", "for", "with", "from"}]
        key_terms = words[:3] if len(words) >= 3 else words
        
        # Generate generic clarification questions
        if len(key_terms) > 0:
            questions.append(ClarificationQuestion(
                id="focus",
                question="What specific aspect are you most interested in?",
                options=[
                    f"Theoretical foundations of {key_terms[0]}",
                    f"Practical applications of {key_terms[0]}",
                    f"Recent advances in {key_terms[0]}",
                    f"Comparison of approaches",
                ]
            ))
        
        questions.append(ClarificationQuestion(
            id="research_type",
            question="What type of research are you doing?",
            options=[
                "Literature review",
                "New research idea",
                "Method comparison",
                "General exploration",
            ]
        ))
        
        return questions[:2]  # Maximum 2 questions for heuristics
    
    def classify_query(
        self,
        query: str,
        use_cache: bool = True,
        use_ai: bool = True
    ) -> QueryClassificationResult:
        """
        Classify a research query.
        
        Args:
            query: The research query to classify
            use_cache: Whether to use cached results
            use_ai: Whether to use AI for classification (fallback to heuristics if False)
        
        Returns:
            QueryClassificationResult with classification, clarification questions, and research direction
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        cache_key = self._get_cache_key(query)
        
        if use_cache and self._is_cache_valid(cache_key):
            return self._cache[cache_key]
        
        # Classify using heuristics (AI integration can be added later)
        classification = self._classify_by_heuristics(query)
        
        # Generate clarification questions if needed
        clarification_questions = []
        if classification.requires_clarification:
            clarification_questions = self._generate_clarification_questions_by_heuristics(query)
        
        # Generate research direction
        research_direction = ResearchDirection(
            topic=query.strip(),
            focus=None,
            research_intent=classification.user_friendly_description,
            suggested_scope="2020–2026"
        )
        
        result = QueryClassificationResult(
            query=query.strip(),
            classification=classification,
            clarification_questions=clarification_questions,
            research_direction=research_direction
        )
        
        # Cache the result
        if use_cache:
            self._cache[cache_key] = result
        
        return result


# Global service instance
_query_classification_service: Optional[QueryClassificationService] = None


def get_query_classification_service() -> QueryClassificationService:
    """Get the global query classification service instance."""
    global _query_classification_service
    if _query_classification_service is None:
        _query_classification_service = QueryClassificationService()
    return _query_classification_service
