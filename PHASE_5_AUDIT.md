# PHASE 5: Research Workflow Intelligence & Academic Output - Audit Report

**Date:** 2025-01-XX  
**Objective:** Audit existing systems before implementing PHASE 5 research workflow enhancements.  
**Scope:** Identify reusable components, persistence mechanisms, integration points, and missing capabilities.

---

## Executive Summary

The audit reveals a solid foundation with existing DocSpace/editor infrastructure, Research Intelligence Artifacts, and report generation capabilities. Key gaps are in persistent research objects (questions, plans, blueprints) and workflow integration between intelligence analysis and academic output generation.

**Key Findings:**
- ✅ DocSpace provides workspace document persistence and editing
- ✅ Research Intelligence Artifacts fully implemented with 7-stage pipeline
- ✅ Report generation with intelligence backing and provenance
- ✅ Research Question Service exists but questions are transient
- ❌ No persistent research questions
- ❌ No research plan/blueprint objects
- ❌ No methodology advisor service
- ❌ No contribution builder
- ❌ No researcher decision layer

---

## Existing Reusable Components

### 1. DocSpace / Workspace Document System

**Location:** `frontend/src/pages/DocSpace.tsx`, `backend/routers/workspaces.py`

**Capabilities:**
- Workspace-scoped document persistence (title, content, version)
- Auto-save with debouncing (900ms)
- Real-time sync with conflict resolution
- Citation insertion from papers
- Paper reference insertion
- Abstract insertion
- Markdown-based editing

**Backend Data Model:**
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

**API Endpoints:**
- GET `/workspaces/{workspace_id}/docspace` - Load document
- PUT `/workspaces/{workspace_id}/docspace` - Save document

**Reusability for PHASE 5:**
- ✅ Can store research blueprints as workspace documents
- ✅ Can store methodology notes
- ✅ Can store contribution drafts
- ✅ Already has workspace authorization
- ✅ Auto-save functionality ready

---

### 2. Research Intelligence Artifacts

**Location:** `backend/repositories/research.py` (lines 346-368), `backend/routers/research_agent.py`

**Capabilities:**
- 7-stage intelligence pipeline (evidence, gaps, opportunities, questions, challenge, citations, graph)
- Full artifact lifecycle (create, read, update, delete)
- Workspace ownership validation
- Status tracking (running, completed, partial, failed)
- Provenance metadata

**Backend Data Model:**
```python
@dataclass
class ResearchIntelligenceArtifact:
    id: str
    workspace_id: int
    user_id: int
    topic: str
    paper_ids: List[int]
    paper_count: int
    status: str
    pipeline_version: str
    created_at: datetime
    updated_at: datetime
    evidence_analysis: Optional[Dict[str, Any]]
    gap_analysis: Optional[Dict[str, Any]]
    opportunity_ranking: Optional[Dict[str, Any]]
    research_questions: Optional[Dict[str, Any]]
    hypothesis_challenges: Optional[Dict[str, Any]]
    citation_verification: Optional[Dict[str, Any]]
    knowledge_graph: Optional[Dict[str, Any]]
    overall_score: Optional[int]
    summary: Optional[str]
    stage_errors: Optional[Dict[str, str]]
```

**API Endpoints:**
- POST `/research/intelligence` - Create artifact
- GET `/research/intelligence/{artifact_id}` - Get artifact
- GET `/workspaces/{workspace_id}/research-intelligence` - List artifacts
- DELETE `/research/intelligence/{artifact_id}` - Delete artifact

**Reusability for PHASE 5:**
- ✅ Source of gaps for research questions
- ✅ Source of opportunities for research plans
- ✅ Source of evidence for methodology advisor
- ✅ Provenance tracking already implemented
- ✅ Workspace authorization pattern established

---

### 3. Research Question Service

**Location:** `backend/services/research_question_service.py`

**Capabilities:**
- Generates research questions from gaps
- Question categorization (exploratory, confirmatory, comparative, causal)
- Complexity scoring (simple, moderate, complex)
- Evidence-based grounding
- Caching (10-minute TTL)

