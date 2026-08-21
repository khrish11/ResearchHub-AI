"""
test_evidence_intelligence.py
────────────────────────────
Tests for Evidence Intelligence Service
"""

import os
import pytest
from datetime import datetime, timezone

from repositories.research import Paper
from services.evidence_intelligence_service import (
    EvidenceIntelligenceService,
    EvidenceClassification,
    EvidenceStrength,
    EvidenceAnalysis,
    Claim,
    get_evidence_service,
)


@pytest.fixture
def sample_papers():
    """Create sample papers for testing."""
    return [
        Paper(
            id=1,
            workspace_id=1,
            title="Deep Learning Improves Image Classification",
            authors="Smith, Johnson",
            abstract="We demonstrate that deep learning models significantly improve image classification accuracy on CIFAR-10 dataset.",
            url="https://example.com/paper1",
            source="arxiv",
        ),
        Paper(
            id=2,
            workspace_id=1,
            title="Limitations of Deep Learning for Small Datasets",
            authors="Brown, Davis",
            abstract="Deep learning models fail to generalize on small datasets due to overfitting and limited data.",
            url="https://example.com/paper2",
            source="pubmed",
        ),
        Paper(
            id=3,
            workspace_id=1,
            title="Replication Study: Deep Learning on CIFAR-10",
            authors="Wilson, Miller",
            abstract="We replicate the deep learning experiments on CIFAR-10 and confirm the reported improvements.",
            url="https://example.com/paper3",
            source="openalex",
        ),
    ]


@pytest.fixture
def evidence_service():
    """Create evidence service instance."""
    return EvidenceIntelligenceService()


