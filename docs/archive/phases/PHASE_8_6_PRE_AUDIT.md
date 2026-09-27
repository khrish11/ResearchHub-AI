# PHASE 8.6 Pre-Implementation Audit

**Date:** 2026-08-25
**Phase:** Workspace Research Intelligence Integration

---

## Executive Summary

Audit completed to identify reusable APIs and components for integrating Research Intelligence into Workspace without duplication.

**Key Finding:** Comprehensive Research Intelligence infrastructure already exists. The standalone ResearchIntelligencePage provides a full-featured experience. The goal is to add a minimal progressive workflow section to Workspace that guides users to the next logical action, reusing existing APIs and navigating to the full page when needed.

---

## Reusable APIs (from researchIntelligence.ts)

### Core Intelligence APIs
1. **Evidence Analysis**
   - Function: `analyzeEvidence(request: EvidenceAnalysisRequest)`
   - Endpoint: `POST /research/evidence-analysis`
   - Request: `{ workspace_id, claim, topic?, paper_ids? }`

2. **Gap Detection**
   - Function: `detectGaps(request: GapDetectionRequest)`
   - Endpoint: `POST /research/gap-detection`
   - Request: `{ workspace_id, topic?, paper_ids? }`

3. **Opportunity Ranking**
   - Function: `rankOpportunities(request: OpportunityRankingRequest)`
   - Endpoint: `POST /research/opportunity-ranking`
   - Request: `{ workspace_id, topic?, paper_ids? }`

4. **Research Question Generation**
   - Function: `generateQuestions(request: QuestionGenerationRequest)`
   - Endpoint: `POST /research/question-generation`
   - Request: `{ workspace_id, topic?, paper_ids?, max_questions? }`

5. **Plan Suggestions**
   - Function: `generatePlanSuggestions(request: GeneratePlanSuggestionsRequest)`
   - Endpoint: `POST /research/plans/generate`
   - Request: `{ artifact_id, opportunity_id, gap_description, category, evidence_strength, novelty, impact, feasibility, recency, overall_score, explanation, supporting_papers, affected_papers }`

6. **Create Research Plan**
   - Function: `createResearchPlan(request: CreateResearchPlanRequest)`
   - Endpoint: `POST /research/plans`
   - Request: `{ workspace_id, artifact_id, opportunity_id, ...plan fields }`

7. **List Research Plans**
   - Function: `listResearchPlans(workspaceId: number)`
   - Endpoint: `GET /research/workspaces/{workspace_id}/plans`

### Additional APIs (for future use)
- `challengeHypothesis` - Hypothesis challenge
- `verifyCitations` - Citation verification
- `enhanceKnowledgeGraph` - Knowledge graph enhancement
- `listWorkspaceResearchIntelligenceArtifacts` - Artifact history

---

## Reusable Components

### ResearchQuestionGenerator
- **File:** `frontend/src/features/research-intelligence/ResearchQuestionGenerator.tsx`
- **Props:** `questions`, `onAddToWorkspace`, `onChallengeQuestion`, `onSaveQuestion`, `savedQuestions`, `onDeleteSavedQuestion`
- **Purpose:** Displays generated research questions with categories and scores
- **Complexity:** Medium - has its own UI for question cards

### ResearchPlanBuilder
- **File:** `frontend/src/features/research-intelligence/ResearchPlanBuilder.tsx`
- **Props:** `suggestions`, `onSavePlan`, `onCancel`, `isLoading`
- **Purpose:** Builds research plans from AI suggestions with accept/modify/reject decisions
- **Complexity:** High - has many form fields and decision logic

### Other Components (not needed for minimal integration)
- EvidenceLandscape, GapIntelligence, OpportunityRanking, HypothesisChallenger, CitationIntegrity, EvidenceTrace, IntelligencePipeline, IntelligenceScorecard, ResearchIntelligenceHeader

---

## Current WorkspacePage Structure

### Existing Features
- Workspace data with papers
- Research context display (from PHASE 8.5)
- Tabs: papers, chat, review, ops
- "Research Intelligence" button that navigates to standalone page
- Copilot panel
- Paper list with filtering
- Paper detail view