**Data Model:**
```python
@dataclass
class ResearchQuestion:
    id: str
    question: str
    category: str
    complexity: str
    confidence: int
    novelty: int
    feasibility: int
    impact: int
    source_gap_id: str
    source_gap_description: str
    supporting_papers: List[int]
    rationale: str
```

**Current Limitation:**
- ❌ Questions are transient (not persisted to database)
- ❌ No workspace association
- ❌ No CRUD operations

**Reusability for PHASE 5:**
- ✅ Question generation logic already exists
- ✅ Can be extended with persistence layer
- ✅ Can integrate with workspace documents

---

### 4. Report Generation

**Location:** `backend/routers/research_agent.py`, `frontend/src/pages/ResearchReport.tsx`

**Capabilities:**
- Standard report generation from papers
- Intelligence-backed report generation from artifacts
- Provenance metadata tracking
- Fallback mechanisms for AI failures
- Export to markdown/PDF
- Save to workspace notes

**Intelligence-Backed Report Structure:**
- Title, Abstract, Key Themes
- Literature Overview, Methodology Trends
- Consensus Findings, Conflicting Views
- Research Gaps, Future Directions
- Conclusion
- Provenance metadata (artifact_id, workspace_id, paper_ids, score, generated_at)

**Reusability for PHASE 5:**
- ✅ Can be extended for blueprint-based reports
- ✅ Provenance pattern established
- ✅ Export functionality exists
- ✅ Workspace integration exists

---

### 5. Citation Service

**Location:** `backend/services/citation_service.py`

**Capabilities:**
- Citation generation in multiple formats (APA, MLA, Chicago, BibTeX)
- Paper metadata extraction
- DOI resolution

**Reusability for PHASE 5:**
- ✅ Can be used for blueprint references
- ✅ Can be used for methodology citations
- ✅ Can be used for contribution attribution

---

## Existing Persistence Mechanisms

### Firestore Collections

**Existing Collections:**
1. `users` - User accounts
2. `workspaces` - Research workspaces
3. `papers` - Paper metadata
4. `chats` - Chat history
5. `workspace_documents` - DocSpace documents
6. `research_intelligence_artifacts` - Intelligence artifacts
7. `workspace_files` - File storage records
8. `paper_check_jobs` - Paper check jobs
9. `search_history` - Search history
10. `user_session_state` - Session state

**Repository Pattern:**
- `ResearchRepository` protocol with Firestore and in-memory implementations
- Consistent CRUD patterns
- Workspace ownership validation
- User authorization checks

**Reusability for PHASE 5:**
- ✅ Can add new collections for research questions, plans, blueprints
- ✅ Repository pattern established for new data models
- ✅ Authorization helpers available

---

## Integration Points

### 1. Intelligence → Questions

**Current Flow:**
```
Gaps → ResearchQuestionService.generate_questions() → Transient questions
```

**Proposed Flow:**
```
Gaps → ResearchQuestionService.generate_questions() → Persist to Firestore → Display in UI
```

**Integration Point:**
- Extend `ResearchQuestionService` with persistence
- Add repository methods for question CRUD
- Add API endpoints for question management

---

### 2. Questions → Plans

**Current Flow:**
```
None (questions are transient)
```

**Proposed Flow:**
```
Saved Question + Opportunity → ResearchPlanService.generate_plan() → Persist plan
```

**Integration Point:**
- Create new `ResearchPlan` dataclass
- Create `ResearchPlanService` for plan generation
- Integrate with existing LLM client

---

### 3. Plans → Methodology

**Current Flow:**
```
None
```

**Proposed Flow:**
```
Research Plan + Evidence → MethodologyAdvisor.generate_recommendations() → Persist methodology
```

**Integration Point:**
- Create `MethodologyAdvisor` service
- Build on existing `research_agent.py` LLM integration
- Use evidence from intelligence artifact

---

### 4. All → Blueprints

**Current Flow:**
```
None
```

