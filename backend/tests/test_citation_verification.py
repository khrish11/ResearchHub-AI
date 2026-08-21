"""
test_citation_verification.py
────────────────────────────
Tests for Citation Verification Service
"""

import os
import pytest

from repositories.research import Paper
from services.citation_verification_service import (
    CitationVerificationService,
    CitationVerification,
    CitationVerificationResult,
    get_citation_service,
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
            doi="10.1234/example.doi",
        ),
        Paper(
            id=2,
            workspace_id=1,
            title="Limitations of Deep Learning",
            authors="Brown, Davis",
            abstract="Short abstract",
            url="https://example.com/paper2",
            source="pubmed",
            doi="",
        ),
        Paper(
            id=3,
            workspace_id=1,
            title="Replication Study",
            authors="Wilson, Miller",
            abstract="We replicate the deep learning experiments on CIFAR-10 and confirm the reported improvements.",
            url="",
            source="openalex",
            doi="10.5678/another.doi",
        ),
    ]


@pytest.fixture
def citation_service():
    """Create citation service instance."""
    return CitationVerificationService()


class TestCitationVerificationService:
    """Test Citation Verification Service functionality."""

    def test_calculate_quality_score(self, citation_service, sample_papers):
        """Test quality score calculation."""
        for paper in sample_papers:
            score = citation_service._calculate_quality_score(paper)
            assert 0 <= score <= 100
            assert isinstance(score, int)

    def test_calculate_quality_score_arxiv(self, citation_service):
        """Test quality score for arXiv source."""
        paper = Paper(
            id=1,
            workspace_id=1,
            title="Test",
            authors="Test",
            abstract="Test abstract",
            url="https://arxiv.org/test",
            source="arxiv",
            doi="10.1234/test",
        )
        score = citation_service._calculate_quality_score(paper)
        assert score > 70  # arXiv should have good quality

    def test_calculate_quality_score_unknown(self, citation_service):
        """Test quality score for unknown source."""
        paper = Paper(
            id=1,
            workspace_id=1,
            title="Test",
            authors="Test",
            abstract="Test abstract",
            url="https://example.com/test",
            source="unknown",
            doi="",
        )
        score = citation_service._calculate_quality_score(paper)
        assert score < 80  # unknown source should have lower quality

    def test_calculate_accessibility_score(self, citation_service, sample_papers):
        """Test accessibility score calculation."""
        for paper in sample_papers:
            score = citation_service._calculate_accessibility_score(paper)
            assert 0 <= score <= 100
            assert isinstance(score, int)

    def test_calculate_accessibility_score_with_doi(self, citation_service):
        """Test accessibility score with DOI."""
        paper = Paper(
            id=1,
            workspace_id=1,
            title="Test",
            authors="Test",
            abstract="Test abstract",
            url="https://example.com/test",
            source="arxiv",
            doi="10.1234/test.doi",
        )
        score = citation_service._calculate_accessibility_score(paper)
        assert score >= 80  # DOI should boost accessibility

    def test_calculate_accessibility_score_without_doi(self, citation_service):
        """Test accessibility score without DOI."""
        paper = Paper(
            id=1,
            workspace_id=1,
            title="Test",
            authors="Test",
            abstract="Test abstract",
            url="https://example.com/test",
            source="arxiv",
            doi="",
        )
        score = citation_service._calculate_accessibility_score(paper)
        assert score < 80  # Missing DOI should reduce accessibility

    def test_calculate_consistency_score(self, citation_service, sample_papers):
        """Test consistency score calculation."""
        for paper in sample_papers:
            score = citation_service._calculate_consistency_score(paper)
            assert 0 <= score <= 100
            assert isinstance(score, int)

    def test_calculate_consistency_score_complete(self, citation_service):
        """Test consistency score for complete paper."""
        paper = Paper(
            id=1,
            workspace_id=1,
            title="Complete Paper Title",
            authors="Author One, Author Two",
            abstract="Complete abstract with sufficient length for testing purposes",
            url="https://example.com/test",
            source="arxiv",
            doi="10.1234/test.doi",
        )
        score = citation_service._calculate_consistency_score(paper)
        assert score >= 80  # Complete metadata should have high consistency

    def test_detect_issues(self, citation_service):
        """Test issue detection."""
        paper = Paper(
            id=1,
            workspace_id=1,
            title="Test",
            authors="Test",
            abstract="Short",
            url="",
            source="unknown",
            doi="",
        )
        issues = citation_service._detect_issues(paper, 50, 40, 50)
        
        assert isinstance(issues, list)
        assert len(issues) > 0  # Should detect issues

    def test_detect_issues_no_issues(self, citation_service):
        """Test issue detection with no issues."""
        paper = Paper(
            id=1,
            workspace_id=1,
            title="Complete Paper Title",
            authors="Author One, Author Two",
            abstract="Complete abstract with sufficient length for testing purposes",
            url="https://example.com/test",
            source="arxiv",
            doi="10.1234/test.doi",
        )
        issues = citation_service._detect_issues(paper, 90, 90, 90)
        
        # Should have few or no issues
        assert len(issues) <= 1

    def test_generate_recommendations(self, citation_service):
        """Test recommendation generation."""
        paper = Paper(
            id=1,
            workspace_id=1,
            title="Test",
            authors="Test",
            abstract="Short",
            url="",
            source="unknown",
            doi="",
        )
        issues = ["Missing DOI", "Missing URL"]
        recommendations = citation_service._generate_recommendations(paper, issues)
        
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0

    def test_calculate_overall_confidence(self, citation_service):
        """Test overall confidence calculation."""
        confidence = citation_service._calculate_overall_confidence(80, 70, 75)
        assert 0 <= confidence <= 100
        # Weighted average: 80*0.4 + 70*0.3 + 75*0.3 = 75.5
        assert confidence == 75

    def test_verify_citations(self, citation_service, sample_papers):
        """Test full citation verification."""
        result = citation_service.verify_citations(
            papers=sample_papers,
            use_cache=False
        )
        
        assert isinstance(result, CitationVerificationResult)
        assert result.total_papers == len(sample_papers)
        assert len(result.verifications) == len(sample_papers)
        assert 0 <= result.average_quality <= 100
        assert 0 <= result.average_accessibility <= 100
        assert 0 <= result.average_consistency <= 100
        assert 0 <= result.overall_confidence <= 100
        assert len(result.summary) > 0

    def test_verify_citations_empty_papers(self, citation_service):
        """Test citation verification with empty papers."""
        result = citation_service.verify_citations(
            papers=[],
            use_cache=False
        )
        
        assert result.total_papers == 0
        assert len(result.verifications) == 0
        assert result.average_quality == 0
        assert result.average_accessibility == 0
        assert result.average_consistency == 0
        assert result.overall_confidence == 0
        assert "no papers" in result.summary.lower()

    def test_feature_flag_disabled(self, monkeypatch):
        """Test that service raises error when feature flag is disabled."""
        monkeypatch.setenv("CITATION_VERIFICATION_ENABLED", "0")
        
        # Re-import to pick up new env var
        from services import citation_verification_service
        citation_verification_service.CITATION_VERIFICATION_ENABLED = False
        
        service = CitationVerificationService()
        
        with pytest.raises(RuntimeError, match="Citation Verification is disabled"):
            service.verify_citations([], use_cache=False)

    def test_global_service_instance(self):
        """Test global service instance getter."""
        service = get_citation_service()
        
        assert isinstance(service, CitationVerificationService)
        
        # Second call should return same instance
        service2 = get_citation_service()
        assert service is service2

    def test_verification_validation(self, citation_service, sample_papers):
        """Test that verifications have valid properties."""
        # Enable feature flag for this test
        from services import citation_verification_service
        original_flag = citation_verification_service.CITATION_VERIFICATION_ENABLED
        citation_verification_service.CITATION_VERIFICATION_ENABLED = True
        
        try:
            result = citation_service.verify_citations(
                papers=sample_papers,
                use_cache=False
            )
            
            for verification in result.verifications:
                assert verification.paper_id > 0
                assert len(verification.paper_title) > 0
                assert len(verification.source) > 0
                assert 0 <= verification.quality_score <= 100
                assert 0 <= verification.accessibility_score <= 100
                assert 0 <= verification.consistency_score <= 100
                assert 0 <= verification.overall_confidence <= 100
                assert isinstance(verification.issues, list)
                assert isinstance(verification.recommendations, list)
        finally:
            citation_verification_service.CITATION_VERIFICATION_ENABLED = original_flag

    def test_critical_issues_detection(self, citation_service):
        """Test critical issues detection."""
        # Enable feature flag for this test
        from services import citation_verification_service
        original_flag = citation_verification_service.CITATION_VERIFICATION_ENABLED
        citation_verification_service.CITATION_VERIFICATION_ENABLED = True
        
        try:
            papers = [
                Paper(
                    id=1,
                    workspace_id=1,
                    title="Test",
                    authors="Test",
                    abstract="Short",
                    url="",
                    source="unknown",
                    doi="",
                ),
            ]
            result = citation_service.verify_citations(papers, use_cache=False)
            
            # Should detect critical issues
            assert len(result.critical_issues) > 0
        finally:
            citation_verification_service.CITATION_VERIFICATION_ENABLED = original_flag

    def test_verify_citations_with_cache(self, citation_service, sample_papers):
        """Test citation verification with caching."""
        # Enable feature flag for this test
        from services import citation_verification_service
        original_flag = citation_verification_service.CITATION_VERIFICATION_ENABLED
        citation_verification_service.CITATION_VERIFICATION_ENABLED = True
        
        try:
            # First call
            result1 = citation_service.verify_citations(sample_papers, use_cache=True)
            
            # Second call should use cache
            result2 = citation_service.verify_citations(sample_papers, use_cache=True)
            
            assert result1.total_papers == result2.total_papers
            assert result1.average_quality == result2.average_quality
            assert result1.overall_confidence == result2.overall_confidence
        finally:
            citation_verification_service.CITATION_VERIFICATION_ENABLED = original_flag
