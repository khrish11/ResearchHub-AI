# PHASE 8.5 Pre-Implementation Audit

**Date:** 2026-08-25
**Objective:** Audit existing research workflow infrastructure before implementing PHASE 8.5 improvements
**Scope:** Frontend Research/Search/Intelligence, Backend Research APIs, Services, Repositories

---

## Executive Summary

The codebase has a **comprehensive but fragmented** research workflow infrastructure. Core functionality exists across multiple specialized services and components, but the user experience feels disconnected. PHASE 8.5 should focus on **cohering existing capabilities** rather than adding new features.

**Key Findings:**
- ✅ Strong foundation: Research classification, search enhancement, intelligence services all exist
- ⚠️ Fragmentation: Multiple entry points (Research, Search, Research Agent, Intelligence, Workspaces, Library)
- ⚠️ Context loss: Research context from Research.tsx not preserved in workspace
- ⚠️ Redundant destinations: Too many user-facing entry points
- ✅ Reusable APIs: Most required functionality already exists via research intelligence services

---

## 1. Frontend Components Audit

### 1.1 Research.tsx (`frontend/src/pages/Research.tsx`)

**Purpose:** Research question entry point with classification and clarification

**Current Flow:**
1. User enters research question
2. Classify query via `/research/classify` API
3. Optional clarification questions
4. Display research direction (topic, focus, research intent, suggested scope)
5. Actions: Start Research (→ Search), Deep Research (→ Research Agent), Save Question, Create Workspace

**Key Features:**
- Query classification with 8 categories (topic_exploration, research_question, problem_investigation, literature_review, comparison, methodology, trend_analysis, ambiguous)
- Clarification questions for ambiguous queries
- Research direction display with enhanced context
- Saves research context to sessionStorage (`RESEARCH_CONTEXT_KEY`)
- Hardcoded scores for saved questions (novelty: 75, feasibility: 70, impact: 80)

**Issues:**
- Research context saved to sessionStorage but not persisted to workspace
- No handoff to workspace when papers are selected
- "Save Research Question" requires workspace but doesn't create one automatically
- Hardcoded scores are not calculated dynamically

### 1.2 SearchPapersPage.tsx (`frontend/src/features/search/SearchPapersPage.tsx`)

**Purpose:** Global search across 28+ sources with research-aware query enhancement

**Current Flow:**
1. User enters search query (or redirected from Research)
2. Load research context from sessionStorage if available
3. Build research-enhanced query using `buildResearchEnhancedQuery()`
4. Execute search via `/papers/search-global`
5. Display results with filters, modes, actions

**Key Features (PHASE 8.4.4):**
- Research context loading from sessionStorage
- Research-enhanced query with intent-specific rules
- Toggle between original and enhanced query
- Search modes: Fast, Balanced, Deep
- Year filters, source filters
- Paper actions: Open, Add to Workspace, Save, Compare, Explain
- Workspace selection for paper import

**Issues:**
- Research context not preserved when papers are added to workspace
- No indication of which papers relate to the research question
- Search results not optimized for research use (generic presentation)

### 1.3 ResearchIntelligencePage.tsx (`frontend/src/features/research-intelligence/ResearchIntelligencePage.tsx`)

**Purpose:** Unified page for all research intelligence features

**Current Flow:**
1. User selects workspace
2. Run intelligence pipeline (evidence, gaps, opportunities, questions, challenge, citations, graph)
3. View results in specialized components
4. Generate research plans from opportunities

**Key Features:**
- Evidence Analysis
- Gap Detection (upgraded)
- Opportunity Ranking
- Research Question Generation
- Hypothesis Challenge
- Citation Verification
- Knowledge Graph Enhancement
- Research Plan Builder
- Artifact history

**Issues:**
- Standalone page, not integrated with Research → Search flow
- Requires manual workspace selection
- No connection to research context from Research.tsx

### 1.4 ResearchQuestionGenerator.tsx (`frontend/src/features/research-intelligence/ResearchQuestionGenerator.tsx`)

**Purpose:** Display generated research questions with scores

**Key Features:**
- Categories: Exploratory, Confirmatory, Comparative, Causal
- Scores: Complexity, Novelty, Impact, Feasibility (0-100)
- Actions: Add to workspace, Challenge, Save, Delete
- Top # ranking for top 3 questions

**Issues:**
- Scores displayed but calculation method unclear
- Hardcoded in Research.tsx, AI-generated in intelligence page (inconsistent)

