"""
test_gap_intelligence.py
────────────────────────
Tests for Gap Intelligence Service
"""

import os
import pytest
from datetime import datetime, timezone

from repositories.research import Paper
from services.gap_intelligence_service import (
    GapIntelligenceService,
    StructuredGap,
    GapScores,
    GapIntelligenceResult,
    get_gap_service,
)


@pytest.fixture
def sample_papers():
    """Create sample papers for testing."""
    return [
        Paper(
            id=1,
            workspace_id=1,
            title="Deep Learning Improves Image Classification with Ablation Studies",
            authors="Smith, Johnson",
            abstract="We demonstrate that deep learning models significantly improve image classification accuracy on CIFAR-10 dataset using cross-validation.",
            url="https://example.com/paper1",
            source="arxiv",
        ),
        Paper(
            id=2,
            workspace_id=1,
            title="Limitations of Deep Learning for Small Datasets",
            authors="Brown, Davis",
            abstract="Deep learning models fail to generalize on small datasets due to overfitting and limited data without proper evaluation.",
            url="https://example.com/paper2",
            source="pubmed",
        ),
        Paper(
            id=3,
            workspace_id=1,
            title="Replication Study: Deep Learning on CIFAR-10",
            authors="Wilson, Miller",
            abstract="We replicate the deep learning experiments on CIFAR-10 and confirm the reported improvements using k-fold cross-validation.",
            url="https://example.com/paper3",
            source="openalex",
        ),
    ]


@pytest.fixture
def gap_service():
    """Create gap service instance."""
    return GapIntelligenceService()


