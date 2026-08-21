"""
test_research_question.py
─────────────────────────
Tests for Research Question Generation Service
"""

import os
import pytest

from repositories.research import StructuredGap
from services.research_question_service import (
    ResearchQuestionService,
    ResearchQuestion,
    QuestionGenerationResult,
    get_question_service,
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
            category="contradiction",
            description="Conflicting findings around deep learning performance",
            confidence=75,
            evidence_count=3,
            novelty_potential=85,
            research_impact=80,
            feasibility=70,
            recency=75,
            supporting_papers=[],
            counter_evidence=[],
            affected_papers=[1, 2],
            explanation="Positive mentions: 5, Negative mentions: 3"
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
    ]


@pytest.fixture
def question_service():
    """Create question service instance."""
    return ResearchQuestionService()


class TestResearchQuestionService:
    """Test Research Question Service functionality."""

    def test_extract_aspect_from_gap(self, question_service, sample_gaps):
        """Test aspect extraction from gap description."""
        for gap in sample_gaps:
            aspect = question_service._extract_aspect_from_gap(gap)
            assert len(aspect) > 0
            assert isinstance(aspect, str)

    def test_determine_question_category(self, question_service, sample_gaps):
        """Test question category determination."""
        for gap in sample_gaps:
            category = question_service._determine_question_category(gap)
            assert category in {"exploratory", "confirmatory", "comparative", "causal"}

    def test_determine_question_category_contradiction(self, question_service):
        """Test that contradiction gaps yield confirmatory questions."""
        gap = StructuredGap(
            category="contradiction",
            description="Test contradiction",
            confidence=70,
            evidence_count=2,
            novelty_potential=75,
            research_impact=80,
            feasibility=65,
            recency=70,
            supporting_papers=[],
            counter_evidence=[],
            affected_papers=[],
            explanation="Test"
        )
        category = question_service._determine_question_category(gap)
        assert category == "confirmatory"

    def test_determine_question_category_dataset(self, question_service):
        """Test that dataset gaps yield comparative questions."""
        gap = StructuredGap(
            category="dataset",
            description="Test dataset",
            confidence=70,
            evidence_count=2,
            novelty_potential=75,
            research_impact=80,
            feasibility=65,
            recency=70,
            supporting_papers=[],
            counter_evidence=[],
            affected_papers=[],
            explanation="Test"
        )
        category = question_service._determine_question_category(gap)
        assert category == "comparative"

    def test_generate_question_from_gap(self, question_service, sample_gaps):
        """Test question generation from a single gap."""
        for idx, gap in enumerate(sample_gaps):
            question = question_service._generate_question_from_gap(gap, "deep learning", idx)
            
            assert isinstance(question, ResearchQuestion)
            assert len(question.question) > 0
            assert question.category in {"exploratory", "confirmatory", "comparative", "causal"}
            assert question.complexity in {"simple", "moderate", "complex"}
            assert 0 <= question.confidence <= 100
            assert 0 <= question.novelty <= 100
            assert 0 <= question.feasibility <= 100
            assert 0 <= question.impact <= 100

    def test_rank_questions(self, question_service, sample_gaps):
        """Test question ranking."""
        questions = [
            question_service._generate_question_from_gap(gap, "deep learning", idx)
            for idx, gap in enumerate(sample_gaps)
        ]
        
        ranked = question_service._rank_questions(questions)
        
        assert len(ranked) == len(questions)
        # Check that scores are in descending order
        scores = [q.novelty * 0.4 + q.impact * 0.4 + q.feasibility * 0.2 for q in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_generate_questions(self, question_service, sample_gaps):
        """Test full question generation."""
        result = question_service.generate_questions(
            topic="deep learning",
            gaps=sample_gaps,
            max_questions=10,
            use_cache=False
        )
        
        assert isinstance(result, QuestionGenerationResult)
        assert result.topic == "deep learning"
        assert result.total_questions == len(sample_gaps)
        assert len(result.questions) == len(sample_gaps)
        assert len(result.top_questions) == min(5, len(sample_gaps))
        assert len(result.summary) > 0

    def test_generate_questions_empty_gaps(self, question_service):
        """Test question generation with empty gaps."""
        result = question_service.generate_questions(
            topic="test",
            gaps=[],
            max_questions=10,
            use_cache=False
        )
        
        assert result.total_questions == 0
        assert len(result.questions) == 0
        assert len(result.top_questions) == 0
        assert "no gaps" in result.summary.lower()

    def test_generate_questions_max_limit(self, question_service, sample_gaps):
        """Test that max_questions limits the output."""
        result = question_service.generate_questions(
            topic="deep learning",
            gaps=sample_gaps,
            max_questions=2,
            use_cache=False
        )
        
        assert result.total_questions <= 2
        assert len(result.questions) <= 2

    def test_feature_flag_disabled(self, monkeypatch):
        """Test that service raises error when feature flag is disabled."""
        monkeypatch.setenv("RESEARCH_QUESTION_GENERATION_ENABLED", "0")
        
        # Re-import to pick up new env var
        from services import research_question_service
        research_question_service.RESEARCH_QUESTION_GENERATION_ENABLED = False
        
        service = ResearchQuestionService()
        
        with pytest.raises(RuntimeError, match="Research Question Generation is disabled"):
            service.generate_questions("test topic", [], use_cache=False)

    def test_global_service_instance(self):
        """Test global service instance getter."""
        service = get_question_service()
        
        assert isinstance(service, ResearchQuestionService)
        
        # Second call should return same instance
        service2 = get_question_service()
        assert service is service2

    def test_question_validation(self, question_service, sample_gaps):
        """Test that generated questions have valid properties."""
        questions = [
            question_service._generate_question_from_gap(gap, "deep learning", idx)
            for idx, gap in enumerate(sample_gaps)
        ]
        
        for q in questions:
            assert len(q.question) > 0
            assert q.category in {"exploratory", "confirmatory", "comparative", "causal"}
            assert q.complexity in {"simple", "moderate", "complex"}
            assert 0 <= q.confidence <= 100
            assert 0 <= q.novelty <= 100
            assert 0 <= q.feasibility <= 100
            assert 0 <= q.impact <= 100
            assert len(q.rationale) > 0
            assert len(q.source_gap_description) > 0

    def test_top_questions_are_highest_ranked(self, question_service, sample_gaps):
        """Test that top questions are the highest ranked."""
        # Enable feature flag for this test
        from services import research_question_service
        original_flag = research_question_service.RESEARCH_QUESTION_GENERATION_ENABLED
        research_question_service.RESEARCH_QUESTION_GENERATION_ENABLED = True
        
        try:
            result = question_service.generate_questions(
                topic="deep learning",
                gaps=sample_gaps,
                max_questions=10,
                use_cache=False
            )
            
            if result.top_questions and result.questions:
                top_scores = [
                    q.novelty * 0.4 + q.impact * 0.4 + q.feasibility * 0.2
                    for q in result.top_questions
                ]
                all_scores = [
                    q.novelty * 0.4 + q.impact * 0.4 + q.feasibility * 0.2
                    for q in result.questions
                ]
                
                # Top questions should be the highest scores
                for top_score in top_scores:
                    assert top_score in all_scores[:len(result.top_questions)]
        finally:
            research_question_service.RESEARCH_QUESTION_GENERATION_ENABLED = original_flag

    def test_generate_questions_with_cache(self, question_service, sample_gaps):
        """Test question generation with caching."""
        # Enable feature flag for this test
        from services import research_question_service
        original_flag = research_question_service.RESEARCH_QUESTION_GENERATION_ENABLED
        research_question_service.RESEARCH_QUESTION_GENERATION_ENABLED = True
        
        try:
            topic = "deep learning"
            
            # First call
            result1 = question_service.generate_questions(topic, sample_gaps, 10, use_cache=True)
            
            # Second call should use cache
            result2 = question_service.generate_questions(topic, sample_gaps, 10, use_cache=True)
            
            assert result1.topic == result2.topic
            assert result1.total_questions == result2.total_questions
        finally:
            research_question_service.RESEARCH_QUESTION_GENERATION_ENABLED = original_flag
