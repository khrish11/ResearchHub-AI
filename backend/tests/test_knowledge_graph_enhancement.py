"""
test_knowledge_graph_enhancement.py
──────────────────────────────────
Tests for Knowledge Graph Enhancement Service
"""

import os
import pytest

from repositories.research import Paper
from services.knowledge_graph_enhancement_service import (
    KnowledgeGraphEnhancementService,
    IntelligenceLayer,
    EnhancedKnowledgeGraph,
    get_graph_enhancement_service,
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
            abstract="Deep learning models fail to generalize on small datasets due to overfitting.",
            url="https://example.com/paper2",
            source="pubmed",
            doi="",
        ),
    ]


@pytest.fixture
def sample_base_graph():
    """Create a sample base knowledge graph."""
    return {
        "nodes": [
            {"id": 1, "title": "Paper 1", "type": "paper"},
            {"id": 2, "title": "Paper 2", "type": "paper"},
        ],
        "edges": [
            {"source": 1, "target": 2, "type": "citation"},
        ],
        "workspace": {"id": 1, "name": "Test Workspace"}
    }


@pytest.fixture
def graph_service():
    """Create graph enhancement service instance."""
    return KnowledgeGraphEnhancementService()


class TestKnowledgeGraphEnhancementService:
    """Test Knowledge Graph Enhancement Service functionality."""

    def test_add_gap_layer(self, graph_service, sample_papers):
        """Test gap intelligence layer addition."""
        layer = graph_service._add_gap_layer(sample_papers, "deep learning")
        
        assert isinstance(layer, IntelligenceLayer)
        assert layer.layer_type == "gap"
        assert isinstance(layer.data, dict)
        assert len(layer.summary) > 0

    def test_add_evidence_layer(self, graph_service, sample_papers):
        """Test evidence intelligence layer addition."""
        layer = graph_service._add_evidence_layer(sample_papers, "deep learning improves performance")
        
        assert isinstance(layer, IntelligenceLayer)
        assert layer.layer_type == "evidence"
        assert isinstance(layer.data, dict)
        assert len(layer.summary) > 0

    def test_add_opportunity_layer(self, graph_service, sample_papers):
        """Test opportunity scoring layer addition."""
        layer = graph_service._add_opportunity_layer(sample_papers, "deep learning")
        
        assert isinstance(layer, IntelligenceLayer)
        assert layer.layer_type == "opportunity"
        assert isinstance(layer.data, dict)
        assert len(layer.summary) > 0

    def test_add_citation_layer(self, graph_service, sample_papers):
        """Test citation verification layer addition."""
        layer = graph_service._add_citation_layer(sample_papers)
        
        assert isinstance(layer, IntelligenceLayer)
        assert layer.layer_type == "citation"
        assert isinstance(layer.data, dict)
        assert len(layer.summary) > 0

    def test_enhance_knowledge_graph_all_layers(self, sample_papers, sample_base_graph):
        """Test full knowledge graph enhancement with all layers."""
        from services import knowledge_graph_enhancement_service
        from services import gap_intelligence_service, evidence_intelligence_service
        from services import opportunity_scoring_service, citation_verification_service
        
        # Ensure all feature flags are enabled for this test
        original_kg_flag = knowledge_graph_enhancement_service.KNOWLEDGE_GRAPH_ENHANCED_ENABLED
        original_gap_flag = gap_intelligence_service.GAP_INTELLIGENCE_ENABLED
        original_evidence_flag = evidence_intelligence_service.EVIDENCE_INTELLIGENCE_ENABLED
        original_opp_flag = opportunity_scoring_service.OPPORTUNITY_SCORING_ENABLED
        original_citation_flag = citation_verification_service.CITATION_VERIFICATION_ENABLED
        
        knowledge_graph_enhancement_service.KNOWLEDGE_GRAPH_ENHANCED_ENABLED = True
        gap_intelligence_service.GAP_INTELLIGENCE_ENABLED = True
        evidence_intelligence_service.EVIDENCE_INTELLIGENCE_ENABLED = True
        opportunity_scoring_service.OPPORTUNITY_SCORING_ENABLED = True
        citation_verification_service.CITATION_VERIFICATION_ENABLED = True
        
        try:
            # Create fresh service instance to avoid cached state
            graph_service = KnowledgeGraphEnhancementService()
            
            result = graph_service.enhance_knowledge_graph(
                base_graph=sample_base_graph,
                papers=sample_papers,
                topic="deep learning",
                layers=["gap", "evidence", "opportunity", "citation"],
                use_cache=False
            )
            
            assert isinstance(result, EnhancedKnowledgeGraph)
            assert result.base_graph == sample_base_graph
            assert result.total_layers == 4
            assert len(result.intelligence_layers) == 4
            assert result.enhanced_nodes > 0
            assert result.enhanced_edges > 0
            assert len(result.summary) > 0
        finally:
            knowledge_graph_enhancement_service.KNOWLEDGE_GRAPH_ENHANCED_ENABLED = original_kg_flag
            gap_intelligence_service.GAP_INTELLIGENCE_ENABLED = original_gap_flag
            evidence_intelligence_service.EVIDENCE_INTELLIGENCE_ENABLED = original_evidence_flag
            opportunity_scoring_service.OPPORTUNITY_SCORING_ENABLED = original_opp_flag
            citation_verification_service.CITATION_VERIFICATION_ENABLED = original_citation_flag

    def test_enhance_knowledge_graph_selective_layers(self, graph_service, sample_papers, sample_base_graph):
        """Test knowledge graph enhancement with selective layers."""
        result = graph_service.enhance_knowledge_graph(
            base_graph=sample_base_graph,
            papers=sample_papers,
            topic="deep learning",
            layers=["gap", "citation"],
            use_cache=False
        )
        
        assert result.total_layers == 2
        assert len(result.intelligence_layers) == 2
        layer_types = {l.layer_type for l in result.intelligence_layers}
        assert layer_types == {"gap", "citation"}

    def test_enhance_knowledge_graph_empty_papers(self, graph_service, sample_base_graph):
        """Test knowledge graph enhancement with empty papers."""
        result = graph_service.enhance_knowledge_graph(
            base_graph=sample_base_graph,
            papers=[],
            topic="test",
            layers=["gap"],
            use_cache=False
        )
        
        assert result.total_layers == 0
        assert len(result.intelligence_layers) == 0
        assert result.enhanced_nodes == 0
        assert result.enhanced_edges == 0
        assert "no papers" in result.summary.lower()

    def test_enhance_knowledge_graph_no_layers(self, graph_service, sample_papers, sample_base_graph):
        """Test knowledge graph enhancement with no layers specified."""
        result = graph_service.enhance_knowledge_graph(
            base_graph=sample_base_graph,
            papers=sample_papers,
            topic="deep learning",
            layers=[],
            use_cache=False
        )
        
        assert result.total_layers == 0
        assert len(result.intelligence_layers) == 0

    def test_feature_flag_disabled(self, monkeypatch):
        """Test that service raises error when feature flag is disabled."""
        from services import knowledge_graph_enhancement_service
        
        # Save original flag value and service instance
        original_flag = knowledge_graph_enhancement_service.KNOWLEDGE_GRAPH_ENHANCED_ENABLED
        original_service = knowledge_graph_enhancement_service._graph_enhancement_service
        
        try:
            monkeypatch.setenv("KNOWLEDGE_GRAPH_ENHANCED_ENABLED", "0")
            
            # Re-import to pick up new env var
            knowledge_graph_enhancement_service.KNOWLEDGE_GRAPH_ENHANCED_ENABLED = False
            
            service = KnowledgeGraphEnhancementService()
            
            with pytest.raises(RuntimeError, match="Knowledge Graph Enhancement is disabled"):
                service.enhance_knowledge_graph({}, [], "test", [], use_cache=False)
        finally:
            # Restore original flag value and service instance
            knowledge_graph_enhancement_service.KNOWLEDGE_GRAPH_ENHANCED_ENABLED = original_flag
            knowledge_graph_enhancement_service._graph_enhancement_service = original_service

    def test_global_service_instance(self):
        """Test global service instance getter."""
        service = get_graph_enhancement_service()
        
        assert isinstance(service, KnowledgeGraphEnhancementService)
        
        # Second call should return same instance
        service2 = get_graph_enhancement_service()
        assert service is service2

    def test_intelligence_layer_validation(self, graph_service, sample_papers):
        """Test that intelligence layers have valid properties."""
        gap_layer = graph_service._add_gap_layer(sample_papers, "deep learning")
        citation_layer = graph_service._add_citation_layer(sample_papers)
        
        for layer in [gap_layer, citation_layer]:
            assert len(layer.layer_type) > 0
            assert isinstance(layer.enabled, bool)
            assert isinstance(layer.data, dict)
            assert len(layer.summary) > 0

    def test_enhancement_metrics(self, graph_service, sample_papers, sample_base_graph):
        """Test enhancement metrics calculation."""
        # Enable feature flag for this test
        from services import knowledge_graph_enhancement_service
        original_flag = knowledge_graph_enhancement_service.KNOWLEDGE_GRAPH_ENHANCED_ENABLED
        original_service = knowledge_graph_enhancement_service._graph_enhancement_service
        knowledge_graph_enhancement_service.KNOWLEDGE_GRAPH_ENHANCED_ENABLED = True
        
        try:
            result = graph_service.enhance_knowledge_graph(
                base_graph=sample_base_graph,
                papers=sample_papers,
                topic="deep learning",
                layers=["gap", "citation"],
                use_cache=False
            )
            
            # Calculate enhancement metrics
            base_nodes = len(sample_base_graph.get("nodes", []))
            base_edges = len(sample_base_graph.get("edges", []))
            enabled_layers = len([l for l in result.intelligence_layers if l.enabled])
            
            assert result.enhanced_nodes == base_nodes * enabled_layers
            assert result.enhanced_edges == base_edges * enabled_layers
        finally:
            knowledge_graph_enhancement_service.KNOWLEDGE_GRAPH_ENHANCED_ENABLED = original_flag
            knowledge_graph_enhancement_service._graph_enhancement_service = original_service

    def test_enhance_knowledge_graph_with_cache(self, graph_service, sample_papers, sample_base_graph):
        """Test knowledge graph enhancement with caching."""
        # Enable feature flag for this test
        from services import knowledge_graph_enhancement_service
        original_flag = knowledge_graph_enhancement_service.KNOWLEDGE_GRAPH_ENHANCED_ENABLED
        original_service = knowledge_graph_enhancement_service._graph_enhancement_service
        knowledge_graph_enhancement_service.KNOWLEDGE_GRAPH_ENHANCED_ENABLED = True
        
        try:
            # First call
            result1 = graph_service.enhance_knowledge_graph(
                base_graph=sample_base_graph,
                papers=sample_papers,
                topic="deep learning",
                layers=["gap"],
                use_cache=True
            )
            
            # Second call should use cache
            result2 = graph_service.enhance_knowledge_graph(
                base_graph=sample_base_graph,
                papers=sample_papers,
                topic="deep learning",
                layers=["gap"],
                use_cache=True
            )
            
            assert result1.total_layers == result2.total_layers
            assert result1.enhanced_nodes == result2.enhanced_nodes
            assert result1.enhanced_edges == result2.enhanced_edges
        finally:
            knowledge_graph_enhancement_service.KNOWLEDGE_GRAPH_ENHANCED_ENABLED = original_flag
            knowledge_graph_enhancement_service._graph_enhancement_service = original_service

    def test_layer_disabled_handling(self, graph_service, sample_papers):
        """Test handling of disabled layers."""
        # This test verifies that disabled layers are handled gracefully
        gap_layer = graph_service._add_gap_layer(sample_papers, "deep learning")
        
        # Layer should still be returned even if disabled
        assert gap_layer is not None
        assert isinstance(gap_layer, IntelligenceLayer)

    def test_enhance_knowledge_graph_default_layers(self, graph_service, sample_papers, sample_base_graph):
        """Test knowledge graph enhancement with default layers."""
        # Enable feature flag for this test
        from services import knowledge_graph_enhancement_service
        original_flag = knowledge_graph_enhancement_service.KNOWLEDGE_GRAPH_ENHANCED_ENABLED
        original_service = knowledge_graph_enhancement_service._graph_enhancement_service
        knowledge_graph_enhancement_service.KNOWLEDGE_GRAPH_ENHANCED_ENABLED = True
        
        try:
            result = graph_service.enhance_knowledge_graph(
                base_graph=sample_base_graph,
                papers=sample_papers,
                topic="deep learning",
                layers=None,  # Should use default
                use_cache=False
            )
            
            # Should use all default layers
            assert result.total_layers == 4
        finally:
            knowledge_graph_enhancement_service.KNOWLEDGE_GRAPH_ENHANCED_ENABLED = original_flag
            knowledge_graph_enhancement_service._graph_enhancement_service = original_service
