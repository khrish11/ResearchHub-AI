"""
Research Plan Generation Service

Generates structured research plans from research opportunities using AI.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime

from repositories.research import (
    ResearchIntelligenceArtifact,
    ResearchOpportunity,
    Paper,
    ResearchPlan,
    WorkspaceDocument,
)
from services.ai_service import run_structured_json_task


class ResearchPlanService:
    """Service for generating research plans from opportunities."""

    def __init__(self):
        pass

    def convert_to_document(self, plan: ResearchPlan) -> WorkspaceDocument:
        """
        Convert a structured ResearchPlan to a WorkspaceDocument for DocSpace.

        Args:
            plan: The research plan to convert

        Returns:
            WorkspaceDocument with markdown content
        """
        # Build markdown content from plan fields
        markdown = self._plan_to_markdown(plan)
        
        # Create WorkspaceDocument
        document = WorkspaceDocument(
            id=None,  # Will be assigned by repository
            workspace_id=plan.workspace_id,
            user_id=plan.user_id,
            title=plan.title,
            content=markdown,
            version=1,
            created_at=plan.created_at,
            updated_at=plan.updated_at,
        )
        
        return document

    def _plan_to_markdown(self, plan: ResearchPlan) -> str:
        """Convert ResearchPlan to markdown format."""
        lines = [
            f"# {plan.title}",
            "",
            f"**Research Plan ID:** {plan.id}",
            f"**Generated from Opportunity:** {plan.opportunity_id}",
            f"**Status:** {plan.status}",
            f"**Last Updated:** {plan.updated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            "---",
            "",
            "## Research Problem",
            plan.research_problem,
            "",
            "## Research Question",
            plan.research_question,
            "",
            "## Hypothesis",
            plan.hypothesis,
            "",
            "## Objectives",
            plan.objectives,
            "",
            "## Proposed Methodology",
            plan.proposed_methodology,
            "",
            "## Alternative Methodology",
            plan.alternative_methodology,
            "",
            "## Datasets",
            plan.datasets,
            "",
            "## Variables",
            plan.variables,
            "",
            "## Baselines",
            plan.baselines,
            "",
            "## Evaluation Metrics",
            plan.evaluation_metrics,
            "",
            "## Expected Contribution",
            plan.expected_contribution,
            "",
            "## Risks",
            plan.risks,
            "",
            "## Limitations",
            plan.limitations,
            "",
            "## Reproducibility Requirements",
            plan.reproducibility_requirements,
            "",
            "---",
            "",
            "## Evidence References",
        ]
        
        for ref in plan.evidence_references:
            lines.append(f"- {ref}")
        
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("*This research plan was generated using Research Intelligence AI.*")
        lines.append(f"*Source Artifact ID: {plan.artifact_id}*")
        
        return "\n".join(lines)

    async def generate_plan_suggestions(
        self,
        opportunity: ResearchOpportunity,
        artifact: ResearchIntelligenceArtifact,
        papers: List[Paper],
    ) -> Dict[str, Any]:
        """
        Generate AI suggestions for all research plan fields based on an opportunity.

        Args:
            opportunity: The selected research opportunity
            artifact: The intelligence artifact containing the opportunity
            papers: The papers supporting the opportunity

        Returns:
            Dictionary containing AI suggestions for all plan fields
        """
        # Build context from papers
        paper_context = self._build_paper_context(papers)
        
        # Build opportunity context
        opportunity_context = {
            "gap_id": opportunity.gap_id,
            "gap_description": opportunity.gap_description,
            "category": opportunity.category,
            "evidence_strength": opportunity.evidence_strength,
            "novelty": opportunity.novelty,
            "impact": opportunity.impact,
            "feasibility": opportunity.feasibility,
            "recency": opportunity.recency,
            "overall_score": opportunity.overall_score,
            "explanation": opportunity.explanation,
            "supporting_papers": opportunity.supporting_papers,
            "affected_papers": opportunity.affected_papers,
        }

        # Build system prompt
        system_prompt = """You are an expert research methodology advisor specializing in converting research opportunities into actionable research plans.

Your task is to generate comprehensive, evidence-backed research plan suggestions based on a research opportunity identified from a literature analysis.

For each field you generate:
1. Base your suggestions on the provided evidence (papers, gaps, opportunity analysis)
2. Be specific and actionable
3. Consider feasibility, novelty, and impact
4. Cite specific papers when relevant
5. Do not fabricate datasets, results, or citations not present in the context
6. Indicate the evidence backing for each suggestion

Output format: JSON with all required fields."""

        # Build user prompt
        user_prompt = f"""Generate a research plan for the following research opportunity:

RESEARCH TOPIC: {artifact.topic}

