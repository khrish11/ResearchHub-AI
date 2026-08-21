"""
research_intelligence_artifact_service.py
──────────────────────────────────────────
Research Intelligence Artifact Service for Soyog AI

Manages persistent research intelligence artifacts that store
the results of the 7-stage intelligence pipeline.

This service provides:
- Artifact creation and lifecycle management
- Pipeline orchestration (calls existing intelligence services)
- Overall score calculation
- Summary generation
- Partial/failed pipeline handling
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from repositories.research import (
    Paper,
    ResearchIntelligenceArtifact,
    ResearchRepository,
)
from services.evidence_intelligence_service import get_evidence_service
from services.gap_intelligence_service import get_gap_service
from services.opportunity_scoring_service import get_opportunity_service
from services.research_question_service import get_question_service
from services.research_challenger_service import get_challenger_service
from services.citation_verification_service import get_citation_service
from services.knowledge_graph_enhancement_service import get_graph_enhancement_service

logger = logging.getLogger(__name__)

# Feature flag
RESEARCH_INTELLIGENCE_ARTIFACTS_ENABLED = os.getenv(
    "RESEARCH_INTELLIGENCE_ARTIFACTS_ENABLED", "1"
).strip().lower() in {"1", "true", "yes"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ResearchIntelligenceArtifactService:
    """Service for managing research intelligence artifacts."""
    
    def __init__(self, repository: ResearchRepository):
        self.repository = repository
    
    def create_artifact(
        self,
        workspace_id: int,
        user_id: int,
        topic: str,
        paper_ids: List[int],
        pipeline_version: str = "1.0",
    ) -> ResearchIntelligenceArtifact:
        """Create a new research intelligence artifact with running status."""
        if not RESEARCH_INTELLIGENCE_ARTIFACTS_ENABLED:
            raise RuntimeError(
                "Research Intelligence Artifacts are disabled. "
                "Set RESEARCH_INTELLIGENCE_ARTIFACTS_ENABLED=1 in .env"
            )
        
        artifact_id = str(uuid.uuid4())
        return self.repository.create_research_intelligence_artifact(
            id=artifact_id,
            workspace_id=workspace_id,
            user_id=user_id,
            topic=topic,
            paper_ids=paper_ids,
            status="running",
            pipeline_version=pipeline_version,
        )
    
    def get_artifact(self, artifact_id: str) -> Optional[ResearchIntelligenceArtifact]:
        """Retrieve a research intelligence artifact by ID."""
        return self.repository.get_research_intelligence_artifact(artifact_id)
    
    def list_workspace_artifacts(
        self, workspace_id: int, user_id: int
    ) -> List[ResearchIntelligenceArtifact]:
        """List all artifacts for a workspace."""
        return self.repository.list_research_intelligence_artifacts_for_workspace(
            workspace_id, user_id
        )
    
    def delete_artifact(self, artifact_id: str) -> bool:
        """Delete a research intelligence artifact."""
        return self.repository.delete_research_intelligence_artifact(artifact_id)
    
    def execute_pipeline(
        self,
        artifact_id: str,
        papers: List[Paper],
        topic: str,
    ) -> ResearchIntelligenceArtifact:
        """
        Execute the full intelligence pipeline and update the artifact.
        
        This orchestrates the 7 existing intelligence services:
        1. Evidence Analysis
        2. Gap Detection
        3. Opportunity Ranking
        4. Research Question Generation
        5. Hypothesis Challenge
        6. Citation Verification
        7. Knowledge Graph Enhancement
        """
        artifact = self.get_artifact(artifact_id)
        if not artifact:
            raise ValueError(f"Artifact not found: {artifact_id}")
        
        if artifact.status != "running":
            raise ValueError(f"Artifact is not in running state: {artifact.status}")
        
        stage_errors: Dict[str, str] = {}
        
        # Stage 1: Evidence Analysis
        try:
            evidence_service = get_evidence_service()
            evidence_result = evidence_service.analyze_claim(
                claim=topic,
                papers=papers,
                use_cache=True,
            )
            self.repository.update_research_intelligence_artifact(
                artifact_id,
                {"evidence_analysis": self._serialize_evidence_result(evidence_result)},
            )
        except Exception as exc:
            logger.error(f"Evidence analysis failed: {exc}")
            stage_errors["evidence_analysis"] = str(exc)
        
        # Stage 2: Gap Detection
        try:
            gap_service = get_gap_service()
            gap_result = gap_service.analyze_gaps(topic, papers, use_cache=True)
            self.repository.update_research_intelligence_artifact(
                artifact_id,
                {"gap_analysis": self._serialize_gap_result(gap_result)},
            )
        except Exception as exc:
            logger.error(f"Gap analysis failed: {exc}")
            stage_errors["gap_analysis"] = str(exc)
        
        # Stage 3: Opportunity Ranking (requires gap analysis)
        try:
            if not stage_errors.get("gap_analysis"):
                gap_service = get_gap_service()
                gap_result = gap_service.analyze_gaps(topic, papers, use_cache=True)
                all_gaps = []
                for category_gaps in gap_result.gaps_by_category.values():
                    all_gaps.extend(category_gaps)
                
                opportunity_service = get_opportunity_service()
                opportunity_result = opportunity_service.rank_opportunities(
                    topic, all_gaps, use_cache=True
                )
                self.repository.update_research_intelligence_artifact(
                    artifact_id,
                    {"opportunity_ranking": self._serialize_opportunity_result(opportunity_result)},
                )
        except Exception as exc:
            logger.error(f"Opportunity ranking failed: {exc}")
            stage_errors["opportunity_ranking"] = str(exc)
        
        # Stage 4: Research Question Generation
        try:
            question_service = get_question_service()
            question_result = question_service.generate_questions(
                topic, papers, use_cache=True
            )
            self.repository.update_research_intelligence_artifact(
                artifact_id,
                {"research_questions": self._serialize_question_result(question_result)},
            )
        except Exception as exc:
            logger.error(f"Question generation failed: {exc}")
            stage_errors["research_questions"] = str(exc)
        
        # Stage 5: Hypothesis Challenge
        try:
            challenger_service = get_challenger_service()
            challenge_result = challenger_service.challenge_hypothesis(
                hypothesis=topic, papers=papers, use_cache=True
            )
            self.repository.update_research_intelligence_artifact(
                artifact_id,
                {"hypothesis_challenges": self._serialize_challenge_result(challenge_result)},
            )
        except Exception as exc:
            logger.error(f"Hypothesis challenge failed: {exc}")
            stage_errors["hypothesis_challenges"] = str(exc)
        
        # Stage 6: Citation Verification
        try:
            citation_service = get_citation_service()
            citation_result = citation_service.verify_citations(papers)
            self.repository.update_research_intelligence_artifact(
                artifact_id,
                {"citation_verification": self._serialize_citation_result(citation_result)},
            )
        except Exception as exc:
            logger.error(f"Citation verification failed: {exc}")
            stage_errors["citation_verification"] = str(exc)
        
        # Stage 7: Knowledge Graph Enhancement
        try:
            graph_service = get_graph_enhancement_service()
            base_graph = self._build_base_graph(papers)
            graph_result = graph_service.enhance_knowledge_graph(
                base_graph=base_graph,
                papers=papers,
                topic=topic,
                layers=["gap", "evidence", "opportunity", "citation"],
                use_cache=True,
            )
            self.repository.update_research_intelligence_artifact(
                artifact_id,
                {"knowledge_graph": self._serialize_graph_result(graph_result)},
            )
        except Exception as exc:
            logger.error(f"Knowledge graph enhancement failed: {exc}")
            stage_errors["knowledge_graph"] = str(exc)
        
        # Calculate overall score and summary
        updated_artifact = self.get_artifact(artifact_id)
        if updated_artifact:
            overall_score = self._calculate_overall_score(updated_artifact)
            summary = self._generate_summary(updated_artifact, papers)
            
            # Determine final status
            if stage_errors:
                final_status = "partial" if len(stage_errors) < 7 else "failed"
            else:
                final_status = "completed"
            
            self.repository.update_research_intelligence_artifact(
                artifact_id,
                {
                    "status": final_status,
                    "overall_score": overall_score,
                    "summary": summary,
                    "stage_errors": stage_errors if stage_errors else None,
                },
            )
        
        return self.get_artifact(artifact_id) or artifact
    
    def _serialize_evidence_result(self, result: Any) -> Dict[str, Any]:
        """Serialize evidence analysis result."""
        return {
            "claim": result.claim if hasattr(result, 'claim') else None,
            "classification": {
                "supporting_count": len(result.classification.supporting_papers) if hasattr(result, 'classification') else 0,
                "contradicting_count": len(result.classification.contradicting_papers) if hasattr(result, 'classification') else 0,
                "neutral_count": len(result.classification.neutral_papers) if hasattr(result, 'classification') else 0,
            } if hasattr(result, 'classification') else {},
            "strength": {
                "overall_strength": result.strength.overall_strength if hasattr(result, 'strength') else 0,
                "confidence": result.strength.confidence if hasattr(result, 'strength') else "low",
            } if hasattr(result, 'strength') else {},
        }
    
    def _serialize_gap_result(self, result: Any) -> Dict[str, Any]:
        """Serialize gap analysis result."""
        return {
            "total_gaps": result.total_gaps if hasattr(result, 'total_gaps') else 0,
            "top_opportunities": [
                {
                    "category": g.category,
                    "description": g.description,
                    "confidence": g.confidence,
                    "novelty_potential": g.novelty_potential,
                }
                for g in (result.top_opportunities if hasattr(result, 'top_opportunities') else [])
            ],
        }
    
    def _serialize_opportunity_result(self, result: Any) -> Dict[str, Any]:
        """Serialize opportunity ranking result."""
        return {
            "total_opportunities": len(result.opportunities) if hasattr(result, 'opportunities') else 0,
            "top_opportunity": {
                "gap_description": result.top_opportunity.gap_description if hasattr(result, 'top_opportunity') and result.top_opportunity else None,
                "overall_score": result.top_opportunity.overall_score if hasattr(result, 'top_opportunity') and result.top_opportunity else 0,
            } if hasattr(result, 'top_opportunity') and result.top_opportunity else None,
        }
    
    def _serialize_question_result(self, result: Any) -> Dict[str, Any]:
        """Serialize research question result."""
        return {
            "total_questions": len(result.questions) if hasattr(result, 'questions') else 0,
            "top_questions": [
                {
                    "question": q.question,
                    "category": q.category,
                    "complexity": q.complexity,
                }
                for q in (result.top_questions if hasattr(result, 'top_questions') else [])
            ],
        }
    
    def _serialize_challenge_result(self, result: Any) -> Dict[str, Any]:
        """Serialize hypothesis challenge result."""
        return {
            "total_challenges": len(result.challenges) if hasattr(result, 'challenges') else 0,
            "overall_vulnerability": result.overall_vulnerability if hasattr(result, 'overall_vulnerability') else 0,
            "strongest_challenge": {
                "challenge_text": result.strongest_challenge.challenge_text if hasattr(result, 'strongest_challenge') and result.strongest_challenge else None,
                "strength": result.strongest_challenge.strength if hasattr(result, 'strongest_challenge') and result.strongest_challenge else 0,
            } if hasattr(result, 'strongest_challenge') and result.strongest_challenge else None,
        }
    
    def _serialize_citation_result(self, result: Any) -> Dict[str, Any]:
        """Serialize citation verification result."""
        return {
            "total_papers": result.total_papers if hasattr(result, 'total_papers') else 0,
            "average_quality": result.average_quality if hasattr(result, 'average_quality') else 0,
            "average_accessibility": result.average_accessibility if hasattr(result, 'average_accessibility') else 0,
            "overall_confidence": result.overall_confidence if hasattr(result, 'overall_confidence') else 0,
        }
    
    def _serialize_graph_result(self, result: Any) -> Dict[str, Any]:
        """Serialize knowledge graph result."""
        return {
            "total_layers": result.total_layers if hasattr(result, 'total_layers') else 0,
            "enhanced_nodes": result.enhanced_nodes if hasattr(result, 'enhanced_nodes') else 0,
            "enhanced_edges": result.enhanced_edges if hasattr(result, 'enhanced_edges') else 0,
        }
    
    def _build_base_graph(self, papers: List[Paper]) -> Dict[str, Any]:
        """Build a base knowledge graph from papers."""
        nodes = []
        edges = []
        
        for paper in papers:
            nodes.append({
                "id": f"paper_{paper.id}",
                "label": paper.title[:100],
                "type": "paper",
                "metadata": {
                    "authors": paper.authors,
                    "year": paper.id,  # Using ID as proxy for year
                },
            })
        
        # Simple edge creation based on shared authors
        for i, p1 in enumerate(papers):
            for p2 in papers[i+1:]:
                authors1 = set(p1.authors.split(','))
                authors2 = set(p2.authors.split(','))
                if authors1 & authors2:
                    edges.append({
                        "source": f"paper_{p1.id}",
                        "target": f"paper_{p2.id}",
                        "relation": "co_author",
                        "type": "citation",
                    })
        
        return {"nodes": nodes, "edges": edges}
    
    def _calculate_overall_score(self, artifact: ResearchIntelligenceArtifact) -> Optional[int]:
        """
        Calculate overall score from available pipeline results.
        
        Weighted average of available components:
        - Evidence strength (30%)
        - Gap confidence (20%)
        - Opportunity score (25%)
        - Citation integrity (15%)
        - Knowledge graph completeness (10%)
        """
        scores = []
        weights = []
        
        # Evidence strength
        if artifact.evidence_analysis:
            strength = artifact.evidence_analysis.get("strength", {}).get("overall_strength", 0)
            if strength:
                scores.append(strength)
                weights.append(0.30)
        
        # Gap confidence (average of top opportunities)
        if artifact.gap_analysis:
            top_ops = artifact.gap_analysis.get("top_opportunities", [])
            if top_ops:
                avg_confidence = sum(op.get("confidence", 0) for op in top_ops) / len(top_ops)
                scores.append(avg_confidence)
                weights.append(0.20)
        
        # Opportunity score
        if artifact.opportunity_ranking:
            top_opp = artifact.opportunity_ranking.get("top_opportunity", {})
            if top_opp:
                score = top_opp.get("overall_score", 0)
                if score:
                    scores.append(score)
                    weights.append(0.25)
        
        # Citation integrity
        if artifact.citation_verification:
            avg_quality = artifact.citation_verification.get("average_quality", 0)
            if avg_quality:
                scores.append(avg_quality)
                weights.append(0.15)
        
        # Knowledge graph completeness (enhanced nodes as percentage of papers)
        if artifact.knowledge_graph:
            enhanced_nodes = artifact.knowledge_graph.get("enhanced_nodes", 0)
            if artifact.paper_count > 0:
                completeness = min(100, (enhanced_nodes / artifact.paper_count) * 100)
                scores.append(completeness)
                weights.append(0.10)
        
        if not scores:
            return None
        
        # Calculate weighted average
        total_weight = sum(weights)
        weighted_sum = sum(s * w for s, w in zip(scores, weights))
        return int(weighted_sum / total_weight) if total_weight > 0 else None
    
    def _generate_summary(self, artifact: ResearchIntelligenceArtifact, papers: List[Paper]) -> str:
        """Generate a concise summary from pipeline results."""
        parts = []
        
        parts.append(f"Analyzed {artifact.paper_count} papers on '{artifact.topic}'.")
        
        # Evidence
        if artifact.evidence_analysis:
            classification = artifact.evidence_analysis.get("classification", {})
            supporting = classification.get("supporting_count", 0)
            contradicting = classification.get("contradicting_count", 0)
            if supporting > 0 or contradicting > 0:
                parts.append(f"Found {supporting} supporting and {contradicting} contradicting papers.")
        
        # Gaps
        if artifact.gap_analysis:
            total_gaps = artifact.gap_analysis.get("total_gaps", 0)
            if total_gaps > 0:
                parts.append(f"Identified {total_gaps} research gaps.")
        
        # Opportunities
        if artifact.opportunity_ranking:
            total_opp = artifact.opportunity_ranking.get("total_opportunities", 0)
            if total_opp > 0:
                parts.append(f"Ranked {total_opp} research opportunities.")
        
        # Questions
        if artifact.research_questions:
            total_questions = artifact.research_questions.get("total_questions", 0)
            if total_questions > 0:
                parts.append(f"Generated {total_questions} research questions.")
        
        # Challenges
        if artifact.hypothesis_challenges:
            total_challenges = artifact.hypothesis_challenges.get("total_challenges", 0)
            if total_challenges > 0:
                parts.append(f"Identified {total_challenges} hypothesis challenges.")
        
        # Citation
        if artifact.citation_verification:
            avg_quality = artifact.citation_verification.get("average_quality", 0)
            if avg_quality > 0:
                parts.append(f"Citation integrity: {avg_quality}/100.")
        
        # Knowledge graph
        if artifact.knowledge_graph:
            enhanced_nodes = artifact.knowledge_graph.get("enhanced_nodes", 0)
            if enhanced_nodes > 0:
                parts.append(f"Enhanced {enhanced_nodes} nodes in knowledge graph.")
        
        # Recommended action
        if artifact.opportunity_ranking:
            top_opp = artifact.opportunity_ranking.get("top_opportunity", {})
            if top_opp and top_opp.get("gap_description"):
                parts.append(f"Recommended: Investigate '{top_opp['gap_description'][:80]}...'.")
        
        return " ".join(parts)


# Singleton instance
_artifact_service_instance: Optional[ResearchIntelligenceArtifactService] = None


def get_artifact_service(repository: Optional[ResearchRepository] = None) -> ResearchIntelligenceArtifactService:
    """Get or create the artifact service instance."""
    global _artifact_service_instance
    
    if _artifact_service_instance is None:
        from repositories import get_research_repository
        repo = repository or get_research_repository()
        _artifact_service_instance = ResearchIntelligenceArtifactService(repo)
    
    return _artifact_service_instance


def get_artifact_service_instance(repository: Optional[ResearchRepository] = None) -> ResearchIntelligenceArtifactService:
    """Get or create the artifact service instance (alias for compatibility)."""
    return get_artifact_service(repository)
