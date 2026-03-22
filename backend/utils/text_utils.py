"""Shared text utilities for tokenisation and stop-word filtering.

Centralised here so chat.py, workspaces.py, and research_agent.py all use
the same vocabulary instead of each maintaining its own copy.
"""

from __future__ import annotations

import re
from typing import List

# Broad English stop-word list covering common research-text noise.
STOP_WORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "for",
        "with",
        "from",
        "that",
        "this",
        "into",
        "using",
        "your",
        "about",
        "have",
        "has",
        "are",
        "was",
        "were",
        "how",
        "what",
        "when",
        "where",
        "which",
        "will",
        "would",
        "could",
        "should",
        "can",
        "also",
        "than",
        "then",
        "their",
        "there",
        "these",
        "those",
        "over",
        "under",
        "between",
        "across",
        "based",
        "study",
        "paper",
        "analysis",
        "results",
        "method",
        "methods",
        "data",
        "approach",
        "approaches",
        "system",
        "systems",
        "model",
        "models",
        "research",
        "through",
        "while",
        "after",
        "before",
        "because",
        "such",
        "more",
        "most",
        "less",
        "many",
        "both",
        "each",
        "within",
        "without",
        "only",
        "been",
        "being",
        "upon",
        "its",
        "our",
        "they",
        "them",
        "we",
        "you",
        "it",
        "is",
        "in",
        "of",
        "to",
        "at",
        "by",
        "on",
        "as",
        "be",
        "do",
    }
)


def tokenize(text: str, min_length: int = 3) -> List[str]:
    """Return lowercase alpha-numeric tokens, filtered by stop words and length."""
    tokens = re.findall(r"[a-zA-Z0-9]{" + str(min_length) + r",}", (text or "").lower())
    return [tok for tok in tokens if tok not in STOP_WORDS]


def extract_keywords(text: str, max_keywords: int = 12) -> List[str]:
    """Return the top *max_keywords* unique non-stop tokens from *text*."""
    tokens = tokenize(text)
    seen: set[str] = set()
    unique: List[str] = []
    for tok in tokens:
        if tok not in seen:
            seen.add(tok)
            unique.append(tok)
        if len(unique) >= max_keywords:
            break
    return unique