### 1.5 ResearchPlanBuilder.tsx (`frontend/src/features/research-intelligence/ResearchPlanBuilder.tsx`)

**Purpose:** Build research plans from AI suggestions

**Key Features:**
- Accept/Modify/Reject decisions for each field
- Fields: Title, Research Problem, Research Question, Hypothesis, Methods, Expected Outcomes, Timeline, Resources
- Saves plan to workspace

**Issues:**
- Standalone component, not integrated with opportunity selection flow

### 1.6 Home.tsx (`frontend/src/pages/Home.tsx`)

**Purpose:** Dashboard with personalized recommendations

**Key Features:**
- Personalized paper recommendations via `/workspace-feed/recommendations`
- Recent workspaces
- Quick actions: Search, Deep Research, Upload
- Trending papers fallback

**Issues:**
- Does not answer "What am I researching?"
- Generic dashboard, not research-focused
- No connection to active research context

### 1.7 Workspaces.tsx (`frontend/src/pages/Workspaces.tsx`)

**Purpose:** Workspace management

**Key Features:**
- List workspaces with paper/chat counts
- Create workspace with name and description
- Navigate to workspace details

**Issues:**
- No display of research question/context
- Generic workspace cards
- No indication of active research

### 1.8 Library.tsx (`frontend/src/pages/Library.tsx`)

**Purpose:** Navigation hub for research assets

**Key Features:**
- Papers (→ Search)
- Saved Questions (workspace-scoped)
- Research Artifacts (workspace-scoped)
- Research Plans (workspace-scoped)
- Reports

**Issues:**
- Static navigation, not dynamic
- No actual functionality (just links)
- Saved Questions, Artifacts, Plans are described as "managed within individual workspaces" but no direct access

---

## 2. Backend APIs Audit

### 2.1 Research Agent Router (`backend/routers/research_agent.py`)

**Size:** 5930 lines (very large)

**Endpoints:**
- `/research/classify` - Query classification
- `/research/agent` - Deep research agent
- Multiple research intelligence endpoints (delegated to services)

**Issues:**
- Very large file, likely contains duplicated logic
- Mix of agent functionality and intelligence endpoints

### 2.2 Papers Router (`backend/routers/papers.py`)

**Size:** 6507 lines (very large)

**Key Endpoints:**
- `/papers/search-global` - Multi-source search (28+ sources)
- `/papers/{paper_id}` - Paper details
- `/papers/{paper_id}/explain` - Paper explanation
- `/papers/compare` - Paper comparison
- Workspace paper management

**Key Features:**
- Global search with caching, timeouts, concurrency control
- Source-specific timeouts and overrides
- Unpaywall integration
- Citation metadata

**Issues:**
- Very large file, could be split
- No research context preservation in paper import

### 2.3 Workspaces Router (`backend/routers/workspaces.py`)

**Size:** 1380 lines

**Key Endpoints:**
- `/workspaces/` - List/create workspaces
- `/workspaces/{workspace_id}` - Workspace details with papers/chats
- `/workspaces/{workspace_id}/papers` - Add/remove papers
- `/workspaces/{workspace_id}/report` - Generate report
- `/workspaces/session-state` - Session state management

**Key Features:**
- Workspace CRUD
- Paper management
- Chat management
- Report generation
- Session state persistence

**Issues:**
- Workspace model has `description` field but not used for research context
- No research question field in workspace model
- Session state exists but not used for research context persistence

### 2.4 Research Intelligence APIs

**Services:**
- `evidence_intelligence_service.py` - Evidence analysis
- `gap_intelligence_service.py` - Gap detection
- `opportunity_scoring_service.py` - Opportunity ranking
- `research_question_service.py` - Research question generation
- `research_challenger_service.py` - Hypothesis challenge
- `citation_verification_service.py` - Citation verification
- `knowledge_graph_enhancement_service.py` - Knowledge graph
- `research_plan_service.py` - Research plan generation
- `research_intelligence_artifact_service.py` - Artifact management

**Frontend API:** `frontend/src/api/researchIntelligence.ts` (784 lines)

**Key Endpoints:**
- `/research-intelligence/evidence` - Evidence analysis
- `/research-intelligence/gaps` - Gap detection
- `/research-intelligence/opportunities` - Opportunity ranking
- `/research-intelligence/questions` - Research question generation
- `/research-intelligence/challenge` - Hypothesis challenge
- `/research-intelligence/citations` - Citation verification
- `/research-intelligence/graph` - Knowledge graph enhancement
- `/research-intelligence/plan-suggestions` - Research plan suggestions
- `/research-intelligence/plan` - Create research plan
- `/research-intelligence/questions/save` - Save research question
- `/research-intelligence/questions/list` - List saved questions
- `/research-intelligence/questions/delete` - Delete saved question
- `/research-intelligence/artifacts` - Artifact management