**Proposed Flow:**
```
Question + Plan + Methodology + Contribution → ResearchBlueprint → Persist as WorkspaceDocument
```

**Integration Point:**
- Create `ResearchBlueprint` dataclass
- Use existing `WorkspaceDocument` for persistence
- Integrate with DocSpace for editing

---

### 5. Intelligence → Writing

**Current Flow:**
```
Intelligence Artifact → Report Generation → Display
```

**Proposed Flow:**
```
Intelligence Artifact → Insert into DocSpace with provenance → Editable document
```

**Integration Point:**
- Extend DocSpace with intelligence insertion actions
- Add provenance metadata to document content
- Create UI actions for "Use this Gap/Question/Opportunity"

---

## Missing Workflow Capabilities

### 1. Persistent Research Questions

**Current State:**
- Questions generated but not persisted
- No workspace association
- No CRUD operations

**Required:**
- Firestore collection for research questions
- Repository CRUD methods
- API endpoints (create, list, get, delete)
- Frontend UI for saving/loading questions
- Workspace authorization

**Complexity:** Low (extends existing pattern)

---

### 2. Research Plans

**Current State:**
- No research plan concept
- No plan generation service

**Required:**
- `ResearchPlan` dataclass
- `ResearchPlanService` for plan generation
- Firestore collection for plans
- Repository CRUD methods
- API endpoints
- Frontend UI for plan development
- Researcher decision layer (accept/reject/modify)

**Complexity:** Medium (new service, but builds on existing patterns)

---

### 3. Methodology Advisor

**Current State:**
- No methodology advisor service
- No methodology recommendations

**Required:**
- `MethodologyAdvisor` service
- LLM-based methodology generation
- Evidence-backed recommendations
- Traceability (supporting papers, confidence)
- Distinction between evidence-backed and AI-generated

**Complexity:** Medium (new service, but builds on existing LLM integration)

---

### 4. Contribution Builder

**Current State:**
- No contribution builder
- No contribution types defined

**Required:**
- `ContributionBuilder` service
- Contribution type definitions (methodological, dataset, benchmark, empirical, theoretical, system/tool)
- Novelty assessment (signal vs proven)
- Feasibility and impact scoring
- Frontend UI for contribution development

**Complexity:** Medium (new service, but builds on existing patterns)

---

### 5. Research Blueprints

**Current State:**
- No blueprint concept
- No blueprint persistence

**Required:**
- `ResearchBlueprint` dataclass (or use WorkspaceDocument)
- Blueprint structure (title, problem, question, hypothesis, methodology, etc.)
- CRUD operations
- Export functionality
- Integration with DocSpace for editing
- Frontend UI for blueprint management

**Complexity:** Low to Medium (can reuse WorkspaceDocument)

---

### 6. Researcher Decision Layer

**Current State:**
- No explicit researcher decisions
- No decision persistence

**Required:**
- Decision data model (AI recommendation, researcher decision, timestamp)
- Decision persistence (within blueprint or separate)
- UI for decision recording (accept/reject/modify)
- Decision provenance tracking

**Complexity:** Low (add fields to existing objects)

---

### 7. Intelligence → Writing Integration

**Current State:**
- Report generation exists
- No direct intelligence insertion into writing

**Required:**
- UI actions for "Use this Gap/Question/Opportunity"
- Provenance metadata preservation
- Insertion into DocSpace with source tracking
- Citation integration

**Complexity:** Medium (requires UI work and provenance design)

---

### 8. Evidence-First Report Generation

**Current State:**
- Report generation uses intelligence artifact
- Report structure is generic

**Required:**
- Enhanced report structure for intelligence-backed reports
- Evidence-first organization
- Clear distinction between observed evidence, AI interpretation, researcher decision
- Blueprint-based report generation

**Complexity:** Low to Medium (extends existing report generation)

---

## Recommended Implementation Order

### Phase 5.1: Research Question Persistence (Low Risk)
1. Add `SavedResearchQuestion` dataclass to `repositories/research.py`
2. Add repository CRUD methods for questions
3. Add API endpoints for question management
4. Extend frontend to save/load/delete questions
5. Add workspace authorization tests

