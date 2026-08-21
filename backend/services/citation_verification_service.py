"""
citation_verification_service.py
────────────────────────────────
Citation Verification Service for Soyog AI

Verifies citations by checking source quality, accessibility,
and consistency. Ensures research claims are properly supported.

This service provides:
- Citation quality assessment
- Source accessibility verification
- Citation consistency checking
- Citation confidence scoring
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from repositories.research import Paper

logger = logging.getLogger(__name__)

# Feature flag
CITATION_VERIFICATION_ENABLED = os.getenv(
    "CITATION_VERIFICATION_ENABLED", "1"
).strip().lower() in {"1", "true", "yes"}

# Source quality weights (from research_agent.py)
_SOURCE_QUALITY = {
    "openalex": 1.4,
    "semantic_scholar": 1.3,
    "pubmed": 1.2,
    "arxiv": 1.1,
    "crossref": 1.0,
    "unknown": 0.8,
}

# DOI pattern
_DOI_PATTERN = re.compile(r'10\.\d{4,9}/[-._;()/:A-Z0-9]+', re.IGNORECASE)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class CitationVerification:
    paper_id: int
    paper_title: str
    source: str
    doi: str
    url: str
    quality_score: int  # 0-100
    accessibility_score: int  # 0-100
    consistency_score: int  # 0-100
    overall_confidence: int  # 0-100
    issues: List[str]
    recommendations: List[str]


@dataclass
class CitationVerificationResult:
    total_papers: int
    verifications: List[CitationVerification]
    average_quality: int
    average_accessibility: int
    average_consistency: int
    overall_confidence: int
    critical_issues: List[str]
    summary: str
    generated_at: datetime = field(default_factory=_utcnow)


class CitationVerificationService:
    """Service for citation verification."""
    
    def __init__(self):
        self._cache: Dict[str, CitationVerificationResult] = {}
        self._cache_ttl_seconds = 15 * 60  # 15 minutes
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        if cache_key not in self._cache:
            return False
        cached = self._cache[cache_key]
        age = (datetime.now(timezone.utc) - cached.generated_at).total_seconds()
        return age < self._cache_ttl_seconds
    
    def _get_cache_key(self, paper_ids: List[int]) -> str:
        paper_ids_sorted = tuple(sorted(paper_ids))
        return f"{paper_ids_sorted}"
    
    def _calculate_quality_score(self, paper: Paper) -> int:
        """Calculate source quality score."""
        source = (paper.source or "unknown").lower()
        weight = _SOURCE_QUALITY.get(source, _SOURCE_QUALITY["unknown"])
        
        # Normalize to 0-100
        score = int((weight / max(_SOURCE_QUALITY.values())) * 100)
        return max(0, min(100, score))
    
    def _calculate_accessibility_score(self, paper: Paper) -> int:
        """Calculate accessibility score based on URL and DOI."""
        score = 50  # Base score
        
        # Has DOI
        if paper.doi and _DOI_PATTERN.match(paper.doi):
            score += 30
        
        # Has URL
        if paper.url:
            score += 20
        
        # Has full text available
        if paper.full_text_available:
            score += 10
        
        return max(0, min(100, score))
    
    def _calculate_consistency_score(self, paper: Paper) -> int:
        """Calculate consistency score."""
        score = 70  # Base score
        
        # Has both title and abstract
        if paper.title and paper.abstract:
            score += 20
        
        # Has authors
        if paper.authors:
            score += 10
        
        # Check for common inconsistencies
        if paper.title and len(paper.title) < 10:
            score -= 10
        
        if paper.doi and not _DOI_PATTERN.match(paper.doi):
            score -= 15
        
        return max(0, min(100, score))
    
    def _detect_issues(self, paper: Paper, quality: int, accessibility: int, consistency: int) -> List[str]:
        """Detect citation issues."""
        issues: List[str] = []
        
        if quality < 60:
            issues.append(f"Low source quality ({quality}/100)")
        
        if accessibility < 50:
            issues.append(f"Poor accessibility ({accessibility}/100)")
        
        if consistency < 60:
            issues.append(f"Inconsistent metadata ({consistency}/100)")
        
        if not paper.doi:
            issues.append("Missing DOI")
        
        if not paper.url:
            issues.append("Missing URL")
        
        if not paper.abstract or len(paper.abstract) < 50:
            issues.append("Missing or incomplete abstract")
        
        return issues
    
    def _generate_recommendations(self, paper: Paper, issues: List[str]) -> List[str]:
        """Generate recommendations to improve citation quality."""
        recommendations: List[str] = []
        
        if not paper.doi:
            recommendations.append("Add DOI for better citation tracking")
        
        if not paper.url:
            recommendations.append("Add source URL for accessibility")
        
        if not paper.abstract or len(paper.abstract) < 50:
            recommendations.append("Provide complete abstract for better indexing")
        
        if "Low source quality" in " ".join(issues):
            recommendations.append("Consider adding papers from higher-quality sources")
        
        if not recommendations:
            recommendations.append("Citation is well-formatted")
        
        return recommendations
    
    def _calculate_overall_confidence(self, quality: int, accessibility: int, consistency: int) -> int:
        """Calculate overall citation confidence."""
        # Weighted average
        overall = int((quality * 0.4) + (accessibility * 0.3) + (consistency * 0.3))
        return max(0, min(100, overall))
    
    def verify_citations(
        self,
        papers: List[Paper],
        use_cache: bool = True
    ) -> CitationVerificationResult:
        """Verify citations for a list of papers."""
        if not CITATION_VERIFICATION_ENABLED:
            raise RuntimeError(
                "Citation Verification is disabled. Set CITATION_VERIFICATION_ENABLED=1 in .env"
            )
        
        if not papers:
            return CitationVerificationResult(
                total_papers=0,
                verifications=[],
                average_quality=0,
                average_accessibility=0,
                average_consistency=0,
                overall_confidence=0,
                critical_issues=[],
                summary="No papers to verify"
            )
        
        paper_ids = [p.id for p in papers]
        cache_key = self._get_cache_key(paper_ids)
        
        if use_cache and self._is_cache_valid(cache_key):
            return self._cache[cache_key]
        
        # Verify each paper
        verifications: List[CitationVerification] = []
        all_issues: List[str] = []
        
        for paper in papers:
            quality = self._calculate_quality_score(paper)
            accessibility = self._calculate_accessibility_score(paper)
            consistency = self._calculate_consistency_score(paper)
            overall = self._calculate_overall_confidence(quality, accessibility, consistency)
            
            issues = self._detect_issues(paper, quality, accessibility, consistency)
            recommendations = self._generate_recommendations(paper, issues)
            
            all_issues.extend(issues)
            
            verification = CitationVerification(
                paper_id=paper.id,
                paper_title=paper.title,
                source=paper.source or "unknown",
                doi=paper.doi or "",
                url=paper.url or "",
                quality_score=quality,
                accessibility_score=accessibility,
                consistency_score=consistency,
                overall_confidence=overall,
                issues=issues,
                recommendations=recommendations
            )
            verifications.append(verification)
        
        # Calculate averages
        avg_quality = int(sum(v.quality_score for v in verifications) / len(verifications))
        avg_accessibility = int(sum(v.accessibility_score for v in verifications) / len(verifications))
        avg_consistency = int(sum(v.consistency_score for v in verifications) / len(verifications))
        overall_confidence = int(sum(v.overall_confidence for v in verifications) / len(verifications))
        
        # Identify critical issues
        critical_issues = [issue for issue in all_issues if "Missing" in issue or "Poor" in issue]
        
        # Generate summary
        total = len(papers)
        summary = (
            f"Verified {total} citations. "
            f"Average quality: {avg_quality}/100, "
            f"accessibility: {avg_accessibility}/100, "
            f"consistency: {avg_consistency}/100. "
            f"Overall confidence: {overall_confidence}/100. "
            f"Critical issues: {len(critical_issues)}."
        )
        
        result = CitationVerificationResult(
            total_papers=total,
            verifications=verifications,
            average_quality=avg_quality,
            average_accessibility=avg_accessibility,
            average_consistency=avg_consistency,
            overall_confidence=overall_confidence,
            critical_issues=critical_issues,
            summary=summary
        )
        
        # Cache the result
        self._cache[cache_key] = result
        
        return result


# Global service instance
_citation_service: Optional[CitationVerificationService] = None


def get_citation_service() -> CitationVerificationService:
    """Get the global citation verification service instance."""
    global _citation_service
    if _citation_service is None:
        _citation_service = CitationVerificationService()
    return _citation_service