**Status:** ✅ Comprehensive, well-structured, reusable

---

## 3. Backend Services Audit

### 3.1 Research Intelligence Services

**Evidence Intelligence Service** (`evidence_intelligence_service.py` - 16670 bytes)
- Analyzes claims against workspace papers
- Classifies evidence (supporting, contradicting, neutral)
- Provides evidence strength scores

**Gap Intelligence Service** (`gap_intelligence_service.py` - 18786 bytes)
- Detects research gaps in workspace papers
- Categories: methodological, empirical, theoretical, contextual
- Provides novelty potential and research impact scores

**Opportunity Scoring Service** (`opportunity_scoring_service.py` - 11551 bytes)
- Ranks research opportunities
- Scores: feasibility, impact, novelty
- Prioritizes gaps for investigation

**Research Question Service** (`research_question_service.py` - 10020 bytes)
- Generates research questions from gaps/opportunities
- Categories: exploratory, confirmatory, comparative, causal
- Scores: complexity, novelty, impact, feasibility

**Research Challenger Service** (`research_challenger_service.py` - 12816 bytes)
- Challenges hypotheses with counter-evidence
- Identifies weaknesses and alternative explanations

**Citation Verification Service** (`citation_verification_service.py` - 10187 bytes)
- Verifies citation integrity
- Identifies missing or incorrect citations

**Knowledge Graph Enhancement Service** (`knowledge_graph_enhancement_service.py` - 12891 bytes)
- Enhances knowledge graph with new relationships
- Identifies concept connections

**Research Plan Service** (`research_plan_service.py` - 11518 bytes)
- Generates research plan suggestions
- Fields: title, problem, question, hypothesis, methods, outcomes, timeline, resources

**Research Intelligence Artifact Service** (`research_intelligence_artifact_service.py` - 21827 bytes)
- Manages intelligence artifacts (snapshots of analysis)
- Versioning and history

**Status:** ✅ All services exist and are comprehensive
**Opportunity:** Reuse existing services, integrate better with Research → Search flow

### 3.2 Query Classification Service (`query_classification_service.py` - 9345 bytes)

**Purpose:** Classify research queries into intents

**Categories:**
- topic_exploration
- research_question
- problem_investigation
- literature_review
- comparison
- methodology
- trend_analysis
- ambiguous

**Features:**
- Heuristic-based classification (no LLM required)
- Confidence scores
- Clarification questions
- Research direction generation

**Status:** ✅ Well-implemented, used in Research.tsx

### 3.3 Other Services

**Paper Check Service** (`paper_check_service.py` - 52011 bytes)
- Very large service for paper verification
- Not directly relevant to PHASE 8.5

**Citation Service** (`citation_service.py` - 20564 bytes)
- Citation metadata and formatting
- Research artifacts generation

**AI Service** (`ai_service.py` - 30774 bytes)
- Generic AI task execution
- Used by intelligence services

**Status:** ✅ Adequate for PHASE 8.5 needs

---

## 4. Backend Repositories Audit

### 4.1 Research Repository (`backend/repositories/research.py`)

**Size:** 4861 lines (very large)

**Key Models:**
- `Workspace` - id, name, description, created_at, updated_at
- `Paper` - id, title, authors, abstract, url, doi, source, etc.
- `User` - User information
- `UserSessionState` - Session state (page_path, workspace_id, last_query, extra)
- `StructuredGap` - Research gaps
- `ResearchIntelligenceArtifact` - Intelligence analysis artifacts
- `SavedResearchQuestion` - Saved research questions
- `ResearchPlan` - Research plans
- `ResearcherDecision` - User decisions on AI suggestions

**Key Methods:**
- Workspace CRUD
- Paper management
- Search history
- Session state management
- Intelligence artifact management
- Research question management
- Research plan management

**Issues:**
- `Workspace` model has `description` but not `research_question` or `research_context`
- Session state exists but not used for research context persistence
- Very large file, could be split

**Opportunity:** 
- Add `research_question` field to Workspace model
- Use session state for research context persistence
- Or use `description` field for research context (simpler)

