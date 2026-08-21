# PHASE 5.3 API CONTRACT VALIDATION REPORT

**Date:** 2025-01-XX
**Scope:** Backend Pydantic models vs Frontend TypeScript interfaces
**Status:** ✅ COMPLETE with findings

---

## Executive Summary

API contract validation compared backend Pydantic models in `research_agent.py` with frontend TypeScript interfaces in `researchIntelligence.ts`. Found minor discrepancies that should be addressed for consistency.

**Overall Status:** ✅ PASS with recommendations

---

## Findings

### 1. CreateResearchPlanRequest

**Backend (Pydantic):**
```python
class CreateResearchPlanRequest(BaseModel):
    workspace_id: int
    artifact_id: str
    opportunity_id: str
    opportunity_description: str
    title: str
    research_problem: str
    research_question: str
    hypothesis: str
    objectives: str
    proposed_methodology: str
    alternative_methodology: str
    datasets: str
    variables: str
    baselines: str
    evaluation_metrics: str
    expected_contribution: str
    risks: str
    limitations: str
    reproducibility_requirements: str
    supporting_papers: List[int] = Field(default_factory=list)
    evidence_references: List[str] = Field(default_factory=list)
    status: str = "draft"
```

**Frontend (TypeScript):**
```typescript
export interface CreateResearchPlanRequest extends WorkspaceScopedRequest {
  artifact_id: string;
  opportunity_id: string;
  opportunity_description: string;
  title: string;
  research_problem: string;
  research_question: string;
  hypothesis: string;
  objectives: string;
  proposed_methodology: string;
  alternative_methodology: string;
  datasets: string;
  variables: string;
  baselines: string;
  evaluation_metrics: string;
  expected_contribution: string;
  risks: string;
  limitations: string;
  reproducibility_requirements: string;
  supporting_papers?: number[];
  evidence_references?: string[];
  status?: string;
}
```

**WorkspaceScopedRequest (TypeScript):**
```typescript
export interface WorkspaceScopedRequest {
  workspace_id: number;
  topic?: string;
  paper_ids?: number[];
}
```

**Discrepancies:**
1. Frontend includes `topic` and `paper_ids` from WorkspaceScopedRequest which are not used by the backend
2. Frontend has `supporting_papers`, `evidence_references`, `status` as optional; backend has them with defaults
3. Frontend `status` is `string`; backend `status` is `string` with default "draft"

**Impact:** Low - Extra fields are ignored by backend, optional fields work correctly

---

### 2. UpdateResearchPlanRequest

**Backend (Pydantic):**
```python
class UpdateResearchPlanRequest(BaseModel):
    title: Optional[str] = None
    research_problem: Optional[str] = None
    research_question: Optional[str] = None
    hypothesis: Optional[str] = None
    objectives: Optional[str] = None
    proposed_methodology: Optional[str] = None
    alternative_methodology: Optional[str] = None
    datasets: Optional[str] = None
    variables: Optional[str] = None
    baselines: Optional[str] = None
    evaluation_metrics: Optional[str] = None
    expected_contribution: Optional[str] = None
    risks: Optional[str] = None
    limitations: Optional[str] = None
    reproducibility_requirements: Optional[str] = None
    supporting_papers: Optional[List[int]] = None
    evidence_references: Optional[List[str]] = None
    researcher_decisions: Optional[List[Dict[str, Any]]] = None
    status: Optional[str] = None
```

**Frontend (TypeScript):**
```typescript
export interface UpdateResearchPlanRequest {
  title?: string;
  research_problem?: string;
  research_question?: string;
  hypothesis?: string;
  objectives?: string;
  proposed_methodology?: string;
  alternative_methodology?: string;
  datasets?: string;
  variables?: string;
  baselines?: string;
  evaluation_metrics?: string;
  expected_contribution?: string;
  risks?: string;
  limitations?: string;
  reproducibility_requirements?: string;
  supporting_papers?: number[];
  evidence_references?: string[];
  researcher_decisions?: ResearcherDecision[];
  status?: string;
}
```

**Discrepancies:**
1. Frontend `researcher_decisions` is typed as `ResearcherDecision[]`; backend is `Optional[List[Dict[str, Any]]]`
2. Both have all fields optional - matches

**Impact:** Low - TypeScript interface is more specific, backend accepts dict

---

### 3. GeneratePlanSuggestionsRequest

**Backend (Pydantic):**
```python
class GeneratePlanSuggestionsRequest(BaseModel):
    artifact_id: str
    opportunity_id: str
    gap_description: str
    category: str
    evidence_strength: int
    novelty: int
    impact: int
    feasibility: int
    recency: int
    overall_score: int
    explanation: str
    supporting_papers: List[int]
    affected_papers: List[int]
```

**Frontend (TypeScript):**
```typescript
export interface GeneratePlanSuggestionsRequest {
  artifact_id: string;
  opportunity_id: string;
  gap_description: string;
  category: string;
  evidence_strength: number;
  novelty: number;
  impact: number;
  feasibility: number;
  recency: number;
  overall_score: number;
  explanation: string;
  supporting_papers: number[];
  affected_papers: number[];
}
```