**Rationale:** Low complexity, extends existing pattern, immediate value

---

### Phase 5.2: Research Plan Generation (Medium Risk)
1. Add `ResearchPlan` dataclass
2. Create `ResearchPlanService` for plan generation
3. Add repository CRUD methods
4. Add API endpoints
5. Create frontend UI for plan development
6. Add researcher decision UI

**Rationale:** Builds on questions, establishes plan concept

---

### Phase 5.3: Methodology Advisor (Medium Risk)
1. Create `MethodologyAdvisor` service
2. Implement methodology generation using existing LLM client
3. Add evidence-backed recommendation logic
4. Add traceability (supporting papers, confidence)
5. Integrate with research plans

**Rationale:** Enhances plans with methodology guidance

---

### Phase 5.4: Contribution Builder (Medium Risk)
1. Create `ContributionBuilder` service
2. Define contribution types
3. Implement contribution generation
4. Add novelty assessment (signal vs proven)
5. Create frontend UI

**Rationale:** Completes plan with contribution analysis

---

### Phase 5.5: Research Blueprint (Low Risk)
1. Design `ResearchBlueprint` structure (or use WorkspaceDocument)
2. Implement blueprint aggregation (question + plan + methodology + contribution)
3. Add CRUD operations
4. Add export functionality
5. Integrate with DocSpace for editing
6. Create frontend UI

**Rationale:** Brings everything together into actionable blueprint

---

### Phase 5.6: Intelligence → Writing Integration (Medium Risk)
1. Design provenance metadata format
2. Add UI actions for intelligence insertion
3. Implement insertion into DocSpace with source tracking
4. Add citation integration
5. Test provenance preservation

**Rationale:** Connects intelligence to writing workflow

---

### Phase 5.7: Evidence-First Report Generation (Low Risk)
1. Enhance report structure for intelligence-backed reports
2. Add evidence-first organization
3. Add distinction between evidence/interpretation/decision
4. Add blueprint-based report generation
5. Test with existing artifacts

**Rationale:** Improves report quality with evidence-first approach

---

### Phase 5.8: Researcher Decision Layer (Low Risk)
1. Add decision data model
2. Add decision persistence
3. Create decision UI components
4. Integrate decisions into blueprints
5. Add decision provenance tracking

**Rationale:** Ensures researcher agency in workflow

---

### Phase 5.9: Workflow UI Improvements (Medium Risk)
1. Redesign ResearchIntelligencePage with workflow focus
2. Add action buttons at each stage
3. Improve navigation between stages
4. Add progress tracking
5. Add next-step guidance

**Rationale:** Improves UX and guides user through workflow

---

### Phase 5.10-5.14: Testing, Security, Performance, Validation (Standard)
1. Add backend tests for all new endpoints
2. Add frontend tests for new UI flows
3. Conduct security audit
4. Conduct performance audit
5. Validate complete end-to-end workflow

**Rationale:** Ensures production readiness

---

## Architecture Recommendations

### 1. Data Model Strategy

**Option A: New Collections**
- Create separate collections for questions, plans, blueprints
- Pros: Clean separation, independent lifecycle
- Cons: More collections to manage, potential duplication

**Option B: Extend WorkspaceDocument**
- Use `WorkspaceDocument` with kind/type field
- Pros: Reuse existing infrastructure, simpler
- Cons: Mixed concerns, potential size limits

**Recommendation:** Option A for questions and plans, Option B for blueprints

---

### 2. Service Layer Strategy

**Pattern:** Follow existing service pattern
- Service class with caching
- Feature flags for new features
- Global service instance with getter function
- Integration with existing LLM client

**Example:**
```python
RESEARCH_PLAN_GENERATION_ENABLED = os.getenv("RESEARCH_PLAN_GENERATION_ENABLED", "1")

class ResearchPlanService:
    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._cache_ttl_seconds = 10 * 60
    
    def generate_plan(self, question, opportunity, artifact):
        # Implementation
        pass

_plan_service: Optional[ResearchPlanService] = None

def get_plan_service() -> ResearchPlanService:
    global _plan_service
    if _plan_service is None:
        _plan_service = ResearchPlanService()
    return _plan_service
```

