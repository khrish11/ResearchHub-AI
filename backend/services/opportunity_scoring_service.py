"""
opportunity_scoring_service.py
──────────────────────────────
Research Opportunity Scoring Service for Soyog AI

Ranks research gaps by opportunity potential using weighted scoring.
Integrates with Gap Intelligence to provide actionable research opportunities.

This service provides:
- Gap ranking by overall opportunity score
- Weighted scoring (novelty, impact, feasibility, recency)
- Comparison matrix for opportunities
- Explainable scoring rationale
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from repositories.research import StructuredGap, ResearchOpportunity
from services.gap_intelligence_service import get_gap_service

logger = logging.getLogger(__name__)

# Feature flag
OPPORTUNITY_SCORING_ENABLED = os.getenv(
    "OPPORTUNITY_SCORING_ENABLED", "1"
).strip().lower() in {"1", "true", "yes"}

# Scoring weights
_EVIDENCE_STRENGTH_WEIGHT = 0.25
_NOVELTY_WEIGHT = 0.25
_IMPACT_WEIGHT = 0.25
_FEASIBILITY_WEIGHT = 0.15
_RECENCY_WEIGHT = 0.10


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class OpportunityComparison:
    opportunity_1: ResearchOpportunity
    opportunity_2: ResearchOpportunity
    comparison: str
    recommendation: str


@dataclass
class OpportunityRankingResult:
    topic: str
    opportunities: List[ResearchOpportunity]
    total_opportunities: int
    top_opportunity: Optional[ResearchOpportunity]
    comparison_matrix: List[OpportunityComparison]
    summary: str
    generated_at: datetime = field(default_factory=_utcnow)


class OpportunityScoringService:
    """Service for research opportunity scoring and ranking."""
    
    def __init__(self):
        self._cache: Dict[str, OpportunityRankingResult] = {}
        self._cache_ttl_seconds = 10 * 60  # 10 minutes
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        if cache_key not in self._cache:
            return False
        cached = self._cache[cache_key]
        age = (datetime.now(timezone.utc) - cached.generated_at).total_seconds()
        return age < self._cache_ttl_seconds
    
    def _get_cache_key(self, topic: str, paper_ids: List[int]) -> str:
        paper_ids_sorted = tuple(sorted(paper_ids))
        return f"{topic}:{paper_ids_sorted}"
    
    def _calculate_opportunity_score(self, gap: StructuredGap) -> int:
        """Calculate overall opportunity score for a gap."""
        # Weighted scoring formula
        overall_score = int(
            (gap.evidence_count * _EVIDENCE_STRENGTH_WEIGHT) +
            (gap.novelty_potential * _NOVELTY_WEIGHT) +
            (gap.research_impact * _IMPACT_WEIGHT) +
            (gap.feasibility * _FEASIBILITY_WEIGHT) +
            (gap.recency * _RECENCY_WEIGHT)
        )
        
        # Normalize evidence_count to 0-100 range (assuming max 10 papers)
        evidence_normalized = min(100, gap.evidence_count * 10)
        
        # Recalculate with normalized evidence
        overall_score = int(
            (evidence_normalized * _EVIDENCE_STRENGTH_WEIGHT) +
            (gap.novelty_potential * _NOVELTY_WEIGHT) +
            (gap.research_impact * _IMPACT_WEIGHT) +
            (gap.feasibility * _FEASIBILITY_WEIGHT) +
            (gap.recency * _RECENCY_WEIGHT)
        )
        
        return max(0, min(100, overall_score))
    
    def _generate_explanation(self, gap: StructuredGap, score: int) -> str:
        """Generate explainable scoring rationale."""
        parts = []
        
        if gap.novelty_potential >= 75:
            parts.append(f"High novelty potential ({gap.novelty_potential})")
        if gap.research_impact >= 75:
            parts.append(f"High research impact ({gap.research_impact})")
        if gap.feasibility >= 70:
            parts.append(f"High feasibility ({gap.feasibility})")
        if gap.recency >= 70:
            parts.append(f"Recent evidence ({gap.recency})")
        if gap.evidence_count >= 3:
            parts.append(f"Strong evidence base ({gap.evidence_count} papers)")
        
        if not parts:
            parts.append("Moderate opportunity across all dimensions")
        
        explanation = "; ".join(parts) + f". Overall score: {score}/100."
        return explanation
    
    def _rank_gaps(self, gaps: List[StructuredGap]) -> List[ResearchOpportunity]:
        """Rank gaps by opportunity score."""
        opportunities: List[ResearchOpportunity] = []
        
        for idx, gap in enumerate(gaps):
            score = self._calculate_opportunity_score(gap)
            explanation = self._generate_explanation(gap, score)
            
            opportunity = ResearchOpportunity(
                gap_id=f"gap_{idx}",
                gap_description=gap.description,
                category=gap.category,
                evidence_strength=min(100, gap.evidence_count * 10),
                novelty=gap.novelty_potential,
                impact=gap.research_impact,
                feasibility=gap.feasibility,
                recency=gap.recency,
                overall_score=score,
                rank=0,  # Will be set after sorting
                explanation=explanation,
                supporting_papers=gap.supporting_papers,
                affected_papers=gap.affected_papers,
            )
            opportunities.append(opportunity)
        
        # Sort by overall score
        opportunities.sort(key=lambda o: o.overall_score, reverse=True)
        
        # Assign ranks
        for rank, opportunity in enumerate(opportunities, start=1):
            opportunity.rank = rank
        
        return opportunities
    
    def _compare_opportunities(
        self, opportunities: List[ResearchOpportunity]
    ) -> List[OpportunityComparison]:
        """Generate comparison matrix for top opportunities."""
        comparisons: List[OpportunityComparison] = []
        
        # Compare top 3 opportunities pairwise
        top_opportunities = opportunities[:3]
        
        for i in range(len(top_opportunities)):
            for j in range(i + 1, len(top_opportunities)):
                opp1 = top_opportunities[i]
                opp2 = top_opportunities[j]
                
                # Generate comparison text
                if opp1.overall_score > opp2.overall_score:
                    diff = opp1.overall_score - opp2.overall_score
                    comparison = (
                        f"{opp1.gap_description} ranks higher than "
                        f"{opp2.gap_description} by {diff} points. "
                        f"Key advantage: "
                    )
                    
                    # Identify key advantage
                    if opp1.novelty > opp2.novelty:
                        comparison += f"higher novelty ({opp1.novelty} vs {opp2.novelty})"
                    elif opp1.impact > opp2.impact:
                        comparison += f"higher impact ({opp1.impact} vs {opp2.impact})"
                    elif opp1.feasibility > opp2.feasibility:
                        comparison += f"higher feasibility ({opp1.feasibility} vs {opp2.feasibility})"
                    else:
                        comparison += "better overall balance"
                    
                    recommendation = f"Prioritize {opp1.gap_description} over {opp2.gap_description}"
                else:
                    diff = opp2.overall_score - opp1.overall_score
                    comparison = (
                        f"{opp2.gap_description} ranks higher than "
                        f"{opp1.gap_description} by {diff} points. "
                        f"Key advantage: "
                    )
                    
                    if opp2.novelty > opp1.novelty:
                        comparison += f"higher novelty ({opp2.novelty} vs {opp1.novelty})"
                    elif opp2.impact > opp1.impact:
                        comparison += f"higher impact ({opp2.impact} vs {opp1.impact})"
                    elif opp2.feasibility > opp1.feasibility:
                        comparison += f"higher feasibility ({opp2.feasibility} vs {opp1.feasibility})"
                    else:
                        comparison += "better overall balance"
                    
                    recommendation = f"Prioritize {opp2.gap_description} over {opp1.gap_description}"
                
                comparisons.append(OpportunityComparison(
                    opportunity_1=opp1,
                    opportunity_2=opp2,
                    comparison=comparison,
                    recommendation=recommendation
                ))
        
        return comparisons
    
    def rank_opportunities(
        self,
        topic: str,
        gaps: List[StructuredGap],
        use_cache: bool = True
    ) -> OpportunityRankingResult:
        """Rank research opportunities from gaps."""
        if not OPPORTUNITY_SCORING_ENABLED:
            raise RuntimeError("Opportunity Scoring is disabled. Set OPPORTUNITY_SCORING_ENABLED=1 in .env")
        
        if not gaps:
            return OpportunityRankingResult(
                topic=topic,
                opportunities=[],
                total_opportunities=0,
                top_opportunity=None,
                comparison_matrix=[],
                summary="No gaps detected to rank as opportunities"
            )
        
        # Rank gaps
        opportunities = self._rank_gaps(gaps)
        
        # Generate comparison matrix
        comparisons = self._compare_opportunities(opportunities)
        
        # Generate summary
        total = len(opportunities)
        top = opportunities[0] if opportunities else None
        
        if top:
            summary = (
                f"Identified {total} research opportunities. "
                f"Top opportunity: {top.gap_description} "
                f"(rank #{top.rank}, score {top.overall_score}/100). "
                f"Category: {top.category}."
            )
        else:
            summary = "No significant research opportunities identified"
        
        return OpportunityRankingResult(
            topic=topic,
            opportunities=opportunities,
            total_opportunities=total,
            top_opportunity=top,
            comparison_matrix=comparisons,
            summary=summary
        )
    
    def rank_opportunities_from_workspace(
        self,
        topic: str,
        paper_ids: List[int],
        use_cache: bool = True
    ) -> OpportunityRankingResult:
        """Rank opportunities by first running gap intelligence."""
        if not OPPORTUNITY_SCORING_ENABLED:
            raise RuntimeError("Opportunity Scoring is disabled. Set OPPORTUNITY_SCORING_ENABLED=1 in .env")
        
        # This would require access to papers and gap service
        # For now, raise NotImplementedError as this needs integration
        raise NotImplementedError(
            "Use rank_opportunities with pre-computed gaps, "
            "or integrate with gap_intelligence_service directly"
        )


# Global service instance
_opportunity_service: Optional[OpportunityScoringService] = None


def get_opportunity_service() -> OpportunityScoringService:
    """Get the global opportunity scoring service instance."""
    global _opportunity_service
    if _opportunity_service is None:
        _opportunity_service = OpportunityScoringService()
    return _opportunity_service
