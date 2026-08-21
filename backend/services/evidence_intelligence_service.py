"""
evidence_intelligence_service.py
────────────────────────────────
Evidence Intelligence Service for Soyog AI

Analyzes research claims against literature to determine evidence strength,
supporting/contradicting papers, and explainable scores.

This service provides:
- Claim extraction and classification
- Evidence classification (supporting/contradicting/neutral)
- Evidence strength scoring with explainability
- Source quality evaluation
- Recency and replication signal analysis
- Evidence-to-passage linking via RAG
"""

from __future__ import annotations

import logging
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Sequence
from uuid import uuid4

from repositories.research import Paper
from utils.text_utils import tokenize as _tokenize

logger = logging.getLogger(__name__)

# Feature flag
EVIDENCE_INTELLIGENCE_ENABLED = os.getenv(
    "EVIDENCE_INTELLIGENCE_ENABLED", "1"
).strip().lower() in {"1", "true", "yes"}

# Source quality weights (from research_agent.py)
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

# Positive/negative terms for evidence classification
_POSITIVE_TERMS = {
    "improve", "outperform", "state", "robust", "significant", "effective",
    "achieve", "demonstrate", "show", "prove", "confirm", "support", "validate"
}

_NEGATIVE_TERMS = {
    "limitation", "limited", "challenge", "fail", "bias", "unstable", "uncertain",
    "contradict", "disagree", "refute", "reject", "inconsistent", "weak"
}