---

## 5. Research Workflow Mapping

### Current Flow (Fragmented)

```
Home
  ↓
Research (optional)
  ↓ classify → clarify → research direction
  ↓ save context to sessionStorage
  ↓
Search
  ↓ load context from sessionStorage
  ↓ enhance query with research context
  ↓ search papers
  ↓ add papers to workspace (context lost)
  ↓
Workspaces
  ↓ select workspace
  ↓
Research Intelligence (standalone)
  ↓ run analysis
  ↓ generate questions
  ↓ create plan
```

### Issues with Current Flow

1. **Context Loss:** Research context saved to sessionStorage is lost when papers are added to workspace
2. **Fragmented Entry Points:** User must navigate between Research, Search, Workspaces, Intelligence separately
3. **No Workspace Research Context:** Workspace doesn't store the research question/context
4. **Disconnected Intelligence:** Research Intelligence is a standalone page, not integrated with Research → Search
5. **Redundant Destinations:** Too many separate pages (Research, Search, Research Agent, Intelligence, Workspaces, Library)

### Ideal Flow (Coherent)

```
Home
  ↓ "What are you researching?"
  ↓
Research
  ↓ classify → clarify → research direction
  ↓ save context to workspace
  ↓
Search (with research context)
  ↓ enhance query with research context
  ↓ search papers
  ↓ add papers to workspace (context preserved)
  ↓
Workspace (with research question displayed)
  ↓ "Research Question: [question]"
  ↓ "Focus: [focus]"
  ↓ "Intent: [intent]"
  ↓
Research Intelligence (integrated)
  ↓ analyze evidence from selected papers
  ↓ detect gaps
  ↓ rank opportunities
  ↓ generate questions
  ↓ create plan
```

---

## 6. Duplicated Functionality

### 6.1 Research Question Generation

**Locations:**
- `Research.tsx` - Hardcoded scores (novelty: 75, feasibility: 70, impact: 80)
- `ResearchQuestionGenerator.tsx` - Displays AI-generated questions with scores
- `research_question_service.py` - AI-powered question generation

**Issue:** Inconsistent scoring methods (hardcoded vs AI-generated)

**Recommendation:** Use AI-generated scores consistently, remove hardcoded values

### 6.2 Search Entry Points

**Locations:**
- Home → Search Papers
- Research → Start Research → Search
- Library → Papers → Search
- Direct navigation to /search

**Issue:** Multiple ways to access search, no context preservation

**Recommendation:** Unify search entry points, preserve research context

### 6.3 Workspace Access

**Locations:**
- Workspaces page
- Home → Recent Workspaces
- Search → Add to Workspace → Select Workspace
- Research Intelligence → Select Workspace

**Issue:** Workspace selection scattered across UI

**Recommendation:** Centralize workspace selection, preserve active workspace context

### 6.4 Intelligence Features

**Locations:**
- Research Intelligence page (unified)
- Research Agent (deep research)
- Individual components (Compare, Explain, etc.)

**Issue:** Intelligence features scattered, not integrated with research flow

**Recommendation:** Integrate intelligence into Research → Search → Workspace flow

---

## 7. Existing APIs Available for Reuse

### 7.1 Research Context APIs

**Available:**
- `/research/classify` - Query classification ✅
- `/research-intelligence/questions/generate` - Question generation ✅
- `/research-intelligence/plan-suggestions` - Plan generation ✅

**Missing:**
- No API to save research context to workspace
- No API to load research context from workspace

**Recommendation:** Add workspace research context endpoints (or reuse description field)

### 7.2 Evidence APIs

**Available:**
- `/research-intelligence/evidence` - Evidence analysis ✅
- `/research-intelligence/gaps` - Gap detection ✅
- `/research-intelligence/opportunities` - Opportunity ranking ✅

**Status:** ✅ Comprehensive, ready to use

### 7.3 Workspace APIs

**Available:**
- `/workspaces/` - List/create workspaces ✅
- `/workspaces/{workspace_id}` - Workspace details ✅
- `/workspaces/{workspace_id}/papers` - Paper management ✅
- `/workspaces/session-state` - Session state ✅

**Status:** ✅ Adequate, may need research context field

### 7.4 Search APIs

**Available:**
- `/papers/search-global` - Multi-source search ✅
- `/papers/{paper_id}` - Paper details ✅
- `/papers/{paper_id}/explain` - Paper explanation ✅
- `/papers/compare` - Paper comparison ✅

