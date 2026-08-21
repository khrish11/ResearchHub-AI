# PHASE 5.2 AUDIT: Research Opportunity → Research Plan

**Date:** 2025-01-XX
**Objective:** Audit existing implementations to determine what can be reused for Research Plan functionality.

---

## Executive Summary

The audit reveals that most foundational components exist for Research Plan functionality. The main gaps are:
- No persistent ResearchPlan data model
- No Research Plan generation service
- No researcher decision layer infrastructure
- No structured plan-to-document conversion

**Key Findings:**
- ✅ ResearchIntelligenceArtifact contains opportunity_ranking data
- ✅ StructuredGap data model exists
- ✅ ResearchOpportunity data model exists in frontend
- ✅ WorkspaceDocument can store structured content
- ✅ ResearchReport generation pattern exists
- ✅ AI service orchestration pattern exists
- ❌ No ResearchPlan data model
- ❌ No plan generation service
- ❌ No researcher decision tracking
- ❌ No plan-to-DocSpace conversion

---

## Existing Data Models

### 1. ResearchIntelligenceArtifact

**Location:** `backend/repositories/research.py` (lines 346-368)

```python
@dataclass
class ResearchIntelligenceArtifact:
    id: str
    workspace_id: int
    user_id: int
    topic: str
    paper_ids: List[int]
    paper_count: int
    status: str  # "running" | "completed" | "partial" | "failed"
    pipeline_version: str
    created_at: datetime
    updated_at: datetime
    evidence_analysis: Optional[Dict[str, Any]] = None
    gap_analysis: Optional[Dict[str, Any]] = None
    opportunity_ranking: Optional[Dict[str, Any]] = None  # ✅ Source of opportunities
    research_questions: Optional[Dict[str, Any]] = None
    hypothesis_challenges: Optional[Dict[str, Any]] = None
    citation_verification: Optional[Dict[str, Any]] = None
    knowledge_graph: Optional[Dict[str, Any]] = None
    overall_score: Optional[int] = None
    summary: Optional[str] = None
    stage_errors: Optional[Dict[str, str]] = None
```

**Reusability for Research Plans:**
- ✅ `opportunity_ranking` contains the source opportunities
- ✅ `paper_ids` provides supporting papers
- ✅ `topic` provides research context
- ✅ `workspace_id` and `user_id` for authorization
- ✅ Artifact ID for provenance tracking

**Opportunity ID Issue:**
- ⚠️ Opportunities in `opportunity_ranking` do not have stable IDs
- ⚠️ Opportunities are identified by `gap_id` which is derived from gap analysis
- ⚠️ Need to derive a stable opportunity ID from: `{artifact_id}_{gap_id}_{rank}`

---

### 2. StructuredGap

**Location:** `backend/repositories/research.py` (lines 330-343)

```python
@dataclass
class StructuredGap:
    category: str  # methodological, dataset, evaluation, etc.
    description: str
    confidence: int  # 0-100
    evidence_count: int
    novelty_potential: int  # 0-100
    research_impact: int  # 0-100
    feasibility: int  # 0-100
    recency: int  # 0-100
    supporting_papers: List[int]
    counter_evidence: List[int]
    affected_papers: List[int]
    explanation: str
```

**Reusability for Research Plans:**
- ✅ Source of research problems
- ✅ Evidence backing for methodology decisions
- ✅ Feasibility and impact scores for plan prioritization
- ✅ Supporting papers for literature review

---

### 3. ResearchOpportunity (Frontend)

**Location:** `frontend/src/api/researchIntelligence.ts` (lines 125-139)

```typescript
export interface ResearchOpportunity {
  gap_id: string;
  gap_description: string;
  category: string;
  evidence_strength: number;
  novelty: number;
  impact: number;
  feasibility: number;
  recency: number;
  overall_score: number;
  rank: number;
  explanation: string;
  supporting_papers: number[];
  affected_papers: number[];
}
```

**Reusability for Research Plans:**
- ✅ Opportunity selection UI already exists
- ✅ All metadata needed for plan generation
- ⚠️ No stable ID (uses gap_id + rank)

---

### 4. WorkspaceDocument

**Location:** `backend/repositories/research.py` (lines 222-231)

