"""
RAG Query Handler - Generate grounded answers from retrieved context.
"""

import logging
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SourceType(str, Enum):
    PAPER = "paper"
    SUMMARY = "summary"
    CHECKER = "checker"
    REPORT = "report"


dataclass
class SourceAttribution:
    source_id: str
    source_type: str
    title: Optional[str]
    mention_count: int = 0
    relevance_score: float = 0.0


@dataclass
class RAGQueryInput:
    query: str
    retrieved_context: List[Dict[str, Any]]
    max_tokens: int = 1500


@dataclass
class RAGQueryOutput:
    answer: str
    sources_used: List[SourceAttribution]
    confidence: float
    grounding_score: float


class RAGQueryHandler:
    """Handler for rag_query AI task - generates grounded answers."""
    
    def __init__(self, groq_client_ref=None):
        self.groq_client = groq_client_ref
    
    async def handle(self, input: RAGQueryInput) -> RAGQueryOutput:
        """Handle RAG query task."""
        logger.info(f"Handling RAG query: {input.query[:50]}...")
        
        if not input.query or not input.query.strip():
            raise ValueError("Query cannot be empty")
        
        if not input.retrieved_context:
            logger.warning("No retrieved context provided")
            return RAGQueryOutput(
                answer="I could not find relevant information in your workspace.",
                sources_used=[],
                confidence=0.0,
                grounding_score=0.0,
            )
        
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(input)
        
        try:
            response_text = await self._query_llm(system_prompt, user_prompt, input.max_tokens)
        except Exception as e:
            logger.error(f"LLM query failed: {e}")
            raise
        
        answer = response_text.strip()
        sources_used = self._extract_sources(answer, input.retrieved_context)
        self._validate_grounding(answer, sources_used, input.retrieved_context)
        
        confidence = self._calculate_confidence(
            answer=answer,
            sources=sources_used,
            context_count=len(input.retrieved_context),
        )
        
        grounding_score = self._calculate_grounding_score(answer, sources_used)
        
        logger.info(
            f"RAG query completed: {len(sources_used)} sources, "
            f"confidence={confidence:.2f}, grounding={grounding_score:.2f}"
        )
        
        return RAGQueryOutput(
            answer=answer,
            sources_used=sources_used,
            confidence=confidence,
            grounding_score=grounding_score,
        )
    
    def _build_system_prompt(self) -> str:
        return """You are an AI assistant answering questions about research papers.

CRITICAL INSTRUCTIONS:
1. ONLY use information from the provided context
2. If you cannot answer, say so explicitly
3. Cite sources when making claims: "According to [Source 1]..."
4. Never invent references
5. Be honest about uncertainty

ANSWER FORMAT:
- Direct answer to question
- Support with evidence
- Clear source citations
- Any caveats or limitations"""
    
    def _build_user_prompt(self, input: RAGQueryInput) -> str:
        context_text = self._format_context(input.retrieved_context)
        return f"""## Context from Workspace

{context_text}

## Question
{input.query}

## Answer
Based on the provided context:"""
    
    def _format_context(self, retrieved_context: List[Dict[str, Any]]) -> str:
        formatted = ""
        for i, ctx in enumerate(retrieved_context, 1):
            formatted += f"\n### Source {i}\n"
            formatted += f"**Title:** {ctx.get('metadata', {}).get('title', 'Unknown')}\n"
            formatted += f"**Type:** {ctx.get('source_type', 'unknown')}\n"
            formatted += f"**Relevance:** {ctx.get('similarity_score', 0):.1%}\n"
            formatted += f"\n{ctx.get('text', '')}\n\n"
        return formatted
    
    async def _query_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1500,
    ) -> str:
        if not self.groq_client:
            raise RuntimeError("Groq client not available")
        
        from utils.groq_client import model_config
        
        response = self.groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            **model_config(task="pipeline", max_tokens=min(max_tokens, 2000)),
        )
        
        return response.choices[0].message.content.strip()
    
    def _extract_sources(
        self,
        answer: str,
        retrieved_context: List[Dict[str, Any]],
    ) -> List[SourceAttribution]:
        sources_used = {}
        pattern = r"\[?Source\s+(\d+)\]?"
        matches = re.findall(pattern, answer, re.IGNORECASE)
        
        for match in matches:
            try:
                idx = int(match) - 1
                if 0 <= idx < len(retrieved_context):
                    ctx = retrieved_context[idx]
                    source_id = ctx.get("source_id", f"unknown_{idx}")
                    
                    if source_id not in sources_used:
                        sources_used[source_id] = SourceAttribution(
                            source_id=source_id,
                            source_type=ctx.get("source_type", "unknown"),
                            title=ctx.get("metadata", {}).get("title"),
                            mention_count=0,
                            relevance_score=ctx.get("similarity_score", 0.0),
                        )
                    
                    sources_used[source_id].mention_count += 1
            except (ValueError, IndexError):
                logger.warning(f"Invalid source index: {match}")
        
        return list(sources_used.values())
    
    def _validate_grounding(
        self,
        answer: str,
        sources_used: List[SourceAttribution],
        retrieved_context: List[Dict[str, Any]],
    ) -> None:
        valid_source_ids = {ctx.get("source_id") for ctx in retrieved_context}
        used_source_ids = {s.source_id for s in sources_used}
        
        if not used_source_ids.issubset(valid_source_ids):
            invalid = used_source_ids - valid_source_ids
            logger.warning(f"Potential hallucination detected: {invalid}")
    
    def _calculate_confidence(
        self,
        answer: str,
        sources: List[SourceAttribution],
        context_count: int,
    ) -> float:
        if not sources:
            return 0.0
        
        source_coverage = min(len(sources) / max(context_count, 1), 1.0)
        avg_relevance = sum(s.relevance_score for s in sources) / len(sources)
        length_factor = min(len(answer) / 50, 1.0)
        
        confidence = (0.4 * source_coverage + 0.4 * avg_relevance + 0.2 * length_factor)
        return min(confidence, 1.0)
    
    def _calculate_grounding_score(
        self,
        answer: str,
        sources_used: List[SourceAttribution],
    ) -> float:
        if not answer:
            return 0.0
        
        pattern = r"\[?Source\s+\d+\]?"
        mention_count = len(re.findall(pattern, answer, re.IGNORECASE))
        answer_words = len(answer.split())
        expected_mentions = max(1, answer_words // 100)
        
        return min(mention_count / expected_mentions, 1.0)