**Status:** ✅ Comprehensive, ready to use

---

## 8. Recommendations for PHASE 8.5

### 8.1 Priority 1: Preserve Research Context in Workspace

**Options:**
1. Add `research_question` field to Workspace model (requires migration)
2. Add `research_context` JSON field to Workspace model (requires migration)
3. Reuse `description` field for research context (no migration, simpler)

**Recommendation:** Option 3 (reuse description field) for simplicity

**Implementation:**
- When user starts research from Research.tsx, save research context to workspace description
- Display research context in Workspace page
- Load research context when opening workspace

### 8.2 Priority 2: Integrate Research Intelligence into Workflow

**Current:** Standalone Research Intelligence page

**Proposed:** Add intelligence actions to Workspace page

**Implementation:**
- Add "Analyze Evidence" button to Workspace page (when papers exist)
- Add "Detect Gaps" button to Workspace page (when papers exist)
- Add "Generate Questions" button to Workspace page (when gaps exist)
- Add "Create Plan" button to Workspace page (when questions exist)
- Keep Research Intelligence page for advanced users

### 8.3 Priority 3: Simplify User-Facing Destinations

**Current:** Research, Search, Research Agent, Intelligence, Workspaces, Library

**Proposed:** Research, Workspaces (with integrated intelligence)

**Implementation:**
- Keep Research as entry point
- Keep Search as research-aware search (accessed from Research)
- Integrate intelligence into Workspaces
- Keep Library as asset hub
- Consider deprecating standalone Research Agent (or integrate into Research)
- Keep Home as dashboard but add "What am I researching?" section

### 8.4 Priority 4: Improve Search Results for Research Use

**Current:** Generic paper presentation

**Proposed:** Research-focused metadata display

**Implementation:**
- Prioritize scholarly metadata (authors, year, venue, DOI, citations)
- Add open-access indicator
- Add relevance score
- Add methodology indicators where available
- Keep existing filters (year, source)

### 8.5 Priority 5: Fix Research Question Scoring

**Current:** Hardcoded scores in Research.tsx

**Proposed:** Use AI-generated scores consistently

**Implementation:**
- Remove hardcoded scores from Research.tsx
- Use `/research-intelligence/questions/generate` for score calculation
- Display scores as estimates or omit if unreliable

### 8.6 Priority 6: Improve Empty States

**Current:** Generic empty states

**Proposed:** Action-oriented empty states

**Implementation:**
- No workspace → "Create workspace to start research"
- No papers → "Search papers or upload papers"
- No research question → "Start research to define your question"
- No evidence → "Add papers to analyze evidence"
- No gaps → "Analyze evidence to detect gaps"
- No questions → "Detect gaps to generate questions"
- No plan → "Generate questions to create plan"

### 8.7 Priority 7: Simplify Home Page

**Current:** Generic dashboard with recommendations

**Proposed:** Research-focused dashboard

**Implementation:**
- Add "What am I researching?" section (display active workspace research question)
- Keep recent workspaces
- Keep quick actions (Search, Deep Research, Upload)
- Remove or simplify generic recommendations

---

## 9. Security Considerations

### 9.1 Existing Security

**Workspace Ownership:** ✅ Enforced via `get_current_user` in workspaces router
**Paper Ownership:** ✅ Papers are workspace-scoped
**Research Question Ownership:** ✅ Questions are workspace-scoped
**Research Plan Ownership:** ✅ Plans are workspace-scoped
**IDOR Protection:** ✅ Workspace ID checks in place

### 9.5 Security Requirements for PHASE 8.5

**Research Context in Workspace:**
- Ensure only workspace owner can modify research context
- Validate research context on save/load

**Intelligence Integration:**
- Ensure intelligence operations are workspace-scoped
- No cross-workspace data leakage

**Status:** ✅ Existing security mechanisms are adequate, no changes needed

---

## 10. Performance Considerations

### 10.1 Current Performance

**Search:** ✅ Cached, timeout-controlled, concurrent
**Intelligence:** ⚠️ AI-powered, may be slow for large workspaces
**Workspace Loading:** ⚠️ May be slow for workspaces with many papers

### 10.2 Performance Requirements for PHASE 8.5

**Research Context Persistence:** ✅ Minimal overhead (text field)
**Intelligence Integration:** ⚠️ May need lazy loading or async execution
**Search Results:** ✅ No performance impact (UI changes only)

**Recommendation:** No performance optimizations needed unless measurements show issues

---

## 11. Testing Requirements

