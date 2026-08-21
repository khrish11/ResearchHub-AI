"""
test_opportunity_scoring.py
───────────────────────────
Tests for Research Opportunity Scoring Service
"""

import os
import pytest

from repositories.research import StructuredGap
from services.opportunity_scoring_service import (
    OpportunityScoringService,
    ResearchOpportunity,
    OpportunityComparison,
    OpportunityRankingResult,
    get_opportunity_service,
)


@pytest.fixture
def sample_gaps():
    """Create sample gaps for testing."""
    return [
        StructuredGap(
            category="methodological",
            description="Limited ablation studies across the literature",
            confidence=70,
            evidence_count=2,
            novelty_potential=75,
            research_impact=80,
            feasibility=65,
            recency=70,
            supporting_papers=[],
            counter_evidence=[1],
            affected_papers=[1, 2, 3],
            explanation="Only 1 out of 3 papers include ablation studies"
        ),
        StructuredGap(
            category="dataset",
            description="Dataset 'CIFAR-10' is under-tested in the literature",
            confidence=75,
            evidence_count=1,
            novelty_potential=85,
            research_impact=80,
            feasibility=70,
            recency=75,
            supporting_papers=[],
            counter_evidence=[],
            affected_papers=[1],
            explanation="Only 1 papers use CIFAR-10"
        ),
        StructuredGap(
            category="evaluation",
            description="Limited evaluation metrics across studies",
            confidence=70,
            evidence_count=3,
            novelty_potential=75,
            research_impact=80,
            feasibility=65,
            recency=70,
            supporting_papers=[],
            counter_evidence=[],
            affected_papers=[1, 2, 3],
            explanation="Only 2 unique metrics used across 3 papers"
        ),
    ]


@pytest.fixture
def opportunity_service():
    """Create opportunity service instance."""
    return OpportunityScoringService()


