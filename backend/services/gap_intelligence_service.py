"""
gap_intelligence_service.py
───────────────────────────
Gap Intelligence Service for Soyog AI

Upgrades existing gap detection with structured categories,
explainable scores, and comprehensive gap analysis.

This service provides:
- Structured gap categories (methodological, dataset, evaluation, etc.)
- Gap scoring with explainable components
- Evidence-based gap detection
- Integration with existing heuristic gap detection
"""

from __future__ import annotations

import logging
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence
from uuid import uuid4

from repositories.research import Paper
from utils.text_utils import tokenize as _tokenize

logger = logging.getLogger(__name__)

# Feature flag
GAP_INTELLIGENCE_ENABLED = os.getenv(
    "GAP_INTELLIGENCE_ENABLED", "1"
).strip().lower() in {"1", "true", "yes"}

# Dataset and metric terms (from research_agent.py)
_DATASET_TERMS = {
    "cifar-10", "cifar10", "imagenet", "coco", "mnist", "svhn",
    "cityscapes", "kitti", "squad", "glue", "superglue", "mmlu",
    "wikitext", "commoncrawl", "physionet", "mimic-iii", "mimic-iv",
    "librispeech", "kddcup", "nsl-kdd", "unsw-nb15", "ecg",
    "chestxray", "chexpert",
}

_METRIC_TERMS = {
    "accuracy", "f1", "f1-score", "auc", "precision", "recall",
    "specificity", "sensitivity", "rmse", "mae", "mape", "bleu",
    "rouge", "map", "ndcg", "latency", "throughput", "robustness",
    "fairness", "calibration",
}

# Gap categories
_GAP_CATEGORIES = {
    "methodological": "Methodological gaps in experimental design or approach",
    "dataset": "Dataset coverage or diversity gaps",
    "evaluation": "Evaluation metric or benchmark gaps",
    "generalization": "Generalization or cross-domain performance gaps",
    "temporal": "Temporal or longitudinal study gaps",
    "contradiction": "Contradictory findings across studies",
    "reproducibility": "Reproducibility or replication gaps",
    "population": "Population or demographic coverage gaps",
    "benchmark": "Benchmark or baseline comparison gaps",
    "integration": "Integration or multi-modal fusion gaps",
}

# Positive/negative terms for contradiction detection
_POSITIVE_TERMS = {
    "improve", "outperform", "state", "robust", "significant", "effective",
    "achieve", "demonstrate", "show", "prove", "confirm", "support", "validate"
}