# Replication indicators
_REPLICATION_TERMS = {
    "replicate", "reproduce", "reproduction", "replication", "reproducible",
    "confirm", "validate", "verify", "independent", "external"
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Claim:
    text: str
    source_paper_id: Optional[int] = None
    confidence: float = 0.0


@dataclass
class EvidenceClassification:
    claim: str
    supporting_papers: List[Paper]
    contradicting_papers: List[Paper]
    neutral_papers: List[Paper]
    insufficient_evidence: bool


@dataclass
class EvidencePassage:
    paper_id: int
    paper_title: str
    passage_text: str
    relevance_score: float
    evidence_type: str  # "supporting" | "contradicting" | "neutral"


@dataclass
class EvidenceStrength:
    support_count: int
    contradiction_count: int
    neutral_count: int
    source_quality_score: int  # 0-100
    recency_score: int  # 0-100
    replication_signal: int  # 0-100
    overall_strength: int  # 0-100
    confidence: str  # "high" | "medium" | "low"
    explanation: str


@dataclass
class EvidenceAnalysis:
    claim: str
    classification: EvidenceClassification
    strength: EvidenceStrength
    passages: List[EvidencePassage]
    evidence_type: str  # "observed" | "inferred" | "ai_generated"
    generated_at: datetime = field(default_factory=_utcnow)


class EvidenceIntelligenceService:
    """Service for evidence intelligence analysis."""
    
    def __init__(self):
        self._cache: Dict[str, EvidenceAnalysis] = {}
        self._cache_ttl_seconds = 30 * 60  # 30 minutes
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        if cache_key not in self._cache:
            return False
        cached = self._cache[cache_key]
        age = (datetime.now(timezone.utc) - cached.generated_at).total_seconds()
        return age < self._cache_ttl_seconds
    
    def _get_cache_key(self, claim: str, paper_ids: List[int]) -> str:
        paper_ids_sorted = tuple(sorted(paper_ids))
        return f"{claim}:{paper_ids_sorted}"
    
    def _extract_claims_from_papers(
        self, papers: List[Paper], topic: Optional[str] = None
    ) -> List[Claim]:
        """Extract potential claims from paper abstracts."""
        claims: List[Claim] = []
        claim_patterns = [
            r"(?:we|this study|this paper|our work) (?:demonstrate|show|prove|establish|find|reveal) that (.+?)(?:\.|;|$)",
            r"(?:the|our) (?:results|findings|analysis) (?:show|demonstrate|indicate|suggest) that (.+?)(?:\.|;|$)",
            r"(?:we|this study) (?:propose|present|introduce) (.+?)(?:\.|;|$)",
        ]
        
        for paper in papers:
            text = f"{paper.title} {paper.abstract or ''}"
            for pattern in claim_patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    claim_text = match.group(1).strip()
                    if len(claim_text) > 20 and len(claim_text) < 300:
                        claims.append(Claim(
                            text=claim_text,
                            source_paper_id=paper.id,
                            confidence=0.7
                        ))
        
        # If topic provided, create a synthetic claim
        if topic and not claims:
            claims.append(Claim(
                text=f"Research on {topic} shows significant improvements",
                source_paper_id=None,
                confidence=0.5
            ))
        
        return claims[:10]  # Limit to top 10 claims
    
    def _classify_evidence(
        self, papers: List[Paper], claim: Claim
    ) -> EvidenceClassification:
        """Classify papers as supporting, contradicting, or neutral for a claim."""
        claim_tokens = set(_tokenize(claim.text.lower()))
        supporting: List[Paper] = []
        contradicting: List[Paper] = []
        neutral: List[Paper] = []
        
        for paper in papers:
            text = f"{paper.title} {paper.abstract or ''}".lower()
            tokens = set(_tokenize(text))
            
            # Calculate overlap
            overlap = len(claim_tokens & tokens)
            positive_hits = sum(1 for term in _POSITIVE_TERMS if term in tokens)
            negative_hits = sum(1 for term in _NEGATIVE_TERMS if term in tokens)
            
            if overlap < 2:
                neutral.append(paper)
            elif positive_hits > negative_hits:
                supporting.append(paper)
            elif negative_hits > positive_hits:
                contradicting.append(paper)
            else:
                neutral.append(paper)
        
        return EvidenceClassification(
            claim=claim.text,
            supporting_papers=supporting,
            contradicting_papers=contradicting,
            neutral_papers=neutral,
            insufficient_evidence=len(papers) < 3
        )
    
    def _calculate_source_quality(
        self, papers: List[Paper]
    ) -> int:
        """Calculate source quality score (0-100)."""
        if not papers:
            return 0
        
        total_weight = 0.0
        total_papers = len(papers)
        
        for paper in papers:
            source = str(paper.source or "unknown").lower()
            weight = _SOURCE_QUALITY.get(source, 1.0)
            total_weight += weight
        
        avg_weight = total_weight / max(1, total_papers)
        # Normalize to 0-100 (assuming max weight ~1.4)
        score = min(100, int((avg_weight / 1.4) * 100))
        return max(0, score)
    
    def _calculate_recency_score(
        self, papers: List[Paper]
    ) -> int:
        """Calculate recency score (0-100)."""
        if not papers:
            return 0
        
        now = datetime.now(timezone.utc)
        total_age_days = 0
        
        for paper in papers:
            # Try to extract year from title/abstract
            year_match = re.search(r"\b(19|20)\d{2}\b", f"{paper.title} {paper.abstract or ''}")
            if year_match:
                year = int(year_match.group(0))
                paper_date = datetime(year, 1, 1, tzinfo=timezone.utc)
                age_days = (now - paper_date).days
                total_age_days += age_days
        
        if not papers:
            return 0
        
        avg_age_days = total_age_days / len(papers)
        # Newer papers get higher scores (0-5 years = 100, 10+ years = 0)
        score = max(0, min(100, int(100 - (avg_age_days / 365 * 10))))
        return score
    
    def _calculate_replication_signal(
        self, papers: List[Paper]
    ) -> int:
        """Calculate replication signal (0-100)."""
        if not papers:
            return 0
        
        replication_count = 0
        for paper in papers:
            text = f"{paper.title} {paper.abstract or ''}".lower()
            if any(term in text for term in _REPLICATION_TERMS):
                replication_count += 1
        
        # Score based on percentage of papers mentioning replication
        ratio = replication_count / len(papers)
        return min(100, int(ratio * 100))
    
    def _calculate_evidence_strength(
        self, classification: EvidenceClassification, papers: List[Paper]
    ) -> EvidenceStrength:
        """Calculate overall evidence strength with explainable scores."""
        support_count = len(classification.supporting_papers)
        contradiction_count = len(classification.contradicting_papers)
        neutral_count = len(classification.neutral_papers)
        total_papers = len(papers)
        
        # Calculate component scores
        source_quality = self._calculate_source_quality(papers)
        recency_score = self._calculate_recency_score(papers)
        replication_signal = self._calculate_replication_signal(papers)
        
        # Calculate net evidence strength
        # More supporting papers = higher strength
        # More contradictions = lower strength
        net_support = support_count - contradiction_count
        evidence_ratio = (net_support / max(1, total_papers)) if total_papers > 0 else 0
        
        # Overall strength formula
        # 40% evidence ratio, 25% source quality, 20% recency, 15% replication
        overall_strength = int(
            (evidence_ratio * 40) +
            (source_quality * 0.25) +
            (recency_score * 0.20) +
            (replication_signal * 0.15)
        )
        overall_strength = max(0, min(100, overall_strength))
        
        # Determine confidence level
        if overall_strength >= 75:
            confidence = "high"
        elif overall_strength >= 50:
            confidence = "medium"
        else:
            confidence = "low"
        
        # Generate explanation
        explanation_parts = []
        if support_count > 0:
            explanation_parts.append(f"{support_count} papers support this claim")
        if contradiction_count > 0:
            explanation_parts.append(f"{contradiction_count} papers contradict this claim")
        if neutral_count > 0:
            explanation_parts.append(f"{neutral_count} papers are neutral")
        
        explanation = "; ".join(explanation_parts) if explanation_parts else "Insufficient evidence"
        
        return EvidenceStrength(
            support_count=support_count,
            contradiction_count=contradiction_count,
            neutral_count=neutral_count,
            source_quality_score=source_quality,
            recency_score=recency_score,
            replication_signal=replication_signal,
            overall_strength=overall_strength,
            confidence=confidence,
            explanation=explanation
        )
    
    def _link_evidence_to_passages(
        self, classification: EvidenceClassification, claim: str
    ) -> List[EvidencePassage]:
        """Link evidence to relevant passages (simplified version)."""
        passages: List[EvidencePassage] = []
        claim_tokens = set(_tokenize(claim.lower()))
        
        # Add supporting paper passages
        for paper in classification.supporting_papers[:5]:
            text = f"{paper.title} {paper.abstract or ''}"
            tokens = set(_tokenize(text.lower()))
            overlap = len(claim_tokens & tokens)
            if overlap >= 2:
                # Extract relevant sentence (simplified)
                sentences = re.split(r"[.!?]", text)
                best_sentence = max(
                    sentences,
                    key=lambda s: len(set(_tokenize(s.lower())) & claim_tokens),
                    default=text[:200]
                )
                passages.append(EvidencePassage(
                    paper_id=paper.id,
                    paper_title=paper.title,
                    passage_text=best_sentence[:300],
                    relevance_score=min(1.0, overlap / len(claim_tokens)),
                    evidence_type="supporting"
                ))
        
        # Add contradicting paper passages
        for paper in classification.contradicting_papers[:3]:
            text = f"{paper.title} {paper.abstract or ''}"
            tokens = set(_tokenize(text.lower()))
            overlap = len(claim_tokens & tokens)
            if overlap >= 2:
                sentences = re.split(r"[.!?]", text)
                best_sentence = max(
                    sentences,
                    key=lambda s: len(set(_tokenize(s.lower())) & claim_tokens),
                    default=text[:200]
                )
                passages.append(EvidencePassage(
                    paper_id=paper.id,
                    paper_title=paper.title,
                    passage_text=best_sentence[:300],
                    relevance_score=min(1.0, overlap / len(claim_tokens)),
                    evidence_type="contradicting"
                ))
        
        return passages[:10]  # Limit to top 10 passages
    
    def analyze_claim(
        self,
        claim: str,
        papers: List[Paper],
        use_cache: bool = True
    ) -> EvidenceAnalysis:
        """Analyze a research claim against papers."""
        if not EVIDENCE_INTELLIGENCE_ENABLED:
            raise RuntimeError("Evidence Intelligence is disabled. Set EVIDENCE_INTELLIGENCE_ENABLED=1 in .env")
        
        paper_ids = [p.id for p in papers]
        cache_key = self._get_cache_key(claim, paper_ids)
        
        if use_cache and self._is_cache_valid(cache_key):
            return self._cache[cache_key]
        
        claim_obj = Claim(text=claim, confidence=0.8)
        classification = self._classify_evidence(papers, claim_obj)
        strength = self._calculate_evidence_strength(classification, papers)
        passages = self._link_evidence_to_passages(classification, claim)
        
        # Determine evidence type
        evidence_type = "observed" if classification.supporting_papers else "inferred"
        if not papers:
            evidence_type = "ai_generated"
        
        analysis = EvidenceAnalysis(
            claim=claim,
            classification=classification,
            strength=strength,
            passages=passages,
            evidence_type=evidence_type
        )
        
        # Cache the result
        self._cache[cache_key] = analysis
        
        return analysis
    
    def analyze_topic(
        self,
        topic: str,
        papers: List[Paper],
        use_cache: bool = True
    ) -> List[EvidenceAnalysis]:
        """Analyze multiple claims extracted from a topic."""
        if not EVIDENCE_INTELLIGENCE_ENABLED:
            raise RuntimeError("Evidence Intelligence is disabled. Set EVIDENCE_INTELLIGENCE_ENABLED=1 in .env")
        
        claims = self._extract_claims_from_papers(papers, topic)
        
        # If no claims extracted, create a synthetic claim from topic
        if not claims:
            claims = [Claim(text=f"Research on {topic}", confidence=0.5)]
        
        analyses: List[EvidenceAnalysis] = []
        for claim in claims:
            try:
                analysis = self.analyze_claim(claim.text, papers, use_cache)
                analyses.append(analysis)
            except Exception as e:
                logger.warning(f"Failed to analyze claim '{claim.text}': {e}")
        
        return analyses[:5]  # Limit to top 5 analyses


# Global service instance
_evidence_service: Optional[EvidenceIntelligenceService] = None


def get_evidence_service() -> EvidenceIntelligenceService:
    """Get the global evidence intelligence service instance."""
    global _evidence_service
    if _evidence_service is None:
        _evidence_service = EvidenceIntelligenceService()
    return _evidence_service