### Integration Point
The "Workspace flow" section (lines 875-891) currently shows static guidance. This is the ideal location to add the progressive Research Intelligence workflow.

---

## Recommended Integration Approach

### Principle: Minimal Integration, Progressive Disclosure

**Do NOT:**
- Embed the full ResearchIntelligencePage into Workspace (too complex)
- Recreate all intelligence components (duplication)
- Show 10+ buttons simultaneously (confusing)

**DO:**
- Add a simple "Research Intelligence" section to Workspace
- Show only the next logical action based on current state
- Reuse existing API functions
- Navigate to standalone page for complex UI (questions, plans)
- Keep the workflow progressive and clear

### Progressive Workflow

```
No papers:
  "Add papers to begin research intelligence"
  → Button: "Search Papers"

Has papers, no analysis:
  "Analyze your papers to find evidence and research gaps"
  → Button: "Analyze Evidence"

Evidence available:
  "Find gaps in the current literature"
  → Button: "Detect Gaps"

Gaps available:
  "Turn gaps into research opportunities"
  → Button: "Find Opportunities"

Opportunities available:
  "Generate research questions from opportunities"
  → Button: "Generate Questions"

Questions available:
  "Turn your strongest direction into a research plan"
  → Button: "Create Research Plan" (navigates to standalone page)
```

### Implementation Strategy

**Simple State Tracking:**
- Track which intelligence operations have been run
- Show only the next action
- Use loading states for API calls
- Use error handling with retry option

**API Usage:**
- Call `detectGaps`, `rankOpportunities`, `generateQuestions` directly
- For complex operations (plan creation), navigate to standalone page with context
- Pass workspace_id and paper_ids from current workspace

**UI Design:**
- Replace or augment the existing "Workspace flow" section
- Use emerald/indigo color scheme to match research context
- Keep it minimal - one action at a time
- Show loading states with spinner
- Show errors with retry button

---

## Backend Authorization

All research intelligence endpoints in `research_agent.py` use:
- `get_current_user` for authentication
- Workspace-scoped requests require `workspace_id`
- Repository validates workspace ownership

**Conclusion:** Existing authorization is adequate. No changes needed.

---

## Performance Considerations

- Do NOT run intelligence operations automatically on page load
- Only run when user explicitly clicks action button
- Lazy-load intelligence results
- No additional API calls on workspace load

---

## Known Limitations

1. **Complex UI Navigation:** For question generation and plan creation, users will be navigated to the standalone ResearchIntelligencePage. This is acceptable as those features have complex UI.

2. **State Persistence:** Intelligence results are not persisted in the current implementation (except via artifacts). This is acceptable for the minimal integration.

3. **Progressive State:** The simple state tracking (which operations have been run) is local to the component. This is acceptable for the minimal integration.

---

## Implementation Plan

1. Add state tracking for intelligence operations (evidence, gaps, opportunities, questions)
2. Add "Research Intelligence" section to WorkspacePage
3. Implement progressive action buttons
4. Add loading states
5. Add error handling
6. Test with existing backend APIs
7. Verify authorization
8. Run backend tests (345/345 must pass)
9. Frontend build and lint
10. Create completion report

---

## Files to Modify

- `frontend/src/features/workspace/WorkspacePage.tsx` - Add intelligence section
- No backend changes (reuse existing APIs)
- No new components (reuse existing APIs)

---

## Files to Keep Unchanged

- `frontend/src/features/research-intelligence/ResearchIntelligencePage.tsx` - Keep standalone page working
- `backend/routers/research_agent.py` - No changes needed
- All intelligence components - No changes needed

---

## Success Criteria

1. Workspace shows progressive research intelligence actions
2. Actions call existing APIs correctly
3. Loading states prevent duplicate requests
4. Errors are recoverable
5. Authorization remains enforced
6. Existing Workspace functionality intact
7. Standalone Research Intelligence page still works
8. 345/345 backend tests pass
9. Frontend builds successfully
10. Frontend lints successfully