_NEGATIVE_TERMS = {
    "limitation", "limited", "challenge", "fail", "bias", "unstable", "uncertain",
    "contradict", "disagree", "refute", "reject", "inconsistent", "weak"
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class StructuredGap:
    category: str  # methodological, dataset, evaluation, etc.
    description: str
    confidence: int  # 0-100
    evidence_count: int
    novelty_potential: int  # 0-100
    research_impact: int  # 0-100
    feasibility: int  # 0-100
    recency: int  # 0-100
    supporting_papers: List[int]
    counter_evidence: List[int]
    affected_papers: List[int]
    explanation: str


@dataclass
class GapScores:
    confidence: int  # 0-100
    novelty_potential: int  # 0-100
    research_impact: int  # 0-100
    feasibility: int  # 0-100
    recency: int  # 0-100
    overall_opportunity: int  # 0-100
    explanation: str


@dataclass
class GapIntelligenceResult:
    topic: str
    gaps_by_category: Dict[str, List[StructuredGap]]
    total_gaps: int
    top_opportunities: List[StructuredGap]
    summary: str
    generated_at: datetime = field(default_factory=_utcnow)


class GapIntelligenceService:
    """Service for gap intelligence analysis."""
    
    def __init__(self):
        self._cache: Dict[str, GapIntelligenceResult] = {}
        self._cache_ttl_seconds = 15 * 60  # 15 minutes
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        if cache_key not in self._cache:
            return False
        cached = self._cache[cache_key]
        age = (datetime.now(timezone.utc) - cached.generated_at).total_seconds()
        return age < self._cache_ttl_seconds
    
    def _get_cache_key(self, topic: str, paper_ids: List[int]) -> str:
        paper_ids_sorted = tuple(sorted(paper_ids))
        return f"{topic}:{paper_ids_sorted}"
    
    def _detect_methodological_gaps(
        self, papers: List[Paper], topic: str
    ) -> List[StructuredGap]:
        """Detect methodological gaps in experimental design."""
        gaps: List[StructuredGap] = []
        
        # Check for lack of ablation studies
        ablation_papers = []
        for paper in papers:
            text = f"{paper.title} {paper.abstract or ''}".lower()
            if "ablation" in text or "ablate" in text:
                ablation_papers.append(paper.id)
        
        if len(ablation_papers) < len(papers) * 0.3:
            gaps.append(StructuredGap(
                category="methodological",
                description="Limited ablation studies across the literature",
                confidence=70,
                evidence_count=len(papers) - len(ablation_papers),
                novelty_potential=75,
                research_impact=80,
                feasibility=65,
                recency=70,
                supporting_papers=[],
                counter_evidence=ablation_papers,
                affected_papers=[p.id for p in papers],
                explanation=f"Only {len(ablation_papers)} out of {len(papers)} papers include ablation studies"
            ))
        
        # Check for lack of cross-validation
        cv_papers = []
        for paper in papers:
            text = f"{paper.title} {paper.abstract or ''}".lower()
            if "cross-validation" in text or "cross validation" in text or "k-fold" in text:
                cv_papers.append(paper.id)
        
        if len(cv_papers) < len(papers) * 0.4:
            gaps.append(StructuredGap(
                category="methodological",
                description="Inconsistent use of cross-validation techniques",
                confidence=65,
                evidence_count=len(papers) - len(cv_papers),
                novelty_potential=60,
                research_impact=70,
                feasibility=75,
                recency=65,
                supporting_papers=[],
                counter_evidence=cv_papers,
                affected_papers=[p.id for p in papers],
                explanation=f"Only {len(cv_papers)} out of {len(papers)} papers use cross-validation"
            ))
        
        return gaps
    
    def _detect_dataset_gaps(
        self, papers: List[Paper], topic: str
    ) -> List[StructuredGap]:
        """Detect dataset coverage gaps."""
        gaps: List[StructuredGap] = []
        
        # Count dataset usage
        dataset_counter = Counter()
        for paper in papers:
            text = f"{paper.title} {paper.abstract or ''}".lower()
            for dataset in _DATASET_TERMS:
                if dataset in text:
                    dataset_counter[dataset] += 1
        
        # Find under-tested datasets
        total_papers = len(papers)
        for dataset, count in dataset_counter.items():
            if count <= 1 and total_papers > 3:
                gaps.append(StructuredGap(
                    category="dataset",
                    description=f"Dataset '{dataset}' is under-tested in the literature",
                    confidence=75,
                    evidence_count=count,
                    novelty_potential=85,
                    research_impact=80,
                    feasibility=70,
                    recency=75,
                    supporting_papers=[],
                    counter_evidence=[],
                    affected_papers=[p.id for p in papers if dataset in f"{p.title} {p.abstract or ''}".lower()],
                    explanation=f"Only {count} papers use {dataset}"
                ))
        
        # Check for lack of dataset diversity
        if len(dataset_counter) < 3 and total_papers > 5:
            gaps.append(StructuredGap(
                category="dataset",
                description="Limited dataset diversity across studies",
                confidence=80,
                evidence_count=len(dataset_counter),
                novelty_potential=70,
                research_impact=75,
                feasibility=60,
                recency=70,
                supporting_papers=[],
                counter_evidence=[],
                affected_papers=[p.id for p in papers],
                explanation=f"Only {len(dataset_counter)} unique datasets used across {total_papers} papers"
            ))
        
        return gaps
    
    def _detect_evaluation_gaps(
        self, papers: List[Paper], topic: str
    ) -> List[StructuredGap]:
        """Detect evaluation metric gaps."""
        gaps: List[StructuredGap] = []
        
        # Count metric usage
        metric_counter = Counter()
        for paper in papers:
            text = f"{paper.title} {paper.abstract or ''}".lower()
            for metric in _METRIC_TERMS:
                if metric in text:
                    metric_counter[metric] += 1
        
        # Find missing metrics
        total_papers = len(papers)
        for metric in _METRIC_TERMS:
            if metric_counter.get(metric, 0) == 0 and total_papers > 2:
                gaps.append(StructuredGap(
                    category="evaluation",
                    description=f"Metric '{metric}' is not reported in the literature",
                    confidence=60,
                    evidence_count=0,
                    novelty_potential=65,
                    research_impact=70,
                    feasibility=75,
                    recency=65,
                    supporting_papers=[],
                    counter_evidence=[],
                    affected_papers=[],
                    explanation=f"No papers report {metric}"
                ))
        
        # Check for lack of comprehensive evaluation
        if len(metric_counter) < 3 and total_papers > 3:
            gaps.append(StructuredGap(
                category="evaluation",
                description="Limited evaluation metrics across studies",
                confidence=70,
                evidence_count=len(metric_counter),
                novelty_potential=75,
                research_impact=80,
                feasibility=65,
                recency=70,
                supporting_papers=[],
                counter_evidence=[],
                affected_papers=[p.id for p in papers],
                explanation=f"Only {len(metric_counter)} unique metrics used across {total_papers} papers"
            ))
        
        return gaps
    
    def _detect_contradiction_gaps(
        self, papers: List[Paper], topic: str
    ) -> List[StructuredGap]:
        """Detect contradictory findings."""
        gaps: List[StructuredGap] = []
        
        # Analyze positive vs negative term usage per concept
        text_blob = " ".join(f"{p.title} {p.abstract or ''}" for p in papers)
        keywords = _tokenize(text_blob)
        
        positive_counter = Counter()
        negative_counter = Counter()
        
        for paper in papers:
            text = f"{paper.title} {paper.abstract or ''}".lower()
            tokens = set(_tokenize(text))
            
            for term in _POSITIVE_TERMS:
                if term in tokens:
                    positive_counter.update(_tokenize(text)[:5])
            for term in _NEGATIVE_TERMS:
                if term in tokens:
                    negative_counter.update(_tokenize(text)[:5])
        
        # Find contradictions
        for concept, pos_count in positive_counter.most_common(10):
            neg_count = negative_counter.get(concept, 0)
            if pos_count > 0 and neg_count > 0:
                gaps.append(StructuredGap(
                    category="contradiction",
                    description=f"Conflicting findings around '{concept}'",
                    confidence=75,
                    evidence_count=pos_count + neg_count,
                    novelty_potential=80,
                    research_impact=85,
                    feasibility=70,
                    recency=75,
                    supporting_papers=[],
                    counter_evidence=[],
                    affected_papers=[p.id for p in papers],
                    explanation=f"Positive mentions: {pos_count}, Negative mentions: {neg_count}"
                ))
        
        return gaps
    
    def _detect_generalization_gaps(
        self, papers: List[Paper], topic: str
    ) -> List[StructuredGap]:
        """Detect generalization gaps."""
        gaps: List[StructuredGap] = []
        
        # Check for cross-domain evaluation
        cross_domain_papers = []
        for paper in papers:
            text = f"{paper.title} {paper.abstract or ''}".lower()
            if any(term in text for term in ["cross-domain", "transfer", "domain adaptation", "generalization"]):
                cross_domain_papers.append(paper.id)
        
        if len(cross_domain_papers) < len(papers) * 0.3:
            gaps.append(StructuredGap(
                category="generalization",
                description="Limited cross-domain generalization evaluation",
                confidence=70,
                evidence_count=len(cross_domain_papers),
                novelty_potential=80,
                research_impact=85,
                feasibility=65,
                recency=75,
                supporting_papers=[],
                counter_evidence=cross_domain_papers,
                affected_papers=[p.id for p in papers],
                explanation=f"Only {len(cross_domain_papers)} out of {len(papers)} papers evaluate generalization"
            ))
        
        return gaps
    
    def _calculate_gap_scores(self, gap: StructuredGap, papers: List[Paper]) -> GapScores:
        """Calculate comprehensive gap scores."""
        # Calculate recency based on affected papers
        now = datetime.now(timezone.utc)
        total_age_days = 0
        
        for paper in papers:
            if paper.id in gap.affected_papers:
                year_match = re.search(r"\b(19|20)\d{2}\b", f"{paper.title} {paper.abstract or ''}")
                if year_match:
                    year = int(year_match.group(0))
                    paper_date = datetime(year, 1, 1, tzinfo=timezone.utc)
                    age_days = (now - paper_date).days
                    total_age_days += age_days
        
        avg_age_days = total_age_days / max(1, len(gap.affected_papers))
        recency_score = max(0, min(100, int(100 - (avg_age_days / 365 * 10))))
        
        # Overall opportunity score (weighted average)
        overall_opportunity = int(
            (gap.novelty_potential * 0.30) +
            (gap.research_impact * 0.30) +
            (gap.feasibility * 0.20) +
            (recency_score * 0.10) +
            (gap.confidence * 0.10)
        )
        
        explanation_parts = []
        if gap.novelty_potential >= 75:
            explanation_parts.append("High novelty potential")
        if gap.research_impact >= 75:
            explanation_parts.append("High research impact")
        if gap.feasibility >= 70:
            explanation_parts.append("High feasibility")
        if recency_score >= 70:
            explanation_parts.append("Recent evidence")
        
        explanation = "; ".join(explanation_parts) if explanation_parts else "Moderate opportunity"
        
        return GapScores(
            confidence=gap.confidence,
            novelty_potential=gap.novelty_potential,
            research_impact=gap.research_impact,
            feasibility=gap.feasibility,
            recency=recency_score,
            overall_opportunity=overall_opportunity,
            explanation=explanation
        )
    
    def analyze_gaps(
        self,
        topic: str,
        papers: List[Paper],
        use_cache: bool = True
    ) -> GapIntelligenceResult:
        """Analyze gaps across multiple categories."""
        if not GAP_INTELLIGENCE_ENABLED:
            raise RuntimeError("Gap Intelligence is disabled. Set GAP_INTELLIGENCE_ENABLED=1 in .env")
        
        paper_ids = [p.id for p in papers]
        cache_key = self._get_cache_key(topic, paper_ids)
        
        if use_cache and self._is_cache_valid(cache_key):
            return self._cache[cache_key]
        
        # Detect gaps by category
        gaps_by_category: Dict[str, List[StructuredGap]] = {
            "methodological": self._detect_methodological_gaps(papers, topic),
            "dataset": self._detect_dataset_gaps(papers, topic),
            "evaluation": self._detect_evaluation_gaps(papers, topic),
            "contradiction": self._detect_contradiction_gaps(papers, topic),
            "generalization": self._detect_generalization_gaps(papers, topic),
        }
        
        # Flatten all gaps
        all_gaps: List[StructuredGap] = []
        for category_gaps in gaps_by_category.values():
            all_gaps.extend(category_gaps)
        
        # Calculate scores for each gap
        for gap in all_gaps:
            scores = self._calculate_gap_scores(gap, papers)
            gap.recency = scores.recency
        
        # Sort by overall opportunity
        all_gaps.sort(key=lambda g: (
            g.novelty_potential + g.research_impact + g.feasibility
        ) // 3, reverse=True)
        
        # Generate summary
        total_gaps = len(all_gaps)
        summary_parts = []
        if total_gaps > 0:
            summary_parts.append(f"Detected {total_gaps} gaps across {len([c for c, g in gaps_by_category.items() if g])} categories")
            top_gap = all_gaps[0]
            summary_parts.append(f"Highest opportunity: {top_gap.description} (category: {top_gap.category})")
        else:
            summary_parts.append("No significant gaps detected")
        
        summary = ". ".join(summary_parts)
        
        result = GapIntelligenceResult(
            topic=topic,
            gaps_by_category=gaps_by_category,
            total_gaps=total_gaps,
            top_opportunities=all_gaps[:5],
            summary=summary
        )
        
        # Cache the result
        self._cache[cache_key] = result
        
        return result


# Global service instance
_gap_service: Optional[GapIntelligenceService] = None


def get_gap_service() -> GapIntelligenceService:
    """Get the global gap intelligence service instance."""
    global _gap_service
    if _gap_service is None:
        _gap_service = GapIntelligenceService()
    return _gap_service
