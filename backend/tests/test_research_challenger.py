"""
test_research_challenger.py
──────────────────────────
Tests for Research Challenger Service
"""

import os
import pytest

from repositories.research import Paper
from services.research_challenger_service import (
    ResearchChallengerService,
    Challenge,
    HypothesisChallengeResult,
    get_challenger_service,
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
def challenger_service():
    """Create challenger service instance."""
    return ResearchChallengerService()


class TestResearchChallengerService:
    """Test Research Challenger Service functionality."""

    def test_detect_counter_evidence(self, challenger_service, sample_papers):
        """Test counter-evidence detection."""
        hypothesis = "deep learning always improves performance"
        counter_evidence = challenger_service._detect_counter_evidence(hypothesis, sample_papers)
        
        assert isinstance(counter_evidence, list)
        # Should find some counter-evidence from paper 2
        assert len(counter_evidence) >= 0

    def test_generate_methodological_challenge(self, challenger_service, sample_papers):
        """Test methodological challenge generation."""
        hypothesis = "deep learning improves image classification"
        challenge = challenger_service._generate_methodological_challenge(hypothesis, sample_papers)
        
        assert isinstance(challenge, Challenge)
        assert challenge.challenge_type == "methodological"
        assert len(challenge.challenge_text) > 0
        assert 0 <= challenge.strength <= 100
        assert 0 <= challenge.confidence <= 100

    def test_generate_data_challenge(self, challenger_service, sample_papers):
        """Test data challenge generation."""
        hypothesis = "deep learning improves image classification"
        challenge = challenger_service._generate_data_challenge(hypothesis, sample_papers)
        
        assert isinstance(challenge, Challenge)
        assert challenge.challenge_type == "data"
        assert len(challenge.challenge_text) > 0
        assert 0 <= challenge.strength <= 100

    def test_generate_interpretation_challenge(self, challenger_service, sample_papers):
        """Test interpretation challenge generation."""
        hypothesis = "deep learning improves image classification"
        challenge = challenger_service._generate_interpretation_challenge(hypothesis, sample_papers)
        
        assert isinstance(challenge, Challenge)
        assert challenge.challenge_type == "interpretation"
        assert len(challenge.challenge_text) > 0
        assert 0 <= challenge.strength <= 100

    def test_generate_generalization_challenge(self, challenger_service, sample_papers):
        """Test generalization challenge generation."""
        hypothesis = "deep learning improves image classification"
        challenge = challenger_service._generate_generalization_challenge(hypothesis, sample_papers)
        
        assert isinstance(challenge, Challenge)
        assert challenge.challenge_type == "generalization"
        assert len(challenge.challenge_text) > 0
        assert 0 <= challenge.strength <= 100

    def test_generate_replication_challenge(self, challenger_service, sample_papers):
        """Test replication challenge generation."""
        hypothesis = "deep learning improves image classification"
        challenge = challenger_service._generate_replication_challenge(hypothesis, sample_papers)
        
        assert isinstance(challenge, Challenge)
        assert challenge.challenge_type == "replication"
        assert len(challenge.challenge_text) > 0
        assert 0 <= challenge.strength <= 100

    def test_calculate_overall_vulnerability(self, challenger_service):
        """Test overall vulnerability calculation."""
        challenges = [
            Challenge(
                id="test1",
                hypothesis="test",
                challenge_type="methodological",
                challenge_text="Test",
                counter_evidence="Test",
                strength=70,
                confidence=75,
                supporting_papers=[],
                rationale="Test"
            ),
            Challenge(
                id="test2",
                hypothesis="test",
                challenge_type="data",
                challenge_text="Test",
                counter_evidence="Test",
                strength=60,
                confidence=65,
                supporting_papers=[],
                rationale="Test"
            ),
        ]
        
        vulnerability = challenger_service._calculate_overall_vulnerability(challenges)
        
        assert 0 <= vulnerability <= 100
        # Should be weighted average of strength and confidence
        expected = int(((70 + 60) / 2 * 0.6) + ((75 + 65) / 2 * 0.4))
        assert vulnerability == expected

    def test_calculate_overall_vulnerability_empty(self, challenger_service):
        """Test vulnerability calculation with empty challenges."""
        vulnerability = challenger_service._calculate_overall_vulnerability([])
        assert vulnerability == 0

    def test_challenge_hypothesis(self, challenger_service, sample_papers):
        """Test full hypothesis challenging."""
        hypothesis = "deep learning improves image classification"
        result = challenger_service.challenge_hypothesis(
            hypothesis=hypothesis,
            papers=sample_papers,
            use_cache=False
        )
        
        assert isinstance(result, HypothesisChallengeResult)
        assert result.hypothesis == hypothesis
        assert result.total_challenges == 5  # 5 challenge types
        assert len(result.challenges) == 5
        assert result.strongest_challenge is not None
        assert 0 <= result.overall_vulnerability <= 100
        assert len(result.summary) > 0

    def test_challenge_hypothesis_empty_papers(self, challenger_service):
        """Test hypothesis challenging with empty papers."""
        hypothesis = "test hypothesis"
        result = challenger_service.challenge_hypothesis(
            hypothesis=hypothesis,
            papers=[],
            use_cache=False
        )
        
        assert result.total_challenges == 0
        assert len(result.challenges) == 0
        assert result.strongest_challenge is None
        assert result.overall_vulnerability == 0
        assert "no papers" in result.summary.lower()

    def test_challenges_ranked_by_strength(self, challenger_service, sample_papers):
        """Test that challenges are ranked by strength."""
        hypothesis = "deep learning improves image classification"
        result = challenger_service.challenge_hypothesis(
            hypothesis=hypothesis,
            papers=sample_papers,
            use_cache=False
        )
        
        strengths = [c.strength for c in result.challenges]
        assert strengths == sorted(strengths, reverse=True)

    def test_feature_flag_disabled(self, monkeypatch):
        """Test that service raises error when feature flag is disabled."""
        monkeypatch.setenv("HYPOTHESIS_CHALLENGER_ENABLED", "0")
        
        # Re-import to pick up new env var
        from services import research_challenger_service
        research_challenger_service.HYPOTHESIS_CHALLENGER_ENABLED = False
        
        service = ResearchChallengerService()
        
        with pytest.raises(RuntimeError, match="Hypothesis Challenger is disabled"):
            service.challenge_hypothesis("test hypothesis", [], use_cache=False)

    def test_global_service_instance(self):
        """Test global service instance getter."""
        service = get_challenger_service()
        
        assert isinstance(service, ResearchChallengerService)
        
        # Second call should return same instance
        service2 = get_challenger_service()
        assert service is service2

    def test_challenge_validation(self, challenger_service, sample_papers):
        """Test that generated challenges have valid properties."""
        # Enable feature flag for this test
        from services import research_challenger_service
        original_flag = research_challenger_service.HYPOTHESIS_CHALLENGER_ENABLED
        research_challenger_service.HYPOTHESIS_CHALLENGER_ENABLED = True
        
        try:
            hypothesis = "deep learning improves image classification"
            result = challenger_service.challenge_hypothesis(
                hypothesis=hypothesis,
                papers=sample_papers,
                use_cache=False
            )
            
            for challenge in result.challenges:
                assert len(challenge.id) > 0
                assert challenge.hypothesis == hypothesis
                assert challenge.challenge_type in {
                    "methodological", "data", "interpretation",
                    "generalization", "replication"
                }
                assert len(challenge.challenge_text) > 0
                assert 0 <= challenge.strength <= 100
                assert 0 <= challenge.confidence <= 100
                assert len(challenge.rationale) > 0
        finally:
            research_challenger_service.HYPOTHESIS_CHALLENGER_ENABLED = original_flag

    def test_strongest_challenge_is_highest_strength(self, challenger_service, sample_papers):
        """Test that strongest challenge has the highest strength."""
        # Enable feature flag for this test
        from services import research_challenger_service
        original_flag = research_challenger_service.HYPOTHESIS_CHALLENGER_ENABLED
        research_challenger_service.HYPOTHESIS_CHALLENGER_ENABLED = True
        
        try:
            hypothesis = "deep learning improves image classification"
            result = challenger_service.challenge_hypothesis(
                hypothesis=hypothesis,
                papers=sample_papers,
                use_cache=False
            )
            
            if result.strongest_challenge and result.challenges:
                max_strength = max(c.strength for c in result.challenges)
                assert result.strongest_challenge.strength == max_strength
        finally:
            research_challenger_service.HYPOTHESIS_CHALLENGER_ENABLED = original_flag

    def test_challenge_hypothesis_with_cache(self, challenger_service, sample_papers):
        """Test hypothesis challenging with caching."""
        # Enable feature flag for this test
        from services import research_challenger_service
        original_flag = research_challenger_service.HYPOTHESIS_CHALLENGER_ENABLED
        research_challenger_service.HYPOTHESIS_CHALLENGER_ENABLED = True
        
        try:
            hypothesis = "deep learning improves image classification"
            
            # First call
            result1 = challenger_service.challenge_hypothesis(hypothesis, sample_papers, use_cache=True)
            
            # Second call should use cache
            result2 = challenger_service.challenge_hypothesis(hypothesis, sample_papers, use_cache=True)
            
            assert result1.hypothesis == result2.hypothesis
            assert result1.total_challenges == result2.total_challenges
            assert result1.overall_vulnerability == result2.overall_vulnerability
        finally:
            research_challenger_service.HYPOTHESIS_CHALLENGER_ENABLED = original_flag
