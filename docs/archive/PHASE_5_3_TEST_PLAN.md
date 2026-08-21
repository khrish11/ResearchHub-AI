# PHASE 5.3 TEST PLAN

**Phase:** Comprehensive Testing & Validation
**Date:** 2025-01-XX
**Status:** In Progress

---

## Executive Summary

This test plan outlines the comprehensive testing strategy for PHASE 5.3, validating all Research Intelligence functionality including Research Intelligence Artifacts, Research Questions, Research Plans, and the complete research workflow from discovery to report generation.

---

## 1. Test Scope

### 1.1 Components Under Test

#### Backend Services (30 files)
- `ai_service.py` - AI task execution
- `evidence_intelligence_service.py` - Evidence analysis
- `gap_intelligence_service.py` - Gap detection
- `opportunity_scoring_service.py` - Opportunity ranking
- `research_question_service.py` - Question generation
- `research_challenger_service.py` - Hypothesis challenge
- `citation_verification_service.py` - Citation verification
- `knowledge_graph_enhancement_service.py` - Knowledge graph enhancement
- `research_intelligence_artifact_service.py` - Artifact management
- `research_plan_service.py` - Plan generation and export
- `citation_service.py` - Citation processing
- `paper_check_service.py` - Paper processing
- `rag_index_service.py` - RAG indexing
- `retrieval_service.py` - RAG retrieval
- `embedding_service.py` - Embedding generation
- `cache_service.py` - Caching layer
- `analytics_service.py` - Analytics tracking

#### Backend Routers (17 files)
- `research_agent.py` - Research Intelligence API (primary focus)
- `workspaces.py` - Workspace management
- `papers.py` - Paper management
- `auth.py` - Authentication/authorization
- `ai.py` - AI endpoints
- `rag.py` - RAG endpoints

#### Repository Implementations
- `repositories/research.py` - ResearchRepository protocol
  - FirebaseResearchRepository
  - InMemoryResearchRepository

#### Data Models
- `ResearchIntelligenceArtifact` - Intelligence artifact persistence
- `SavedResearchQuestion` - Research question persistence
- `ResearchPlan` - Research plan persistence
- `ResearcherDecision` - Decision tracking
- `StructuredGap` - Gap structure
- `ResearchOpportunity` - Opportunity structure
- `ResearchReport` - Report persistence

#### Frontend Components (14 files)
- `ResearchIntelligencePage.tsx` - Main intelligence page
- `ResearchQuestionGenerator.tsx` - Question generation UI
- `OpportunityRanking.tsx` - Opportunity ranking UI
- `ResearchPlanBuilder.tsx` - Plan builder UI
- `EvidenceLandscape.tsx` - Evidence visualization
- `GapIntelligence.tsx` - Gap visualization
- `IntelligencePipeline.tsx` - Pipeline status
- `IntelligenceScorecard.tsx` - Scorecard display
- `HypothesisChallenger.tsx` - Hypothesis challenge UI
- `CitationIntegrity.tsx` - Citation verification UI
- `EvidenceTrace.tsx` - Evidence trace modal
- `ResearchIntelligenceHeader.tsx` - Header component

#### Frontend API Client
- `api/researchIntelligence.ts` - Research Intelligence API client

---

## 2. API Endpoints

### 2.1 Research Intelligence Pipeline

**Evidence Analysis**
- `POST /research/evidence-analysis` - Analyze evidence for a claim

**Gap Detection**
- `POST /research/gap-detection` - Detect research gaps

**Opportunity Ranking**
- `POST /research/opportunity-ranking` - Rank research opportunities

**Question Generation**
- `POST /research/question-generation` - Generate research questions

**Hypothesis Challenge**
- `POST /research/hypothesis-challenge` - Challenge a hypothesis

**Citation Verification**
- `POST /research/citation-verification` - Verify citations

**Knowledge Graph Enhancement**
- `POST /research/knowledge-graph-enhancement` - Enhance knowledge graph

### 2.2 Intelligence Artifacts

**Artifact CRUD**
- `POST /research/intelligence` - Create intelligence artifact
- `GET /research/intelligence/{id}` - Get artifact by ID
- `GET /workspaces/{id}/research-intelligence` - List workspace artifacts
- `DELETE /research/intelligence/{id}` - Delete artifact

### 2.3 Research Questions

**Question CRUD**
- `POST /research/questions` - Save research question
- `GET /research/questions/{question_id}` - Get question by ID
- `GET /research/workspaces/{workspace_id}/questions` - List workspace questions
- `DELETE /research/questions/{question_id}` - Delete question

### 2.4 Research Plans