class TestOpportunityScoringService:
    """Test Opportunity Scoring Service functionality."""

    def test_calculate_opportunity_score(self, opportunity_service, sample_gaps):
        """Test opportunity score calculation."""
        for gap in sample_gaps:
            score = opportunity_service._calculate_opportunity_score(gap)
            assert 0 <= score <= 100
            assert isinstance(score, int)

    def test_calculate_opportunity_score_weights(self, opportunity_service):
        """Test that scoring uses correct weights."""
        # High novelty, impact, feasibility should yield high score
        high_gap = StructuredGap(
            category="methodological",
            description="High opportunity gap",
            confidence=90,
            evidence_count=5,
            novelty_potential=90,
            research_impact=90,
            feasibility=90,
            recency=90,
            supporting_papers=[],
            counter_evidence=[],
            affected_papers=[],
            explanation="High opportunity"
        )
        
        # Low scores should yield low score
        low_gap = StructuredGap(
            category="methodological",
            description="Low opportunity gap",
            confidence=30,
            evidence_count=1,
            novelty_potential=30,
            research_impact=30,
            feasibility=30,
            recency=30,
            supporting_papers=[],
            counter_evidence=[],
            affected_papers=[],
            explanation="Low opportunity"
        )
        
        high_score = opportunity_service._calculate_opportunity_score(high_gap)
        low_score = opportunity_service._calculate_opportunity_score(low_gap)
        
        assert high_score > low_score
        assert high_score > 70
        assert low_score < 50

    def test_generate_explanation(self, opportunity_service, sample_gaps):
        """Test explanation generation."""
        for gap in sample_gaps:
            score = opportunity_service._calculate_opportunity_score(gap)
            explanation = opportunity_service._generate_explanation(gap, score)
            
            assert len(explanation) > 0
            assert "score" in explanation.lower()

    def test_rank_gaps(self, opportunity_service, sample_gaps):
        """Test gap ranking."""
        opportunities = opportunity_service._rank_gaps(sample_gaps)
        
        assert isinstance(opportunities, list)
        assert len(opportunities) == len(sample_gaps)
        assert all(isinstance(o, ResearchOpportunity) for o in opportunities)
        
        # Check that ranks are sequential
        ranks = [o.rank for o in opportunities]
        assert ranks == sorted(ranks)
        
        # Check that scores are in descending order
        scores = [o.overall_score for o in opportunities]
        assert scores == sorted(scores, reverse=True)

    def test_compare_opportunities(self, opportunity_service, sample_gaps):
        """Test opportunity comparison matrix."""
        opportunities = opportunity_service._rank_gaps(sample_gaps)
        comparisons = opportunity_service._compare_opportunities(opportunities)
        
        assert isinstance(comparisons, list)
        
        # Should have comparisons for top 3 opportunities
        if len(opportunities) >= 2:
            assert len(comparisons) > 0
            assert all(isinstance(c, OpportunityComparison) for c in comparisons)

    def test_rank_opportunities(self, opportunity_service, sample_gaps):
        """Test full opportunity ranking."""
        result = opportunity_service.rank_opportunities(
            topic="deep learning",
            gaps=sample_gaps,
            use_cache=False
        )
        
        assert isinstance(result, OpportunityRankingResult)
        assert result.topic == "deep learning"
        assert result.total_opportunities == len(sample_gaps)
        assert len(result.opportunities) == len(sample_gaps)
        assert result.top_opportunity is not None
        assert len(result.summary) > 0

    def test_rank_opportunities_empty_gaps(self, opportunity_service):
        """Test ranking with empty gaps."""
        result = opportunity_service.rank_opportunities(
            topic="test",
            gaps=[],
            use_cache=False
        )
        
        assert result.total_opportunities == 0
        assert result.top_opportunity is None
        assert "no gaps" in result.summary.lower()

    def test_feature_flag_disabled(self, monkeypatch):
        """Test that service raises error when feature flag is disabled."""
        monkeypatch.setenv("OPPORTUNITY_SCORING_ENABLED", "0")
        
        # Re-import to pick up new env var
        from services import opportunity_scoring_service
        opportunity_scoring_service.OPPORTUNITY_SCORING_ENABLED = False
        
        service = OpportunityScoringService()
        
        with pytest.raises(RuntimeError, match="Opportunity Scoring is disabled"):
            service.rank_opportunities("test topic", [], use_cache=False)

    def test_global_service_instance(self):
        """Test global service instance getter."""
        service = get_opportunity_service()
        
        assert isinstance(service, OpportunityScoringService)
        
        # Second call should return same instance
        service2 = get_opportunity_service()
        assert service is service2

    def test_opportunity_validation(self, opportunity_service, sample_gaps):
        """Test that opportunities have valid scores."""
        opportunities = opportunity_service._rank_gaps(sample_gaps)
        
        for opp in opportunities:
            assert 0 <= opp.evidence_strength <= 100
            assert 0 <= opp.novelty <= 100
            assert 0 <= opp.impact <= 100
            assert 0 <= opp.feasibility <= 100
            assert 0 <= opp.recency <= 100
            assert 0 <= opp.overall_score <= 100
            assert opp.rank > 0
            assert len(opp.gap_description) > 0
            assert len(opp.explanation) > 0

    def test_top_opportunity_is_highest_scored(self, opportunity_service, sample_gaps):
        """Test that top opportunity has the highest score."""
        # Enable feature flag for this test
        from services import opportunity_scoring_service
        original_flag = opportunity_scoring_service.OPPORTUNITY_SCORING_ENABLED
        opportunity_scoring_service.OPPORTUNITY_SCORING_ENABLED = True
        
        try:
            result = opportunity_service.rank_opportunities(
                topic="deep learning",
                gaps=sample_gaps,
                use_cache=False
            )
            
            if result.top_opportunity and result.opportunities:
                top_score = result.top_opportunity.overall_score
                max_score = max(o.overall_score for o in result.opportunities)
                assert top_score == max_score
        finally:
            opportunity_scoring_service.OPPORTUNITY_SCORING_ENABLED = original_flag

    def test_comparison_matrix_recommendations(self, opportunity_service, sample_gaps):
        """Test that comparison matrix provides recommendations."""
        opportunities = opportunity_service._rank_gaps(sample_gaps)
        comparisons = opportunity_service._compare_opportunities(opportunities)
        
        for comp in comparisons:
            assert len(comp.comparison) > 0
            assert len(comp.recommendation) > 0
            assert "prioritize" in comp.recommendation.lower()

    def test_rank_opportunities_with_cache(self, opportunity_service, sample_gaps):
        """Test opportunity ranking with caching."""
        # Enable feature flag for this test
        from services import opportunity_scoring_service
        original_flag = opportunity_scoring_service.OPPORTUNITY_SCORING_ENABLED
        opportunity_scoring_service.OPPORTUNITY_SCORING_ENABLED = True
        
        try:
            topic = "deep learning"
            
            # First call
            result1 = opportunity_service.rank_opportunities(topic, sample_gaps, use_cache=True)
            
            # Second call should use cache
            result2 = opportunity_service.rank_opportunities(topic, sample_gaps, use_cache=True)
            
            assert result1.topic == result2.topic
            assert result1.total_opportunities == result2.total_opportunities
        finally:
            opportunity_scoring_service.OPPORTUNITY_SCORING_ENABLED = original_flag