OPPORTUNITY DETAILS:
{self._format_opportunity(opportunity_context)}

SUPPORTING PAPERS:
{paper_context}

Generate a comprehensive research plan with the following fields:
- title: A concise, descriptive title for the research plan
- research_problem: Clear articulation of the research problem
- research_question: Specific, answerable research question
- hypothesis: Testable hypothesis
- objectives: 3-5 specific research objectives
- proposed_methodology: Detailed methodology approach with justification
- alternative_methodology: Alternative approach if primary fails
- datasets: Required datasets and data sources
- variables: Key variables (independent, dependent, control)
- baselines: Baseline methods or approaches for comparison
- evaluation_metrics: Metrics for evaluating success
- expected_contribution: Expected contribution to the field
- risks: Potential risks and mitigation strategies
- limitations: Study limitations
- reproducibility_requirements: Requirements for reproducibility

For each field, provide evidence backing by referencing specific papers or evidence from the opportunity analysis."""

        # Define output schema
        output_schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "research_problem": {"type": "string"},
                "research_question": {"type": "string"},
                "hypothesis": {"type": "string"},
                "objectives": {"type": "string"},
                "proposed_methodology": {"type": "string"},
                "alternative_methodology": {"type": "string"},
                "datasets": {"type": "string"},
                "variables": {"type": "string"},
                "baselines": {"type": "string"},
                "evaluation_metrics": {"type": "string"},
                "expected_contribution": {"type": "string"},
                "risks": {"type": "string"},
                "limitations": {"type": "string"},
                "reproducibility_requirements": {"type": "string"},
                "evidence_backing": {
                    "type": "object",
                    "properties": {
                        "proposed_methodology": {"type": "string"},
                        "datasets": {"type": "string"},
                        "evaluation_metrics": {"type": "string"},
                    },
                },
            },
            "required": [
                "title", "research_problem", "research_question", "hypothesis",
                "objectives", "proposed_methodology", "alternative_methodology",
                "datasets", "variables", "baselines", "evaluation_metrics",
                "expected_contribution", "risks", "limitations",
                "reproducibility_requirements", "evidence_backing"
            ],
        }

        # Generate suggestions
        result = await run_structured_json_task(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_schema=output_schema,
            temperature=0.7,
        )

        # Add evidence references
        result["evidence_references"] = self._extract_evidence_references(
            result.get("evidence_backing", {}),
            opportunity,
            papers,
        )

        return result

    def _build_paper_context(self, papers: List[Paper]) -> str:
        """Build a formatted string of paper context."""
        if not papers:
            return "No papers provided."
        
        context_lines = []
        for i, paper in enumerate(papers, 1):
            context_lines.append(
                f"{i}. {paper.title}\n"
                f"   Authors: {paper.authors}\n"
                f"   Abstract: {paper.abstract[:500]}..."
            )
        return "\n\n".join(context_lines)

    def _format_opportunity(self, opportunity: Dict[str, Any]) -> str:
        """Format opportunity details as a string."""
        return f"""
Gap ID: {opportunity['gap_id']}
Gap Description: {opportunity['gap_description']}
Category: {opportunity['category']}
Evidence Strength: {opportunity['evidence_strength']}/100
Novelty: {opportunity['novelty']}/100
Impact: {opportunity['impact']}/100
Feasibility: {opportunity['feasibility']}/100
Recency: {opportunity['recency']}/100
Overall Score: {opportunity['overall_score']}/100
Explanation: {opportunity['explanation']}
Supporting Papers: {len(opportunity['supporting_papers'])}
Affected Papers: {len(opportunity['affected_papers'])}
"""

    def _extract_evidence_references(
        self,
        evidence_backing: Dict[str, str],
        opportunity: ResearchOpportunity,
        papers: List[Paper],
    ) -> List[str]:
        """Extract evidence references from the AI response."""
        references = []
        
        # Add evidence backing from AI
        for field, backing in evidence_backing.items():
            if backing:
                references.append(f"{field}: {backing}")
        
        # Add opportunity explanation
        if opportunity.explanation:
            references.append(f"Opportunity: {opportunity.explanation}")
        
        # Add supporting paper references
        for paper_id in opportunity.supporting_papers:
            paper = next((p for p in papers if p.id == paper_id), None)
            if paper:
                references.append(f"Paper: {paper.title} (ID: {paper_id})")
        
        return references


# Singleton instance
_plan_service: Optional[ResearchPlanService] = None


def get_plan_service() -> ResearchPlanService:
    """Get the singleton ResearchPlanService instance."""
    global _plan_service
    if _plan_service is None:
        _plan_service = ResearchPlanService()
    return _plan_service