**Discrepancies:** None - Perfect match

**Impact:** None

---

### 4. ResearchPlan Response

**Backend (Serialization):**
```python
def _serialize_research_plan(plan: ResearchPlan) -> Dict[str, Any]:
    return {
        "id": plan.id,
        "workspace_id": plan.workspace_id,
        "user_id": plan.user_id,
        "artifact_id": plan.artifact_id,
        "opportunity_id": plan.opportunity_id,
        "opportunity_description": plan.opportunity_description,
        "title": plan.title,
        "research_problem": plan.research_problem,
        "research_question": plan.research_question,
        "hypothesis": plan.hypothesis,
        "objectives": plan.objectives,
        "proposed_methodology": plan.proposed_methodology,
        "alternative_methodology": plan.alternative_methodology,
        "datasets": plan.datasets,
        "variables": plan.variables,
        "baselines": plan.baselines,
        "evaluation_metrics": plan.evaluation_metrics,
        "expected_contribution": plan.expected_contribution,
        "risks": plan.risks,
        "limitations": plan.limitations,
        "reproducibility_requirements": plan.reproducibility_requirements,
        "supporting_papers": plan.supporting_papers,
        "evidence_references": plan.evidence_references,
        "researcher_decisions": [
            {
                "field_name": dec.field_name,
                "ai_suggestion": dec.ai_suggestion,
                "researcher_decision": dec.researcher_decision,
                "final_value": dec.final_value,
                "decision_timestamp": dec.decision_timestamp.isoformat(),
                "evidence_references": dec.evidence_references,
            }
            for dec in plan.researcher_decisions
        ],
        "status": plan.status,
        "created_at": plan.created_at.isoformat(),
        "updated_at": plan.updated_at.isoformat(),
    }
```

**Frontend (TypeScript):**
```typescript
export interface ResearchPlan {
  id: string;
  workspace_id: number;
  user_id: number;
  artifact_id: string;
  opportunity_id: string;
  opportunity_description: string;
  title: string;
  research_problem: string;
  research_question: string;
  hypothesis: string;
  objectives: string;
  proposed_methodology: string;
  alternative_methodology: string;
  datasets: string;
  variables: string;
  baselines: string;
  evaluation_metrics: string;
  expected_contribution: string;
  risks: string;
  limitations: string;
  reproducibility_requirements: string;
  supporting_papers: number[];
  evidence_references: string[];
  researcher_decisions: ResearcherDecision[];
  status: 'draft' | 'review' | 'final' | 'archived';
  created_at: string;
  updated_at: string;
}
```

**Discrepancies:**
1. Frontend `status` is a union type `'draft' | 'review' | 'final' | 'archived'`; backend sends generic `string`
2. Backend serializes `decision_timestamp` as ISO string; frontend expects string - matches
3. Backend serializes `created_at`/`updated_at` as ISO string; frontend expects string - matches

**Impact:** Low - Status is string in both, frontend union is more restrictive but compatible

---

### 5. ResearcherDecision

**Backend (Dataclass):**
```python
@dataclass
class ResearcherDecision:
    field_name: str
    ai_suggestion: str
    researcher_decision: str  # "ACCEPT" | "MODIFY" | "REJECT"
    final_value: str
    decision_timestamp: datetime = field(default_factory=_utcnow)
    evidence_references: List[str] = field(default_factory=list)
```

**Frontend (TypeScript):**
```typescript
export interface ResearcherDecision {
  field_name: string;
  ai_suggestion: string;
  researcher_decision: 'ACCEPT' | 'MODIFY' | 'REJECT';
  final_value: string;
  decision_timestamp: string;
  evidence_references: string[];
}
```

**Discrepancies:**
1. Backend `researcher_decision` is `str`; frontend is union type `'ACCEPT' | 'MODIFY' | 'REJECT'`
2. Backend `decision_timestamp` is `datetime`; frontend expects `string` (backend serializes to ISO)

**Impact:** Low - Backend serializes datetime to string, union type is compatible

---

## Recommendations

### High Priority
None

### Medium Priority
1. **Remove unused fields from frontend CreateResearchPlanRequest**
   - Remove `topic` and `paper_ids` from WorkspaceScopedRequest extension
   - These fields are not used by the backend endpoint
   - Prevents confusion

2. **Align status field types**
   - Consider adding enum validation to backend Pydantic model
   - Or relax frontend union type to `string`
   - Current implementation works but could be more consistent

### Low Priority
1. **Make researcher_decisions type more specific in backend**
   - Backend uses `Optional[List[Dict[str, Any]]]`
   - Could use a Pydantic model for better type safety
   - Current implementation works

---

## Conclusion

API contracts are largely consistent with minor discrepancies that do not impact functionality. The main issues are:
- Extra fields in frontend request (ignored by backend)
- Status field type differences (compatible)
- Researcher decision typing differences (compatible)

**API Contract Validation Result:** ✅ PASS with recommendations