```python
@dataclass
class WorkspaceDocument:
    id: Optional[int]
    workspace_id: int
    user_id: int
    title: str
    content: str = ""
    version: int = 1
    created_at: datetime
    updated_at: datetime
```

**Reusability for Research Plans:**
- ✅ Can store research plans as structured documents
- ✅ Auto-save functionality exists
- ✅ Workspace authorization exists
- ⚠️ Content is unstructured markdown - would need structured-to-markdown conversion
- ⚠️ No field-level editing or decision tracking

**Decision:** Use WorkspaceDocument for final plan storage, but create a separate ResearchPlan model for structured editing and decision tracking.

---

### 5. ResearchReport

**Location:** `backend/repositories/research.py` (lines 300-310)

```python
@dataclass
class ResearchReport:
    id: str
    user_id: int
    paper_ids: List[int]
    topic: Optional[str] = None
    fingerprint: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    intelligence_artifact_id: Optional[str] = None
    workspace_id: Optional[int] = None
    created_at: datetime = field(default_factory=_utcnow)
```

**Reusability for Research Plans:**
- ✅ Pattern for artifact-backed reports
- ✅ Provenance tracking pattern
- ✅ Workspace association pattern
- ❌ ResearchPlan is different from a report (plan vs. executed research)

**Decision:** Do not reuse ResearchReport. Create separate ResearchPlan model.

---

## Existing Services

### 1. AI Service Orchestration

**Location:** `backend/services/ai_service.py`

**Pattern:**
```python
async def run_structured_json_task(
    system_prompt: str,
    user_prompt: str,
    output_schema: Dict[str, Any],
    ...
) -> Dict[str, Any]:
```

**Reusability for Research Plan Generation:**
- ✅ Structured JSON output generation
- ✅ Schema validation
- ✅ Error handling and retries
- ✅ Can be used for plan field generation

---

### 2. Opportunity Scoring Service

**Location:** `backend/services/opportunity_scoring_service.py`

**Capabilities:**
- Ranks gaps by research potential
- Calculates evidence strength, novelty, impact, feasibility
- Provides opportunity explanations

**Reusability for Research Plans:**
- ✅ Source of opportunity data
- ✅ Scoring methodology can inform plan prioritization
- ⚠️ Does not generate research plans

---

## Existing API Patterns

### 1. Artifact CRUD Pattern

**Endpoints:**
- POST `/research/intelligence` - Create
- GET `/research/intelligence/{artifact_id}` - Get
- GET `/workspaces/{workspace_id}/research-intelligence` - List
- DELETE `/research/intelligence/{artifact_id}` - Delete

**Authorization Pattern:**
```python
workspace = repo.find_workspace_for_user(workspace_id, current_user.id)
if not workspace:
    raise HTTPException(status_code=404, detail="Workspace not found")
```

**Reusability for Research Plans:**
- ✅ Same authorization pattern should be used
- ✅ Same CRUD endpoint structure
- ✅ Same workspace ownership verification

---

## Frontend Components

### 1. OpportunityRanking Component

**Location:** `frontend/src/features/research-intelligence/OpportunityRanking.tsx`

**Capabilities:**
- Displays ranked opportunities
- Shows opportunity scores
- Opportunity selection UI

**Reusability for Research Plans:**
- ✅ Can add "Develop Research Plan" button to opportunity cards
- ✅ Opportunity data already available
- ⚠️ No plan generation UI exists

---

### 2. DocSpace Component

**Location:** `frontend/src/pages/DocSpace.tsx`

**Capabilities:**
- Markdown editing
- Auto-save
- Citation insertion
- Paper reference insertion

**Reusability for Research Plans:**
- ✅ Can be used for final plan editing
- ✅ Can display generated plans
- ⚠️ No structured plan editing UI
- ⚠️ No decision tracking UI

---

## Gaps Analysis

### Missing Data Models

1. **ResearchPlan** - Core persistent model for research plans
2. **ResearcherDecision** - Track researcher decisions on AI suggestions
3. **PlanField** - Individual plan fields with AI suggestion and researcher decision

### Missing Services

1. **Research Plan Generation Service** - Generate plan fields from opportunities
2. **Plan-to-DocSpace Converter** - Convert structured plan to markdown document

### Missing UI Components