---

### 3. Authorization Strategy

**Pattern:** Follow existing authorization pattern
- Workspace ownership validation via `repo.workspace_exists_for_user()`
- User ID filtering in list operations
- 403 errors for unauthorized access
- Artifact ownership validation for intelligence-backed operations

**Helper Function:**
```python
def _workspace_or_default(
    workspace_id: Optional[int],
    current_user: User,
    repo: ResearchRepository,
) -> int:
    if workspace_id is not None:
        workspace = repo.find_workspace_for_user(workspace_id, current_user.id)
        if not workspace:
            raise HTTPException(status_code=403, detail="Access denied")
        return workspace_id
    # Default workspace logic
    return default_workspace_id
```

---

### 4. Provenance Strategy

**Pattern:** Follow existing provenance pattern from intelligence artifacts
- Include source artifact ID
- Include workspace ID
- Include paper IDs
- Include generation timestamp
- Include confidence scores
- Distinguish between evidence-backed and AI-generated

**Example:**
```python
"_provenance": {
    "source_artifact_id": artifact_id,
    "source_question_id": question_id,
    "workspace_id": workspace_id,
    "paper_ids": paper_ids,
    "evidence_type": "observed" | "inferred" | "ai_generated",
    "confidence": 85,
    "generated_at": datetime.now(timezone.utc).isoformat(),
}
```

---

### 5. Frontend State Management

**Pattern:** Follow existing React patterns
- Use React state for local UI state
- Use API calls for persistence
- Use sessionStorage for temporary data transfer
- Use toast notifications for feedback
- Use disabled states for validation

**Example:**
```typescript
const [questions, setQuestions] = useState<SavedQuestion[]>([]);
const [loading, setLoading] = useState(false);
const { success: toastSuccess, error: toastError } = useToast();

const handleSaveQuestion = async (question: ResearchQuestion) => {
  setLoading(true);
  try {
    await saveResearchQuestion(question);
    toastSuccess('Question saved');
    // Refresh list
  } catch {
    toastError('Failed to save question');
  } finally {
    setLoading(false);
  }
};
```

---

## Security Considerations

### Existing Security Patterns

1. **Authentication:** All endpoints require `get_current_user` dependency
2. **Workspace Authorization:** `repo.workspace_exists_for_user()` validation
3. **Artifact Authorization:** Artifact ownership checks
4. **User ID Filtering:** List operations filter by user_id
5. **IDOR Prevention:** Ownership checks before access

### New Security Requirements

1. **Question Authorization:** Questions must be workspace-scoped
2. **Plan Authorization:** Plans must be workspace-scoped
3. **Blueprint Authorization:** Blueprints must be workspace-scoped
4. **Decision Authorization:** Decisions must be user-owned
5. **AI Output Sanitization:** Validate AI-generated content before persistence
6. **Citation Validation:** Ensure citations reference actual papers in workspace

### Security Audit Checklist

- [ ] All new endpoints require authentication
- [ ] All new objects have workspace ownership validation
- [ ] All list operations filter by user_id
- [ ] All delete operations verify ownership
- [ ] No IDOR vulnerabilities
- [ ] AI output is sanitized
- [ ] Citations are validated
- [ ] No prompt injection through paper content
- [ ] No sensitive information leakage

---

## Performance Considerations

### Existing Performance Patterns

1. **Caching:** Services use in-memory caching with TTL
2. **Debouncing:** DocSpace uses 900ms debounce for auto-save
3. **Pagination:** List operations should support pagination
4. **Lazy Loading:** Frontend loads data on demand
5. **Batch Operations:** Minimize Firestore reads

### New Performance Requirements

1. **Question Caching:** Cache question generation results
2. **Plan Caching:** Cache plan generation results
3. **Methodology Caching:** Cache methodology recommendations
4. **Blueprint Size:** Monitor blueprint document size
5. **Provenance Overhead:** Minimize provenance metadata size

