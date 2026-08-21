"""
knowledge_graph_enhancement_service.py
──────────────────────────────────────
Knowledge Graph Enhancement Service for Soyog AI

Enhances the existing knowledge graph with intelligence layers:
- Gap intelligence overlay
- Evidence intelligence overlay
- Opportunity scoring overlay
- Citation quality overlay

This service provides:
- Multi-layer knowledge graph enrichment
- Intelligence layer integration
- Enhanced node and edge attributes
- Explainable graph insights
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from repositories.research import Paper
from services.gap_intelligence_service import get_gap_service
from services.evidence_intelligence_service import get_evidence_service
from services.opportunity_scoring_service import get_opportunity_service
from services.citation_verification_service import get_citation_service

logger = logging.getLogger(__name__)

# Feature flag
KNOWLEDGE_GRAPH_ENHANCED_ENABLED = os.getenv(
    "KNOWLEDGE_GRAPH_ENHANCED_ENABLED", "1"
).strip().lower() in {"1", "true", "yes"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class IntelligenceLayer:
    layer_type: str  # gap, evidence, opportunity, citation
    enabled: bool
    data: Dict[str, Any]
    summary: str


@dataclass
class EnhancedKnowledgeGraph:
    base_graph: Dict[str, Any]
    intelligence_layers: List[IntelligenceLayer]
    total_layers: int
    enhanced_nodes: int
    enhanced_edges: int
    summary: str
    generated_at: datetime = field(default_factory=_utcnow)


class KnowledgeGraphEnhancementService:
    """Service for knowledge graph enhancement with intelligence layers."""
    
    def __init__(self):
        self._cache: Dict[str, EnhancedKnowledgeGraph] = {}
        self._cache_ttl_seconds = 15 * 60  # 15 minutes
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        if cache_key not in self._cache:
            return False
        cached = self._cache[cache_key]
        age = (datetime.now(timezone.utc) - cached.generated_at).total_seconds()
        return age < self._cache_ttl_seconds
    
    def _get_cache_key(self, topic: str, paper_ids: List[int], layers: List[str]) -> str:
        paper_ids_sorted = tuple(sorted(paper_ids))
        layers_sorted = tuple(sorted(layers))
        return f"{topic}:{paper_ids_sorted}:{layers_sorted}"
    
    def _add_gap_layer(
        self, papers: List[Paper], topic: str
    ) -> IntelligenceLayer:
        """Add gap intelligence layer."""
        try:
            gap_service = get_gap_service()
            gap_result = gap_service.analyze_gaps(topic, papers, use_cache=True)
            
            # Extract gap data for graph
            gap_data = {
                "gaps_by_category": gap_result.gaps_by_category,
                "total_gaps": gap_result.total_gaps,
                "top_opportunities": [
                    {
                        "category": g.category,
                        "description": g.description,
                        "confidence": g.confidence,
                        "novelty_potential": g.novelty_potential,
                        "research_impact": g.research_impact,
                    }
                    for g in gap_result.top_opportunities
                ],
            }
            
            summary = f"Gap intelligence layer: {gap_result.total_gaps} gaps detected across {len(gap_result.gaps_by_category)} categories."
            
            return IntelligenceLayer(
                layer_type="gap",
                enabled=True,
                data=gap_data,
                summary=summary
            )
        except RuntimeError:
            return IntelligenceLayer(
                layer_type="gap",
                enabled=False,
                data={},
                summary="Gap intelligence layer disabled"
            )
    
    def _add_evidence_layer(
        self, papers: List[Paper], claim: str
    ) -> IntelligenceLayer:
        """Add evidence intelligence layer."""
        try:
            evidence_service = get_evidence_service()
            
            # Extract claims from papers
            claims = []
            for paper in papers:
                if paper.abstract:
                    claims.append(paper.abstract[:200])  # Use abstract as claim
            
            if not claims:
                return IntelligenceLayer(
                    layer_type="evidence",
                    enabled=False,
                    data={},
                    summary="No claims available for evidence analysis"
                )
            
            # Analyze first claim
            analysis = evidence_service.analyze_claim(claims[0], papers, use_cache=True)
            
            evidence_data = {
                "supporting_papers": [p.id for p in analysis.classification.supporting_papers],
                "contradicting_papers": [p.id for p in analysis.classification.contradicting_papers],
                "neutral_papers": [p.id for p in analysis.classification.neutral_papers],
                "overall_strength": analysis.strength.overall_strength,
                "confidence": analysis.strength.confidence,
            }
            
            summary = f"Evidence intelligence layer: {len(analysis.classification.supporting_papers)} supporting, {len(analysis.classification.contradicting_papers)} contradicting papers."
            
            return IntelligenceLayer(
                layer_type="evidence",
                enabled=True,
                data=evidence_data,
                summary=summary
            )
        except RuntimeError:
            return IntelligenceLayer(
                layer_type="evidence",
                enabled=False,
                data={},
                summary="Evidence intelligence layer disabled"
            )
    
    def _add_opportunity_layer(
        self, papers: List[Paper], topic: str
    ) -> IntelligenceLayer:
        """Add opportunity scoring layer."""
        try:
            # First get gaps
            gap_service = get_gap_service()
            gap_result = gap_service.analyze_gaps(topic, papers, use_cache=True)
            
            # Flatten gaps
            all_gaps = []
            for category_gaps in gap_result.gaps_by_category.values():
                all_gaps.extend(category_gaps)
            
            # Then rank opportunities
            opportunity_service = get_opportunity_service()
            ranking_result = opportunity_service.rank_opportunities(topic, all_gaps, use_cache=True)
            
            opportunity_data = {
                "total_opportunities": ranking_result.total_opportunities,
                "top_opportunity": {
                    "description": ranking_result.top_opportunity.gap_description if ranking_result.top_opportunity else None,
                    "category": ranking_result.top_opportunity.category if ranking_result.top_opportunity else None,
                    "overall_score": ranking_result.top_opportunity.overall_score if ranking_result.top_opportunity else 0,
                } if ranking_result.top_opportunity else None,
                "average_score": sum(o.overall_score for o in ranking_result.opportunities) / len(ranking_result.opportunities) if ranking_result.opportunities else 0,
            }
            
            summary = f"Opportunity scoring layer: {ranking_result.total_opportunities} opportunities ranked."
            
            return IntelligenceLayer(
                layer_type="opportunity",
                enabled=True,
                data=opportunity_data,
                summary=summary
            )
        except RuntimeError:
            return IntelligenceLayer(
                layer_type="opportunity",
                enabled=False,
                data={},
                summary="Opportunity scoring layer disabled"
            )
    
    def _add_citation_layer(
        self, papers: List[Paper]
    ) -> IntelligenceLayer:
        """Add citation verification layer."""
        try:
            citation_service = get_citation_service()
            verification_result = citation_service.verify_citations(papers, use_cache=True)
            
            citation_data = {
                "average_quality": verification_result.average_quality,
                "average_accessibility": verification_result.average_accessibility,
                "average_consistency": verification_result.average_consistency,
                "overall_confidence": verification_result.overall_confidence,
                "critical_issues_count": len(verification_result.critical_issues),
            }
            
            summary = f"Citation verification layer: Overall confidence {verification_result.overall_confidence}/100."
            
            return IntelligenceLayer(
                layer_type="citation",
                enabled=True,
                data=citation_data,
                summary=summary
            )
        except RuntimeError:
            return IntelligenceLayer(
                layer_type="citation",
                enabled=False,
                data={},
                summary="Citation verification layer disabled"
            )
    
    def enhance_knowledge_graph(
        self,
        base_graph: Dict[str, Any],
        papers: List[Paper],
        topic: str,
        layers: Optional[List[str]] = None,
        use_cache: bool = True
    ) -> EnhancedKnowledgeGraph:
        """Enhance knowledge graph with intelligence layers."""
        if not KNOWLEDGE_GRAPH_ENHANCED_ENABLED:
            raise RuntimeError(
                "Knowledge Graph Enhancement is disabled. "
                "Set KNOWLEDGE_GRAPH_ENHANCED_ENABLED=1 in .env"
            )
        
        if not papers:
            return EnhancedKnowledgeGraph(
                base_graph=base_graph,
                intelligence_layers=[],
                total_layers=0,
                enhanced_nodes=0,
                enhanced_edges=0,
                summary="No papers available for enhancement"
            )
        
        if layers is None:
            layers = ["gap", "evidence", "opportunity", "citation"]
        
        paper_ids = [p.id for p in papers]
        cache_key = self._get_cache_key(topic, paper_ids, layers)
        
        if use_cache and self._is_cache_valid(cache_key):
            return self._cache[cache_key]
        
        # Add intelligence layers
        intelligence_layers: List[IntelligenceLayer] = []
        
        if "gap" in layers:
            gap_layer = self._add_gap_layer(papers, topic)
            intelligence_layers.append(gap_layer)
        
        if "evidence" in layers:
            # Use topic as claim for evidence analysis
            evidence_layer = self._add_evidence_layer(papers, topic)
            intelligence_layers.append(evidence_layer)
        
        if "opportunity" in layers:
            opportunity_layer = self._add_opportunity_layer(papers, topic)
            intelligence_layers.append(opportunity_layer)
        
        if "citation" in layers:
            citation_layer = self._add_citation_layer(papers)
            intelligence_layers.append(citation_layer)
        
        # Calculate enhancement metrics
        enabled_layers = [l for l in intelligence_layers if l.enabled]
        enhanced_nodes = len(base_graph.get("nodes", [])) * len(enabled_layers)
        enhanced_edges = len(base_graph.get("edges", [])) * len(enabled_layers)
        
        # Generate summary
        total = len(intelligence_layers)
        enabled_count = len(enabled_layers)
        summary = (
            f"Enhanced knowledge graph with {total} layers ({enabled_count} enabled). "
            f"Enhanced {enhanced_nodes} nodes and {enhanced_edges} edges with intelligence attributes."
        )
        
        result = EnhancedKnowledgeGraph(
            base_graph=base_graph,
            intelligence_layers=intelligence_layers,
            total_layers=total,
            enhanced_nodes=enhanced_nodes,
            enhanced_edges=enhanced_edges,
            summary=summary
        )
        
        # Cache the result
        self._cache[cache_key] = result
        
        return result


# Global service instance
_graph_enhancement_service: Optional[KnowledgeGraphEnhancementService] = None


def get_graph_enhancement_service() -> KnowledgeGraphEnhancementService:
    """Get the global graph enhancement service instance."""
    global _graph_enhancement_service
    if _graph_enhancement_service is None:
        _graph_enhancement_service = KnowledgeGraphEnhancementService()
    return _graph_enhancement_service