**Plan CRUD**
- `POST /research/plans/generate` - Generate AI suggestions for plan
- `POST /research/plans` - Create research plan
- `GET /research/plans/{plan_id}` - Get plan by ID
- `GET /research/workspaces/{workspace_id}/plans` - List workspace plans
- `PUT /research/plans/{plan_id}` - Update plan
- `DELETE /research/plans/{plan_id}` - Delete plan
- `POST /research/plans/{plan_id}/export` - Export plan to DocSpace

### 2.5 Report Generation

**Report Endpoints**
- `POST /research/generate-report` - Generate research report
- `POST /research/generate-report-with-intelligence` - Generate with intelligence

---

## 3. Authorization Boundaries

### 3.1 Workspace Ownership
All Research Intelligence resources are scoped to workspaces:
- `workspace_id` field on all persistent entities
- Workspace ownership verification on all operations
- Cross-workspace access prevention

### 3.2 User Ownership
- `user_id` field on all persistent entities
- User-level isolation within workspaces
- List operations filter by both workspace_id and user_id

### 3.3 Artifact Ownership
- Intelligence artifacts are workspace-scoped
- Plans reference artifacts via `artifact_id`
- Questions reference artifacts via `source_artifact_id`
- Artifact ownership verified before dependent operations

### 3.4 Authorization Tests Required
- User A cannot read User B's artifact
- User A cannot delete User B's artifact
- User A cannot read User B's saved question
- User A cannot delete User B's saved question
- User A cannot read User B's research plan
- User A cannot update User B's research plan
- User A cannot delete User B's research plan
- User A cannot export User B's research plan
- User A cannot generate a plan using User B's artifact
- User A cannot generate a report using User B's artifact
- Valid workspace + invalid artifact
- Valid artifact + wrong workspace
- Valid plan + wrong workspace
- Valid question + wrong workspace
- Nonexistent IDs
- Malformed IDs
- Cross-user IDs
- Cross-workspace IDs

---

## 4. Persistence Paths

### 4.1 Firestore Collections
- `research_intelligence_artifacts` - Intelligence artifacts
- `saved_research_questions` - Saved research questions
- `research_plans` - Research plans
- `research_reports` - Research reports
- `workspace_documents` - DocSpace documents

### 4.2 InMemory Storage
- `_research_intelligence_artifacts` - In-memory artifacts
- `_saved_research_questions` - In-memory questions
- `_research_plans` - In-memory plans
- `_research_reports` - In-memory reports

### 4.3 Serialization/Deserialization
- Firestore document → Dataclass conversion
- Dataclass → Firestore document conversion
- Timestamp handling (UTC, ISO formatting)
- Integer/string ID conversion
- Nested structure handling (researcher_decisions)

---

## 5. Frontend Workflows

### 5.1 Research Intelligence Workflow
1. User navigates to Research Intelligence page
2. Selects workspace and papers
3. Runs intelligence analysis (pipeline stages)
4. Views evidence landscape
5. Views gap intelligence
6. Views opportunity ranking
7. Generates research questions
8. Saves questions to workspace
9. Develops research plan from opportunity
10. Accepts/modifies/rejects AI suggestions
11. Saves research plan
12. Exports plan to DocSpace
13. Generates research report
14. Views final output

### 5.2 Component Interactions
- ResearchIntelligencePage → IntelligencePipeline
- ResearchIntelligencePage → EvidenceLandscape
- ResearchIntelligencePage → GapIntelligence
- ResearchIntelligencePage → OpportunityRanking
- ResearchIntelligencePage → ResearchQuestionGenerator
- ResearchIntelligencePage → ResearchPlanBuilder
- OpportunityRanking → ResearchPlanBuilder (via callback)
- ResearchPlanBuilder → API (save plan)

---

## 6. Regression Risks

### 6.1 High Risk
- **ID Type Mismatches** - Integer/string ID conversion between frontend/backend
- **Authorization Bypass** - Missing workspace ownership checks
- **Data Loss** - Incorrect serialization/deserialization
- **Cross-Workspace Leakage** - Incorrect filtering in list operations

### 6.2 Medium Risk
- **Timestamp Issues** - UTC/local time mismatches
- **Nested Structure Loss** - Researcher decisions not persisted correctly
- **Artifact Linkage** - Broken references between artifacts, questions, plans
- **Frontend State** - Stale state after operations

### 6.3 Low Risk
- **UI Inconsistencies** - Minor UI bugs
- **Loading States** - Missing loading indicators
- **Error Messages** - Unclear error messages

---

## 7. Expected Test Counts

### 7.1 Backend Tests