class TestGapIntelligenceService:
    """Test Gap Intelligence Service functionality."""

    def test_detect_methodological_gaps(self, gap_service, sample_papers):
        """Test methodological gap detection."""
        gaps = gap_service._detect_methodological_gaps(sample_papers, "deep learning")
        
        assert isinstance(gaps, list)
        assert all(isinstance(g, StructuredGap) for g in gaps)
        assert all(g.category == "methodological" for g in gaps)

    def test_detect_dataset_gaps(self, gap_service, sample_papers):
        """Test dataset gap detection."""
        gaps = gap_service._detect_dataset_gaps(sample_papers, "deep learning")
        
        assert isinstance(gaps, list)
        assert all(isinstance(g, StructuredGap) for g in gaps)
        assert all(g.category == "dataset" for g in gaps)

    def test_detect_evaluation_gaps(self, gap_service, sample_papers):
        """Test evaluation gap detection."""
        gaps = gap_service._detect_evaluation_gaps(sample_papers, "deep learning")
        
        assert isinstance(gaps, list)
        assert all(isinstance(g, StructuredGap) for g in gaps)
        assert all(g.category == "evaluation" for g in gaps)

    def test_detect_contradiction_gaps(self, gap_service, sample_papers):
        """Test contradiction gap detection."""
        gaps = gap_service._detect_contradiction_gaps(sample_papers, "deep learning")
        
        assert isinstance(gaps, list)
        assert all(isinstance(g, StructuredGap) for g in gaps)
        assert all(g.category == "contradiction" for g in gaps)

    def test_detect_generalization_gaps(self, gap_service, sample_papers):
        """Test generalization gap detection."""
        gaps = gap_service._detect_generalization_gaps(sample_papers, "deep learning")
        
        assert isinstance(gaps, list)
        assert all(isinstance(g, StructuredGap) for g in gaps)
        assert all(g.category == "generalization" for g in gaps)

    def test_calculate_gap_scores(self, gap_service, sample_papers):
        """Test gap score calculation."""
        gap = StructuredGap(
            category="methodological",
            description="Test gap",
            confidence=75,
            evidence_count=2,
            novelty_potential=80,
            research_impact=85,
            feasibility=70,
            recency=75,
            supporting_papers=[1],
            counter_evidence=[2],
            affected_papers=[1, 2, 3],
            explanation="Test explanation"
        )
        scores = gap_service._calculate_gap_scores(gap, sample_papers)
        
        assert isinstance(scores, GapScores)
        assert 0 <= scores.confidence <= 100
        assert 0 <= scores.novelty_potential <= 100
        assert 0 <= scores.research_impact <= 100
        assert 0 <= scores.feasibility <= 100
        assert 0 <= scores.recency <= 100
        assert 0 <= scores.overall_opportunity <= 100
        assert len(scores.explanation) > 0

    def test_analyze_gaps(self, gap_service, sample_papers):
        """Test full gap analysis."""
        result = gap_service.analyze_gaps(
            topic="deep learning",
            papers=sample_papers,
            use_cache=False
        )
        
        assert isinstance(result, GapIntelligenceResult)
        assert result.topic == "deep learning"
        assert isinstance(result.gaps_by_category, dict)
        assert result.total_gaps >= 0
        assert isinstance(result.top_opportunities, list)
        assert len(result.summary) > 0

    def test_analyze_gaps_with_cache(self, gap_service, sample_papers):
        """Test gap analysis with caching."""
        topic = "deep learning"
        
        # First call
        result1 = gap_service.analyze_gaps(topic, sample_papers, use_cache=True)
        
        # Second call should use cache
        result2 = gap_service.analyze_gaps(topic, sample_papers, use_cache=True)
        
        assert result1.topic == result2.topic
        assert result1.total_gaps == result2.total_gaps

    def test_feature_flag_disabled(self, monkeypatch):
        """Test that service raises error when feature flag is disabled."""
        monkeypatch.setenv("GAP_INTELLIGENCE_ENABLED", "0")
        
        # Re-import to pick up new env var
        from services import gap_intelligence_service
        gap_intelligence_service.GAP_INTELLIGENCE_ENABLED = False
        
        service = GapIntelligenceService()
        
        with pytest.raises(RuntimeError, match="Gap Intelligence is disabled"):
            service.analyze_gaps("test topic", [], use_cache=False)

    def test_global_service_instance(self):
        """Test global service instance getter."""
        service = get_gap_service()
        
        assert isinstance(service, GapIntelligenceService)
        
        # Second call should return same instance
        service2 = get_gap_service()
        assert service is service2

    def test_empty_papers_handling(self, gap_service):
        """Test handling of empty paper list."""
        with pytest.raises(Exception):
            gap_service.analyze_gaps("test topic", [], use_cache=False)

    def test_gap_categories_coverage(self, gap_service, sample_papers):
        """Test that all gap categories are covered."""
        # Enable feature flag for this test
        from services import gap_intelligence_service
        original_flag = gap_intelligence_service.GAP_INTELLIGENCE_ENABLED
        gap_intelligence_service.GAP_INTELLIGENCE_ENABLED = True
        
        try:
            result = gap_service.analyze_gaps(
                topic="deep learning",
                papers=sample_papers,
                use_cache=False
            )
            
            expected_categories = {
                "methodological", "dataset", "evaluation",
                "contradiction", "generalization"
            }
            
            assert set(result.gaps_by_category.keys()) == expected_categories
        finally:
            gap_intelligence_service.GAP_INTELLIGENCE_ENABLED = original_flag

    def test_top_opportunities_sorted(self, gap_service, sample_papers):
        """Test that top opportunities are sorted by opportunity score."""
        # Enable feature flag for this test
        from services import gap_intelligence_service
        original_flag = gap_intelligence_service.GAP_INTELLIGENCE_ENABLED
        gap_intelligence_service.GAP_INTELLIGENCE_ENABLED = True
        
        try:
            result = gap_service.analyze_gaps(
                topic="deep learning",
                papers=sample_papers,
                use_cache=False
            )
            
            if len(result.top_opportunities) > 1:
                for i in range(len(result.top_opportunities) - 1):
                    current_score = (
                        result.top_opportunities[i].novelty_potential +
                        result.top_opportunities[i].research_impact +
                        result.top_opportunities[i].feasibility
                    ) // 3
                    next_score = (
                        result.top_opportunities[i + 1].novelty_potential +
                        result.top_opportunities[i + 1].research_impact +
                        result.top_opportunities[i + 1].feasibility
                    ) // 3
                    assert current_score >= next_score
        finally:
            gap_intelligence_service.GAP_INTELLIGENCE_ENABLED = original_flag

    def test_structured_gap_validation(self, gap_service, sample_papers):
        """Test that structured gaps have valid scores."""
        # Enable feature flag for this test
        from services import gap_intelligence_service
        original_flag = gap_intelligence_service.GAP_INTELLIGENCE_ENABLED
        gap_intelligence_service.GAP_INTELLIGENCE_ENABLED = True
        
        try:
            result = gap_service.analyze_gaps(
                topic="deep learning",
                papers=sample_papers,
                use_cache=False
            )
            
            for category_gaps in result.gaps_by_category.values():
                for gap in category_gaps:
                    assert 0 <= gap.confidence <= 100
                    assert 0 <= gap.novelty_potential <= 100
                    assert 0 <= gap.research_impact <= 100
                    assert 0 <= gap.feasibility <= 100
                    assert 0 <= gap.recency <= 100
                    assert len(gap.description) > 0
                    assert len(gap.explanation) > 0
        finally:
            gap_intelligence_service.GAP_INTELLIGENCE_ENABLED = original_flag
