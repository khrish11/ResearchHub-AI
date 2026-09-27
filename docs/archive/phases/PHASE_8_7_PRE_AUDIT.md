# PHASE 8.7 Pre-Implementation Audit

**Date:** 2026-08-25
**Phase:** Research Intelligence Results + Workflow Persistence

---

## Executive Summary

Audit completed to determine the best strategy for:
1. Displaying lightweight result counts after intelligence operations
2. Persisting workflow state across page refreshes

**Key Finding:** API responses contain count data directly. Artifact data is unstructured, so sessionStorage is the simplest approach for state persistence.

---

## API Response Structures

### Gap Detection Response
```typescript
interface GapIntelligenceResponse {
  workspace: { id: number; name: string };
  topic: string;
  paper_count: number;
  gaps_by_category: Record<string, StructuredGap[]>;  // Can calculate total gaps
  scores: GapScores;
  summary: string;
  generated_at: string;
}
```
**Count extraction:** Sum of array lengths in `gaps_by_category`

### Opportunity Ranking Response
```typescript
interface OpportunityRankingResponse {
  workspace: { id: number; name: string };
  topic: string;
  paper_count: number;
  opportunities: ResearchOpportunity[];
  total_opportunities: number;  // Direct count available
  top_opportunity: TopOpportunity | null;
  comparison_matrix: OpportunityComparison[];
  summary: string;
  generated_at: string;
}
```
**Count extraction:** Use `total_opportunities` field directly

### Question Generation Response
```typescript
interface QuestionGenerationResponse {
  workspace: { id: number; name: string };
  topic: string;
  paper_count: number;
  questions: ResearchQuestion[];
  total_questions: number;  // Direct count available
  top_questions: ResearchQuestion[];
  summary: string;
  generated_at: string;
}
```
**Count extraction:** Use `total_questions` field directly

---

## Artifact APIs

### List Artifacts
```typescript
async function listWorkspaceResearchIntelligenceArtifacts(workspaceId: number): Promise<ListArtifactsResponse>
```

### Artifact Structure
```typescript
interface ResearchIntelligenceArtifact {
  id: string;
  workspace_id: number;
  user_id: number;
  topic: string;
  paper_ids: number[];
  paper_count: number;
  status: 'running' | 'completed' | 'partial' | 'failed';
  pipeline_version: string;
  created_at: string;
  updated_at: string;
  evidence_analysis?: Record<string, unknown>;      // Unstructured
  gap_analysis?: Record<string, unknown>;           // Unstructured
  opportunity_ranking?: Record<string, unknown>;    // Unstructured
  research_questions?: Record<string, unknown>;     // Unstructured
  hypothesis_challenges?: Record<string, unknown>;
  citation_verification?: Record<string, unknown>;
  knowledge_graph?: Record<string, unknown>;
  overall_score?: number;
  summary?: string;
  stage_errors?: Record<string, string>;
}
```

**Issue:** Intelligence results are stored as `Record<string, unknown>`, making it difficult to reliably extract counts without parsing unstructured data.

---

## State Persistence Strategy Decision

### Option 1: Derive from Artifacts
- **Pros:** Persistent across sessions, server-side
- **Cons:** Requires parsing unstructured `Record<string, unknown>` data, fragile, complex

### Option 2: Session Storage (Chosen)
- **Pros:** Simple, no backend changes, minimal data, easy to implement
- **Cons:** Lost on browser close, session-specific

**Decision:** Use sessionStorage for workflow state persistence.

**Rationale:**
- Artifact data is unstructured and not easily parsable for counts
- Session storage is adequate for this use case (workflow state is session-specific)
- Minimal data to store (completion flags, counts, timestamp)
- Simple to implement and maintain
- Can be enhanced later if needed

---

## Session Storage Schema

**Key:** `soyog.workspace.intelligence.v1`

**Structure:**
```typescript
interface WorkspaceIntelligenceState {
  workspaceId: number;
  gapsCompleted: boolean;
  opportunitiesCompleted: boolean;
  questionsCompleted: boolean;
  gapCount?: number;
  opportunityCount?: number;
  questionCount?: number;
  updatedAt: string;  // ISO timestamp
}
```

**Validation:**
- Verify `workspaceId` matches current workspace before loading
- Ignore state older than 24 hours
- Gracefully handle malformed JSON
- Clear state on workspace switch

---

## Implementation Plan

### 1. Result Count Extraction
- Extract gap count from `gaps_by_category` array lengths
- Use `total_opportunities` field directly
- Use `total_questions` field directly
- Store counts in component state

### 2. Result Preview UI
- Show completed steps with checkmarks
- Display count (e.g., "3 gaps found")
- Add "View results →" link to navigate to standalone page
- Keep UI minimal and progressive

### 3. State Persistence
- Save state to sessionStorage after each successful operation
- Load state on component mount
- Validate workspace ID before applying
- Expire stale state (>24 hours)

### 4. State Validation
- Check workspace ID match
- Check timestamp freshness
- Handle JSON parse errors
- Fallback to empty state on validation failure

### 5. View Results Navigation
- Navigate to `/research-intelligence/{workspaceId}` on "View results" click
- Reuse existing standalone page
- No new UI components needed

---

## Security Considerations

- Session storage is client-side only (no security risk)
- Workspace ID validation prevents cross-workspace state leakage
- No sensitive data stored (only completion flags and counts)
- Backend authorization remains unchanged

---

## Performance Considerations

- No additional API calls on page load (session storage read is synchronous)
- State saved only after successful operations (minimal overhead)
- No polling or background workers
- No automatic re-execution of AI operations

---

## Known Limitations

1. **Session-specific:** State lost on browser close. This is acceptable for workflow state.

2. **No artifact integration:** Not using backend artifacts for state. This is acceptable due to unstructured data.

3. **Manual refresh:** User must manually refresh to see persisted state. This is acceptable behavior.

4. **No result details:** Only showing counts, not full results. This is intentional to keep Workspace simple.

---

## Success Criteria

1. Result counts displayed after successful operations
2. Completed steps remain visible after page refresh
3. State does not leak between workspaces
4. Stale state is ignored
5. "View results" navigates to standalone page
6. Errors preserve previous successful state
7. Frontend builds successfully
8. Frontend lints successfully
9. Backend tests pass (345/345)
10. No security vulnerabilities introduced

---

## Files to Modify

- `frontend/src/features/workspace/WorkspacePage.tsx` - Add result counts, state persistence, UI updates

## Files to Keep Unchanged

- `frontend/src/api/researchIntelligence.ts` - No changes needed
- `backend/routers/research_agent.py` - No changes needed
- All intelligence components - No changes needed