**Research Intelligence Services** (Estimated: 50 tests)
- Evidence Intelligence: 8 tests
- Gap Intelligence: 8 tests
- Opportunity Scoring: 8 tests
- Research Question Service: 8 tests
- Research Challenger Service: 8 tests
- Citation Verification: 6 tests
- Knowledge Graph Enhancement: 4 tests

**Intelligence Artifacts** (Estimated: 20 tests)
- Create: 4 tests
- Read: 4 tests
- List: 4 tests
- Delete: 4 tests
- Serialization: 4 tests

**Research Questions** (Estimated: 20 tests)
- Create: 4 tests
- Read: 4 tests
- List: 4 tests
- Delete: 4 tests
- Workspace isolation: 4 tests

**Research Plans** (Estimated: 30 tests)
- Generate suggestions: 6 tests
- Create: 4 tests
- Read: 4 tests
- List: 4 tests
- Update: 4 tests
- Delete: 4 tests
- Export: 4 tests

**Research Reports** (Estimated: 15 tests)
- Standard generation: 5 tests
- Intelligence-backed: 5 tests
- Artifact linkage: 5 tests

**Authorization/IDOR** (Estimated: 20 tests)
- Cross-user access: 10 tests
- Cross-workspace access: 10 tests

**Repository/Persistence** (Estimated: 20 tests)
- Firebase operations: 10 tests
- InMemory operations: 10 tests

**Total Backend Tests: ~175 tests**

### 7.2 Frontend Tests

**Component Tests** (Estimated: 30 tests)
- ResearchIntelligencePage: 8 tests
- ResearchQuestionGenerator: 6 tests
- OpportunityRanking: 6 tests
- ResearchPlanBuilder: 6 tests
- Other components: 4 tests

**API Client Tests** (Estimated: 20 tests)
- All API functions: 20 tests

**Total Frontend Tests: ~50 tests**

### 7.3 E2E Tests

**Workflow Tests** (Estimated: 10 tests)
- Complete research workflow: 5 tests
- Error scenarios: 5 tests

**Total E2E Tests: ~10 tests**

### 7.4 Grand Total

**Expected Total Tests: ~235 tests**

---

## 8. Test Execution Order

### 8.1 Phase 5.3.1: Backend Full Test Suite
- Run complete backend test suite
- Record total, passed, failed, skipped, errors, warnings
- Fix any failures
- Re-run until 100% passing

### 8.2 Phase 5.3.2: Authorization/IDOR Testing
- Run adversarial authorization tests
- Verify no unauthorized data leakage
- Verify correct HTTP status codes

### 8.3 Phase 5.3.3: API Contract Validation
- Compare backend Pydantic models with frontend TypeScript interfaces
- Verify field names, types, optionality, nested structures
- Fix any mismatches

### 8.4 Phase 5.3.4: Repository/Persistence Testing
- Test FirebaseResearchRepository
- Test InMemoryResearchRepository
- Verify serialization/deserialization

### 8.5 Phase 5.3.5: Research Workflow E2E Test
- Test complete research workflow
- Verify ID and provenance consistency

### 8.6 Phase 5.3.6: Frontend Validation
- Run TypeScript compilation
- Run production build
- Run ESLint
- Run existing frontend tests

### 8.7 Phase 5.3.7: AI Failure/Graceful Degradation
- Simulate AI service failures
- Verify graceful degradation

### 8.8 Phase 5.3.8: Performance Check
- Inspect for N+1 queries
- Measure endpoint latency
- Check for unnecessary API calls

### 8.9 Phase 5.3.9: Security Hardening
- Review authentication/authorization
- Review input validation
- Review error leakage

### 8.10 Phase 5.3.10: Final Regression
- Run complete backend suite
- Run complete frontend lint
- Run complete frontend build
- Run focused tests

### 8.11 Phase 5.3.11: Documentation
- Create test report
- Create security test report
- Create completion report

---

## 9. Success Criteria

- 100% backend tests passing
- 100% frontend lint passing
- 100% frontend build passing
- No authorization bypasses
- No API contract mismatches
- No data loss in persistence
- Complete E2E workflow passing
- Graceful degradation on AI failure
- No critical security vulnerabilities

---

## 10. Known Issues

None documented at this time.

---

## 11. Dependencies

- Firebase Admin SDK
- Firestore client
- AI service (Groq/OpenAI)
- Pytest
- TypeScript
- React
- Vite

---

## 12. Notes

- Tests should run against both Firebase and InMemory repositories where possible
- Authorization tests should use multiple test users
- E2E tests should use realistic data
- Performance tests should use varying dataset sizes