### Performance Audit Checklist

- [ ] No repeated intelligence execution
- [ ] No duplicate AI calls
- [ ] No unnecessary Firestore reads
- [ ] No repeated artifact loading
- [ ] No unnecessary React renders
- [ ] Caching implemented where appropriate
- [ ] Pagination for large lists
- [ ] Lazy loading for large documents

---

## Testing Strategy

### Backend Tests

**New Test Files:**
1. `test_saved_research_questions.py` - Question CRUD, authorization
2. `test_research_plans.py` - Plan generation, CRUD, authorization
3. `test_methodology_advisor.py` - Methodology generation, traceability
4. `test_contribution_builder.py` - Contribution generation, novelty assessment
5. `test_research_blueprints.py` - Blueprint CRUD, export, authorization

**Test Coverage:**
- CRUD operations for all new objects
- Workspace authorization
- User authorization
- Artifact authorization
- Malformed requests
- AI failure handling
- Partial intelligence artifact handling
- Authorization failures
- IDOR attempts

### Frontend Tests

**New Test Components:**
1. Question save/load/delete flow
2. Research plan development flow
3. Methodology advisor interaction
4. Contribution builder interaction
5. Blueprint creation/edit/export flow
6. Intelligence insertion into writing
7. Decision layer interaction

**Test Coverage:**
- Navigation between stages
- Loading states
- Error states
- Persistence after refresh
- Report generation
- DocSpace navigation
- Disabled states
- Validation

### Integration Tests

**End-to-End Workflows:**
1. Papers → Intelligence → Questions → Plans → Blueprints → Reports
2. Intelligence → Writing Integration
3. Blueprint → DocSpace → Export
4. Complete research workflow validation

---

## Known Limitations

### Existing Limitations

1. **Research Questions:** Transient, not persisted
2. **No Research Plans:** No plan concept
3. **No Methodology Advisor:** No methodology guidance
4. **No Contribution Builder:** No contribution analysis
5. **No Blueprints:** No blueprint concept
6. **No Decision Layer:** No explicit researcher decisions
7. **Writing Integration:** Limited intelligence insertion

### New Limitations After Implementation

1. **AI Hallucinations:** AI-generated methodology may contain errors
2. **Novelty Assessment:** Heuristic-based, not definitive
3. **Citation Accuracy:** Dependent on paper metadata quality
4. **Blueprint Size:** Large blueprints may hit Firestore limits
5. **Provenance Complexity:** Complex provenance may be hard to track

### Mitigation Strategies

1. **AI Hallucinations:** Clear labeling of AI-generated content, researcher review required
2. **Novelty Assessment:** Use "potentially novel" language, not definitive claims
3. **Citation Accuracy:** Validate citations against workspace papers
4. **Blueprint Size:** Use WorkspaceDocument with size monitoring
5. **Provenance Complexity:** Simplify provenance model, use references

---

## Conclusion

The audit reveals a solid foundation with existing DocSpace, Research Intelligence Artifacts, and report generation. The main gaps are in persistent research objects (questions, plans, blueprints) and workflow integration.

**Key Takeaways:**
- ✅ DocSpace provides excellent document persistence and editing
- ✅ Research Intelligence Artifacts are fully implemented
- ✅ Repository pattern and authorization patterns are established
- ✅ LLM integration is available via existing client
- ❌ Questions are transient and need persistence
- ❌ No research plan/blueprint concepts
- ❌ No methodology advisor or contribution builder
- ❌ Limited intelligence → writing integration

**Recommended Approach:**
1. Start with low-risk persistence (questions)
2. Build medium-risk services (plans, methodology, contributions)
3. Integrate with existing infrastructure (blueprints via WorkspaceDocument)
4. Enhance UI for workflow guidance
5. Ensure security and performance throughout

**Estimated Complexity:** Medium (builds on existing patterns, requires new services)

**Next Step:** Begin PHASE 5.1 - Research Question Persistence