### 11.1 Existing Tests

**Backend:** 345/345 tests passing (baseline)

### 11.2 New Tests Required

**Research Context in Workspace:**
- Test saving research context to workspace
- Test loading research context from workspace
- Test research context display in Workspace page

**Intelligence Integration:**
- Test intelligence buttons in Workspace page
- Test intelligence execution from Workspace page
- Test intelligence results display in Workspace page

**Empty States:**
- Test empty state messages
- Test empty state actions

**Home Page:**
- Test "What am I researching?" display
- Test active workspace research question display

---

## 12. Technical Debt

### 12.1 Existing Technical Debt

1. **Large Files:**
   - `research_agent.py` (5930 lines)
   - `papers.py` (6507 lines)
   - `research.py` (4861 lines)

2. **Hardcoded Scores:**
   - Research.tsx has hardcoded research question scores

3. **Context Loss:**
   - Research context not preserved in workspace

4. **Fragmentation:**
   - Multiple entry points for same functionality

### 12.2 Technical Debt to Address in PHASE 8.5

1. **Remove Hardcoded Scores:** Use AI-generated scores consistently
2. **Preserve Research Context:** Add research context to workspace
3. **Integrate Intelligence:** Add intelligence actions to Workspace page

### 12.3 Technical Debt to Defer

1. **Split Large Files:** Out of scope for PHASE 8.5
2. **Refactor Research Agent:** Out of scope for PHASE 8.5

---

## 13. Implementation Plan Summary

### Phase 8.5.1: Search → Evidence Handoff
- Preserve research context when adding papers to workspace
- Reuse workspace description field for research context

### Phase 8.5.2: Research Context in Workspace
- Display research question/context in Workspace page
- Add "Refine Research Question" action
- Add "Return to Research" action

### Phase 8.5.3: Evidence-Focused Search Results
- Improve search result metadata display
- Add open-access indicator
- Add relevance score

### Phase 8.5.4: Research Filters
- Reuse existing filters (year, source)
- No new filters needed

### Phase 8.5.5: Search Result Actions
- Reuse existing actions (Open, Add to Workspace, Save, Compare, Explain)
- Add "Use as Evidence" action

### Phase 8.5.6: Evidence Collection
- Reuse existing workspace paper storage
- Add evidence metadata to paper (optional, if needed)

### Phase 8.5.7: Research Intelligence Handoff
- Add intelligence buttons to Workspace page
- Integrate existing intelligence services

### Phase 8.5.8: Research Question Quality
- Remove hardcoded scores from Research.tsx
- Use AI-generated scores consistently

### Phase 8.5.9: Research Plan Handoff
- Reuse existing ResearchPlanService
- Integrate plan creation into Workspace page

### Phase 8.5.10: Remove User-Facing Redundancy
- Integrate intelligence into Workspace page
- Keep Research, Search, Workspaces, Library
- Consider deprecating standalone Research Agent

### Phase 8.5.11: Home Page Simplification
- Add "What am I researching?" section
- Display active workspace research question

### Phase 8.5.12: Empty States
- Add action-oriented empty states throughout

### Phase 8.5.13: Error States
- Reuse existing error handling
- Ensure no infinite loops

### Phase 8.5.14: Performance Audit
- Measure before optimizing
- No optimizations expected needed

### Phase 8.5.15: Security Audit
- Verify workspace ownership
- Verify IDOR protection
- No security changes expected needed

### Phase 8.5.16: Testing
- Add tests for new functionality
- Run existing tests (345/345 baseline)

### Phase 8.5.17: Final User Flow Test
- Test complete workflow end-to-end
- Verify coherence

### Phase 8.5.18: Cleanup
- Remove unused imports
- Remove dead code
- Update documentation

---

## 14. Conclusion

**Status:** ✅ Ready for PHASE 8.5 implementation

**Key Insight:** The codebase has comprehensive research intelligence capabilities, but they are fragmented and disconnected. PHASE 8.5 should focus on **cohering existing functionality** rather than adding new features.

**Primary Goal:** Make the research workflow feel coherent rather than like separate pages.

**Secondary Goal:** Simplify the user experience by reducing redundant entry points.

**Approach:** Reuse existing APIs and services, integrate them into a coherent workflow, preserve research context across the flow.

**Expected Outcome:** A unified research workflow from question to plan, with context preserved at each step.

---

**Next Step:** Begin PHASE 8.5.1 implementation (Search → Evidence Handoff)
