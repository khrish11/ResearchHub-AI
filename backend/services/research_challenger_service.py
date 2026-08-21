"""
research_challenger_service.py
──────────────────────────────
Research Challenger Service for Soyog AI

Challenges research hypotheses and claims by finding counter-evidence
and alternative explanations. Critical for robust research validation.

This service provides:
- Hypothesis challenge generation
- Counter-evidence identification
- Alternative explanation generation
- Challenge strength scoring
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from repositories.research import Paper
from utils.text_utils import tokenize as _tokenize

logger = logging.getLogger(__name__)

# Feature flag
HYPOTHESIS_CHALLENGER_ENABLED = os.getenv(
    "HYPOTHESIS_CHALLENGER_ENABLED", "1"
).strip().lower() in {"1", "true", "yes"}

# Challenge types
_CHALLENGE_TYPES = {
    "methodological": "Methodological limitations or biases",
    "data": "Data limitations or inconsistencies",
    "interpretation": "Alternative interpretations of results",
    "generalization": "Generalization or external validity concerns",
    "replication": "Replication or reproducibility issues",
}

# Counter-evidence indicators
_COUNTER_INDICATORS = {
    "contradict", "fail", "limit", "bias", "inconsistent", "weak",
    "unreliable", "overfit", "underperform", "disagree"
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Challenge:
    id: str
    hypothesis: str
    challenge_type: str  # methodological, data, interpretation, generalization, replication
    challenge_text: str
    counter_evidence: str
    strength: int  # 0-100
    confidence: int  # 0-100
    supporting_papers: List[int]
    rationale: str


@dataclass
class HypothesisChallengeResult:
    hypothesis: str
    challenges: List[Challenge]
    total_challenges: int
    strongest_challenge: Optional[Challenge]
    overall_vulnerability: int  # 0-100
    summary: str
    generated_at: datetime = field(default_factory=_utcnow)


class ResearchChallengerService:
    """Service for hypothesis challenging."""
    
    def __init__(self):
        self._cache: Dict[str, HypothesisChallengeResult] = {}
        self._cache_ttl_seconds = 10 * 60  # 10 minutes
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        if cache_key not in self._cache:
            return False
        cached = self._cache[cache_key]
        age = (datetime.now(timezone.utc) - cached.generated_at).total_seconds()
        return age < self._cache_ttl_seconds
    
    def _get_cache_key(self, hypothesis: str, paper_ids: List[int]) -> str:
        paper_ids_sorted = tuple(sorted(paper_ids))
        return f"{hypothesis}:{paper_ids_sorted}"
    
    def _detect_counter_evidence(self, hypothesis: str, papers: List[Paper]) -> List[str]:
        """Detect counter-evidence in papers."""
        counter_evidence: List[str] = []
        hypothesis_tokens = set(_tokenize(hypothesis.lower()))
        
        for paper in papers:
            text = f"{paper.title} {paper.abstract or ''}".lower()
            text_tokens = set(_tokenize(text))
            
            # Check for counter-indicators
            for indicator in _COUNTER_INDICATORS:
                if indicator in text:
                    # Find sentences with counter-indicators
                    sentences = text.split(".")
                    for sentence in sentences:
                        if indicator in sentence:
                            sentence_tokens = set(_tokenize(sentence))
                            overlap = len(hypothesis_tokens.intersection(sentence_tokens))
                            if overlap > 0:
                                counter_evidence.append(sentence.strip())
                                break
        
        return counter_evidence[:5]  # Return top 5 counter-evidence items
    
    def _generate_methodological_challenge(
        self, hypothesis: str, papers: List[Paper]
    ) -> Challenge:
        """Generate methodological challenge."""
        challenge_text = (
            f"The hypothesis '{hypothesis}' may be limited by methodological issues "
            f"such as lack of proper controls, insufficient sample size, or "
            f"inadequate experimental design in the supporting literature."
        )
        
        counter_evidence = self._detect_counter_evidence(hypothesis, papers)
        evidence_text = "; ".join(counter_evidence) if counter_evidence else "No specific counter-evidence found"
        
        return Challenge(
            id="challenge_methodological",
            hypothesis=hypothesis,
            challenge_type="methodological",
            challenge_text=challenge_text,
            counter_evidence=evidence_text,
            strength=60,
            confidence=65,
            supporting_papers=[p.id for p in papers[:2]],
            rationale="Methodological limitations are common in research and can significantly affect validity."
        )
    
    def _generate_data_challenge(
        self, hypothesis: str, papers: List[Paper]
    ) -> Challenge:
        """Generate data-related challenge."""
        challenge_text = (
            f"The hypothesis '{hypothesis}' may be challenged by data limitations "
            f"including dataset bias, insufficient data diversity, or data quality issues."
        )
        
        counter_evidence = self._detect_counter_evidence(hypothesis, papers)
        evidence_text = "; ".join(counter_evidence) if counter_evidence else "No specific counter-evidence found"
        
        return Challenge(
            id="challenge_data",
            hypothesis=hypothesis,
            challenge_type="data",
            challenge_text=challenge_text,
            counter_evidence=evidence_text,
            strength=55,
            confidence=60,
            supporting_papers=[p.id for p in papers[:2]],
            rationale="Data limitations can lead to overgeneralization or biased conclusions."
        )
    
    def _generate_interpretation_challenge(
        self, hypothesis: str, papers: List[Paper]
    ) -> Challenge:
        """Generate interpretation challenge."""
        challenge_text = (
            f"The hypothesis '{hypothesis}' may have alternative interpretations. "
            f"The observed effects could be explained by confounding factors, "
            f"spurious correlations, or different causal mechanisms."
        )
        
        counter_evidence = self._detect_counter_evidence(hypothesis, papers)
        evidence_text = "; ".join(counter_evidence) if counter_evidence else "No specific counter-evidence found"
        
        return Challenge(
            id="challenge_interpretation",
            hypothesis=hypothesis,
            challenge_type="interpretation",
            challenge_text=challenge_text,
            counter_evidence=evidence_text,
            strength=70,
            confidence=70,
            supporting_papers=[p.id for p in papers[:2]],
            rationale="Alternative interpretations are common and should be carefully considered."
        )
    
    def _generate_generalization_challenge(
        self, hypothesis: str, papers: List[Paper]
    ) -> Challenge:
        """Generate generalization challenge."""
        challenge_text = (
            f"The hypothesis '{hypothesis}' may not generalize to other contexts, "
            f"populations, or settings. The supporting evidence may be limited "
            f"to specific conditions or domains."
        )
        
        counter_evidence = self._detect_counter_evidence(hypothesis, papers)
        evidence_text = "; ".join(counter_evidence) if counter_evidence else "No specific counter-evidence found"
        
        return Challenge(
            id="challenge_generalization",
            hypothesis=hypothesis,
            challenge_type="generalization",
            challenge_text=challenge_text,
            counter_evidence=evidence_text,
            strength=65,
            confidence=65,
            supporting_papers=[p.id for p in papers[:2]],
            rationale="Generalization is a key concern in research and requires diverse evidence."
        )
    
    def _generate_replication_challenge(
        self, hypothesis: str, papers: List[Paper]
    ) -> Challenge:
        """Generate replication challenge."""
        challenge_text = (
            f"The hypothesis '{hypothesis}' may face replication challenges. "
            f"Reproducibility issues, lack of replication studies, or "
            f"inconsistent results across studies may undermine confidence."
        )
        
        counter_evidence = self._detect_counter_evidence(hypothesis, papers)
        evidence_text = "; ".join(counter_evidence) if counter_evidence else "No specific counter-evidence found"
        
        return Challenge(
            id="challenge_replication",
            hypothesis=hypothesis,
            challenge_type="replication",
            challenge_text=challenge_text,
            counter_evidence=evidence_text,
            strength=75,
            confidence=70,
            supporting_papers=[p.id for p in papers[:2]],
            rationale="Replication is fundamental to scientific validity and requires attention."
        )
    
    def _calculate_overall_vulnerability(self, challenges: List[Challenge]) -> int:
        """Calculate overall hypothesis vulnerability score."""
        if not challenges:
            return 0
        
        avg_strength = sum(c.strength for c in challenges) / len(challenges)
        avg_confidence = sum(c.confidence for c in challenges) / len(challenges)
        
        overall = int((avg_strength * 0.6) + (avg_confidence * 0.4))
        return max(0, min(100, overall))
    
    def challenge_hypothesis(
        self,
        hypothesis: str,
        papers: List[Paper],
        use_cache: bool = True
    ) -> HypothesisChallengeResult:
        """Challenge a research hypothesis with multiple perspectives."""
        if not HYPOTHESIS_CHALLENGER_ENABLED:
            raise RuntimeError(
                "Hypothesis Challenger is disabled. Set HYPOTHESIS_CHALLENGER_ENABLED=1 in .env"
            )
        
        if not papers:
            return HypothesisChallengeResult(
                hypothesis=hypothesis,
                challenges=[],
                total_challenges=0,
                strongest_challenge=None,
                overall_vulnerability=0,
                summary="No papers available to challenge the hypothesis"
            )
        
        paper_ids = [p.id for p in papers]
        cache_key = self._get_cache_key(hypothesis, paper_ids)
        
        if use_cache and self._is_cache_valid(cache_key):
            return self._cache[cache_key]
        
        # Generate challenges
        challenges: List[Challenge] = [
            self._generate_methodological_challenge(hypothesis, papers),
            self._generate_data_challenge(hypothesis, papers),
            self._generate_interpretation_challenge(hypothesis, papers),
            self._generate_generalization_challenge(hypothesis, papers),
            self._generate_replication_challenge(hypothesis, papers),
        ]
        
        # Rank by strength
        challenges.sort(key=lambda c: c.strength, reverse=True)
        
        # Calculate overall vulnerability
        vulnerability = self._calculate_overall_vulnerability(challenges)
        
        # Identify strongest challenge
        strongest = challenges[0] if challenges else None
        
        # Generate summary
        total = len(challenges)
        summary = (
            f"Generated {total} challenges for hypothesis: '{hypothesis}'. "
            f"Overall vulnerability: {vulnerability}/100. "
            f"Strongest challenge: {strongest.challenge_type if strongest else 'N/A'} "
            f"(strength {strongest.strength if strongest else 0}/100)."
        )
        
        result = HypothesisChallengeResult(
            hypothesis=hypothesis,
            challenges=challenges,
            total_challenges=total,
            strongest_challenge=strongest,
            overall_vulnerability=vulnerability,
            summary=summary
        )
        
        # Cache the result
        self._cache[cache_key] = result
        
        return result


# Global service instance
_challenger_service: Optional[ResearchChallengerService] = None


def get_challenger_service() -> ResearchChallengerService:
    """Get the global challenger service instance."""
    global _challenger_service
    if _challenger_service is None:
        _challenger_service = ResearchChallengerService()
    return _challenger_service