1. **Research Plan Builder** - Structured plan editing interface
2. **Decision Tracking UI** - Accept/Modify/Reject interface for AI suggestions
3. **Plan Status Management** - Draft/Review/Final status transitions

### Missing API Endpoints

1. POST `/research/plans` - Create plan
2. GET `/research/plans/{id}` - Get plan
3. GET `/research/workspaces/{workspace_id}/plans` - List plans
4. PUT `/research/plans/{id}` - Update plan
5. DELETE `/research/plans/{id}` - Delete plan
6. POST `/research/plans/generate` - Generate plan suggestions

---

## Recommendations

### 1. Data Model

**Create new ResearchPlan dataclass** with fields:
- id, workspace_id, user_id, artifact_id, opportunity_id
- title, research_problem, research_question, hypothesis
- objectives, proposed_methodology, alternative_methodology
- datasets, variables, baselines, evaluation_metrics
- expected_contribution, risks, limitations, reproducibility_requirements
- supporting_papers, evidence_references
- researcher_decisions (structured field decisions)
- status (draft, review, final, archived)
- created_at, updated_at

**Create ResearcherDecision tracking** for each field:
- ai_suggestion
- researcher_decision (ACCEPT | MODIFY | REJECT)
- final_value
- decision_timestamp

### 2. Opportunity ID Strategy

**Derive stable opportunity ID from:**
```
opportunity_id = f"{artifact_id}_{gap_id}_{rank}"
```

This ensures:
- Unique identification per artifact
- Traceability back to source gap
- Stable across plan lifecycle

### 3. Service Layer

**Create ResearchPlanService** with:
- `generate_plan_suggestions(opportunity, artifact, papers)` - Generate AI suggestions
- `create_plan(...)` - Create new plan
- `update_plan_field(plan_id, field, decision, value)` - Update field with decision
- `convert_to_document(plan)` - Convert to WorkspaceDocument

### 4. AI Generation Approach

**Use existing `run_structured_json_task`** with:
- System prompt: Research plan generation expert
- User prompt: Opportunity context + artifact data + papers
- Output schema: Structured plan fields with evidence backing

**Evidence backing for each field:**
- Methodology: Based on papers X, Y, Z
- Datasets: Suggested from paper data sections
- Metrics: Common metrics in this domain

### 5. Researcher Decision Layer

**Implement as structured field updates:**
- Each field has: ai_suggestion, researcher_decision, final_value
- UI shows: AI suggestion + editable input + Accept/Modify/Reject buttons
- Backend stores both AI suggestion and final researcher decision
- Regeneration never overwrites researcher decisions

### 6. DocSpace Integration

**Two-stage approach:**
1. **Structured Editing:** Research Plan Builder component
2. **Document Export:** Convert to WorkspaceDocument for final editing in DocSpace

**Conversion strategy:**
- Structured fields → Markdown sections
- Preserve provenance in document metadata
- Link back to original plan for traceability

---

## Implementation Priority

1. **High Priority:**
   - ResearchPlan data model
   - ResearchPlanService (generation)
   - API endpoints (CRUD)
   - Basic Research Plan Builder UI

2. **Medium Priority:**
   - Researcher decision tracking
   - Decision UI (Accept/Modify/Reject)
   - Plan status management

3. **Low Priority:**
   - DocSpace integration
   - Advanced decision analytics
   - Plan templates

---

## Security Considerations

- ✅ Workspace authorization pattern exists
- ✅ User authentication exists
- ⚠️ Need to verify plan ownership on all operations
- ⚠️ Need to prevent cross-workspace plan access
- ⚠️ Need to validate opportunity belongs to user's workspace

---

## Performance Considerations

- ✅ Artifact caching exists
- ✅ Paper caching exists
- ⚠️ Plan generation may be slow (large AI context)
- ⚠️ Consider streaming plan field generation
- ⚠️ Cache generated plans for same opportunity

---

## Conclusion

The existing infrastructure provides a solid foundation for Research Plan functionality. The main work is:
1. Creating the ResearchPlan data model
2. Building the plan generation service
3. Implementing the researcher decision layer
4. Creating the structured plan editing UI

The audit confirms that we should create a new ResearchPlan model rather than reusing existing models, as the use case is distinct from both ResearchIntelligenceArtifact and WorkspaceDocument.