class TestEvidenceIntelligenceService:
    """Test Evidence Intelligence Service functionality."""

    def test_extract_claims_from_papers(self, evidence_service, sample_papers):
        """Test claim extraction from papers."""
        claims = evidence_service._extract_claims_from_papers(sample_papers, "deep learning")
        
        assert len(claims) > 0
        assert all(isinstance(c, Claim) for c in claims)
        assert all(len(c.text) > 20 for c in claims)

    def test_extract_claims_with_topic(self, evidence_service, sample_papers):
        """Test claim extraction with topic fallback."""
        claims = evidence_service._extract_claims_from_papers(sample_papers, "machine learning")
        
        # Should have at least synthetic claim from topic
        assert len(claims) > 0

    def test_classify_evidence_supporting(self, evidence_service, sample_papers):
        """Test evidence classification for supporting claim."""
        claim = Claim(text="deep learning improves image classification", confidence=0.8)
        classification = evidence_service._classify_evidence(sample_papers, claim)
        
        assert isinstance(classification, EvidenceClassification)
        assert classification.claim == claim.text
        assert len(classification.supporting_papers) > 0

    def test_classify_evidence_contradicting(self, evidence_service, sample_papers):
        """Test evidence classification for contradicting claim."""
        claim = Claim(text="deep learning fails on all datasets", confidence=0.8)
        classification = evidence_service._classify_evidence(sample_papers, claim)
        
        assert isinstance(classification, EvidenceClassification)
        # Should have at least some neutral or contradicting papers
        assert len(classification.neutral_papers) > 0 or len(classification.contradicting_papers) > 0

    def test_calculate_source_quality(self, evidence_service, sample_papers):
        """Test source quality calculation."""
        score = evidence_service._calculate_source_quality(sample_papers)
        
        assert 0 <= score <= 100
        assert isinstance(score, int)

    def test_calculate_recency_score(self, evidence_service, sample_papers):
        """Test recency score calculation."""
        score = evidence_service._calculate_recency_score(sample_papers)
        
        assert 0 <= score <= 100
        assert isinstance(score, int)

    def test_calculate_replication_signal(self, evidence_service, sample_papers):
        """Test replication signal calculation."""
        score = evidence_service._calculate_replication_signal(sample_papers)
        
        assert 0 <= score <= 100
        assert isinstance(score, int)

    def test_calculate_evidence_strength(self, evidence_service, sample_papers):
        """Test evidence strength calculation."""
        claim = Claim(text="deep learning improves image classification", confidence=0.8)
        classification = evidence_service._classify_evidence(sample_papers, claim)
        strength = evidence_service._calculate_evidence_strength(classification, sample_papers)
        
        assert isinstance(strength, EvidenceStrength)
        assert 0 <= strength.overall_strength <= 100
        assert strength.confidence in {"high", "medium", "low"}
        assert len(strength.explanation) > 0

    def test_link_evidence_to_passages(self, evidence_service, sample_papers):
        """Test evidence-to-passage linking."""
        claim = Claim(text="deep learning improves image classification", confidence=0.8)
        classification = evidence_service._classify_evidence(sample_papers, claim)
        passages = evidence_service._link_evidence_to_passages(classification, claim.text)
        
        assert isinstance(passages, list)
        assert all(p.paper_id in [1, 2, 3] for p in passages)
        assert all(p.evidence_type in {"supporting", "contradicting", "neutral"} for p in passages)

    def test_analyze_claim(self, evidence_service, sample_papers):
        """Test full claim analysis."""
        analysis = evidence_service.analyze_claim(
            claim="deep learning improves image classification",
            papers=sample_papers,
            use_cache=False
        )
        
        assert isinstance(analysis, EvidenceAnalysis)
        assert analysis.claim == "deep learning improves image classification"
        assert isinstance(analysis.classification, EvidenceClassification)
        assert isinstance(analysis.strength, EvidenceStrength)
        assert analysis.evidence_type in {"observed", "inferred", "ai_generated"}

    def test_analyze_claim_with_cache(self, evidence_service, sample_papers):
        """Test claim analysis with caching."""
        claim = "deep learning improves image classification"
        
        # First call
        analysis1 = evidence_service.analyze_claim(claim, sample_papers, use_cache=True)
        
        # Second call should use cache
        analysis2 = evidence_service.analyze_claim(claim, sample_papers, use_cache=True)
        
        assert analysis1.claim == analysis2.claim
        assert analysis1.strength.overall_strength == analysis2.strength.overall_strength

    def test_analyze_topic(self, evidence_service, sample_papers):
        """Test topic-based analysis."""
        analyses = evidence_service.analyze_topic(
            topic="deep learning",
            papers=sample_papers,
            use_cache=False
        )
        
        assert isinstance(analyses, list)
        assert len(analyses) > 0
        assert all(isinstance(a, EvidenceAnalysis) for a in analyses)

    def test_feature_flag_disabled(self, monkeypatch):
        """Test that service raises error when feature flag is disabled."""
        monkeypatch.setenv("EVIDENCE_INTELLIGENCE_ENABLED", "0")
        
        # Re-import to pick up new env var
        from services import evidence_intelligence_service
        evidence_intelligence_service.EVIDENCE_INTELLIGENCE_ENABLED = False
        
        service = EvidenceIntelligenceService()
        
        with pytest.raises(RuntimeError, match="Evidence Intelligence is disabled"):
            service.analyze_claim("test claim", [], use_cache=False)

    def test_global_service_instance(self):
        """Test global service instance getter."""
        service = get_evidence_service()
        
        assert isinstance(service, EvidenceIntelligenceService)
        
        # Second call should return same instance
        service2 = get_evidence_service()
        assert service is service2

    def test_empty_papers_handling(self, evidence_service):
        """Test handling of empty paper list."""
        with pytest.raises(Exception):
            evidence_service.analyze_claim("test claim", [], use_cache=False)

    def test_insufficient_evidence(self, evidence_service, sample_papers):
        """Test insufficient evidence detection."""
        # Use only one paper
        single_paper = sample_papers[:1]
        claim = Claim(text="deep learning improves image classification", confidence=0.8)
        classification = evidence_service._classify_evidence(single_paper, claim)
        
        assert classification.insufficient_evidence is True
