# PHASE 7.6 PRODUCTION SMOKE TESTS

**Date:** 2026-08-21  
**Phase:** PHASE 7 - Production Launch & Real-World Validation  
**Objective:** Create practical smoke-test checklist for production validation

---

## Executive Summary

Production smoke test checklist covering authentication, research workflows, security scenarios, and AI failure handling. These tests should be executed after deployment to production to validate critical functionality.

**Overall Assessment:** SMOKE TESTS READY FOR EXECUTION

---

## 1. AUTH Smoke Tests

### 1.1 Register/Login

**Test Case 1.1.1: User Registration**
- [ ] Navigate to `/register`
- [ ] Enter valid email address
- [ ] Enter strong password (8+ characters, mixed case, number, special)
- [ ] Submit registration form
- [ ] Verify email verification required message displayed
- [ ] Check email inbox for verification link
- [ ] Click verification link
- [ ] Verify email verified message displayed
- [ ] Navigate to `/login`
- [ ] Enter email and password
- [ ] Submit login form
- [ ] Verify redirect to `/home`
- [ ] Verify authenticated state (user menu visible)

**Expected Result:** User can register, verify email, and login successfully

**Test Case 1.1.2: Google OAuth Registration/Login**
- [ ] Navigate to `/login`
- [ ] Click "Sign in with Google" button
- [ ] Complete Google OAuth flow
- [ ] Verify redirect to `/home`
- [ ] Verify authenticated state (user menu visible)
- [ ] Verify user account created in Firebase

**Expected Result:** User can register/login via Google OAuth successfully

**Test Case 1.1.3: Login with Invalid Credentials**
- [ ] Navigate to `/login`
- [ ] Enter valid email
- [ ] Enter invalid password
- [ ] Submit login form
- [ ] Verify error message displayed
- [ ] Verify not redirected to `/home`

**Expected Result:** Login fails with appropriate error message

### 1.2 Workspace Creation

**Test Case 1.2.1: Create Workspace**
- [ ] Navigate to `/home`
- [ ] Click "Create Workspace" button
- [ ] Enter workspace name
- [ ] Enter workspace description (optional)
- [ ] Submit workspace creation form
- [ ] Verify workspace created
- [ ] Verify redirect to workspace page
- [ ] Verify workspace appears in workspace list

**Expected Result:** Workspace created successfully and accessible

**Test Case 1.2.2: Create Workspace with Invalid Data**
- [ ] Navigate to `/home`
- [ ] Click "Create Workspace" button
- [ ] Leave workspace name empty
- [ ] Submit workspace creation form
- [ ] Verify validation error displayed
- [ ] Verify workspace not created

**Expected Result:** Workspace creation fails with validation error

### 1.3 Logout/Session Handling

**Test Case 1.3.1: User Logout**
- [ ] Navigate to authenticated page (e.g., `/home`)
- [ ] Click user menu
- [ ] Click "Logout" button
- [ ] Verify redirect to landing page
- [ ] Verify authenticated state cleared
- [ ] Attempt to navigate to `/home`
- [ ] Verify redirect to `/login`

**Expected Result:** User logged out successfully, session cleared

**Test Case 1.3.2: Session Expiry**
- [ ] Login to application
- [ ] Wait 15 minutes (access token expiry)
- [ ] Navigate to authenticated page
- [ ] Verify automatic token refresh attempt
- [ ] If refresh fails, verify redirect to `/login`

**Expected Result:** Session expires gracefully, user redirected to login

**Test Case 1.3.3: Multiple Tab Session**
- [ ] Login to application in Tab A
- [ ] Open application in Tab B
- [ ] Verify authenticated state in Tab B
- [ ] Logout in Tab A
- [ ] Refresh Tab B
- [ ] Verify redirect to `/login` in Tab B

**Expected Result:** Session invalidation across tabs

---

## 2. RESEARCH Smoke Tests

### 2.1 Search Papers

**Test Case 2.1.1: Search Papers by Title**
- [ ] Navigate to `/search`
- [ ] Enter search query (e.g., "machine learning")
- [ ] Submit search form
- [ ] Verify search results displayed
- [ ] Verify results contain search terms
- [ ] Verify pagination if many results

**Expected Result:** Search returns relevant papers

**Test Case 2.1.2: Search Papers by Author**
- [ ] Navigate to `/search`
- [ ] Enter author name in search
- [ ] Submit search form
- [ ] Verify search results displayed
- [ ] Verify results contain author

**Expected Result:** Search returns papers by author

**Test Case 2.1.3: Search with No Results**
- [ ] Navigate to `/search`
- [ ] Enter unlikely search query (e.g., "xyz123abc")
- [ ] Submit search form
- [ ] Verify "no results" message displayed

**Expected Result:** Empty state displayed appropriately

### 2.2 Open Paper

**Test Case 2.2.1: Open Paper Details**
- [ ] Navigate to `/search`
- [ ] Search for papers
- [ ] Click on a paper result
- [ ] Verify paper details page displayed
- [ ] Verify title, authors, abstract displayed
- [ ] Verify DOI link (if available)

**Expected Result:** Paper details displayed correctly

**Test Case 2.2.2: Open Paper with Invalid ID**
- [ ] Navigate to `/papers/999999`
- [ ] Verify 404 error or "paper not found" message

**Expected Result:** Appropriate error message displayed

### 2.3 Add Paper to Workspace

**Test Case 2.3.1: Add Paper to Workspace**
- [ ] Navigate to `/search`
- [ ] Search for papers
- [ ] Click on a paper result
- [ ] Click "Add to Workspace" button
- [ ] Select workspace from dropdown
- [ ] Confirm addition
- [ ] Verify success message displayed
- [ ] Navigate to selected workspace
- [ ] Verify paper appears in workspace

**Expected Result:** Paper added to workspace successfully

**Test Case 2.3.2: Add Duplicate Paper to Workspace**
- [ ] Navigate to paper details
- [ ] Click "Add to Workspace" button
- [ ] Select workspace where paper already exists
- [ ] Confirm addition
- [ ] Verify duplicate warning or idempotent success

**Expected Result:** Appropriate handling of duplicate addition

### 2.4 Generate Intelligence

**Test Case 2.4.1: Generate Research Intelligence**
- [ ] Navigate to workspace with papers
- [ ] Click "Research Intelligence" button
- [ ] Navigate to `/research-intelligence/:id`
- [ ] Enter research topic
- [ ] Select papers for analysis
- [ ] Click "Generate Intelligence" button
- [ ] Verify loading state displayed
- [ ] Wait for analysis completion (may take 1-2 minutes)
- [ ] Verify intelligence results displayed:
  - [ ] Evidence analysis
  - [ ] Gap detection
  - [ ] Opportunity ranking
  - [ ] Research questions
  - [ ] Hypothesis challenge
  - [ ] Citation verification

**Expected Result:** Intelligence analysis completes and displays results

**Test Case 2.4.2: Generate Intelligence with No Papers**
- [ ] Navigate to workspace with no papers
- [ ] Click "Research Intelligence" button
- [ ] Verify "add papers first" message or similar

**Expected Result:** Appropriate error message for empty workspace

### 2.5 Save Artifact

**Test Case 2.5.1: Save Intelligence Artifact**
- [ ] Navigate to `/research-intelligence/:id`
- [ ] Generate intelligence analysis
- [ ] Click "Save Artifact" button
- [ ] Enter artifact name
- [ ] Confirm save
- [ ] Verify success message displayed
- [ ] Click "Artifact History" button
- [ ] Verify artifact appears in history

**Expected Result:** Artifact saved successfully

**Test Case 2.5.2: Load Saved Artifact**
- [ ] Navigate to `/research-intelligence/:id`
- [ ] Click "Artifact History" button
- [ ] Select saved artifact
- [ ] Click "Load" button
- [ ] Verify intelligence results restored
- [ ] Verify all components display saved data

**Expected Result:** Artifact loaded successfully

### 2.6 Reload Artifact

**Test Case 2.6.1: Reload Artifact After Page Refresh**
- [ ] Navigate to `/research-intelligence/:id`
- [ ] Generate and save artifact
- [ ] Refresh browser page
- [ ] Verify intelligence results still displayed
- [ ] Verify no data loss

**Expected Result:** Artifact persists across page refresh

### 2.7 Generate Research Questions

**Test Case 2.7.1: Generate Research Questions**
- [ ] Navigate to `/research-intelligence/:id`
- [ ] Generate intelligence analysis
- [ ] Navigate to "Research Questions" component
- [ ] Click "Generate Questions" button
- [ ] Verify questions generated
- [ ] Verify questions relevant to research topic

**Expected Result:** Research questions generated successfully

### 2.8 Save Question

**Test Case 2.8.1: Save Research Question**
- [ ] Navigate to `/research-intelligence/:id`
- [ ] Generate research questions
- [ ] Click "Save" button on a question
- [ ] Verify success message displayed
- [ ] Verify question marked as saved

**Expected Result:** Question saved successfully

**Test Case 2.8.2: Delete Saved Question**
- [ ] Navigate to saved questions list
- [ ] Click "Delete" button on a question
- [ ] Confirm deletion
- [ ] Verify question removed from list

**Expected Result:** Question deleted successfully

### 2.9 Rank Opportunities

**Test Case 2.9.1: View Opportunity Ranking**
- [ ] Navigate to `/research-intelligence/:id`
- [ ] Generate intelligence analysis
- [ ] Navigate to "Opportunity Ranking" component
- [ ] Verify opportunities displayed
- [ ] Verify opportunities ranked by score
- [ ] Verify opportunity details visible

**Expected Result:** Opportunity ranking displayed correctly

### 2.10 Develop Research Plan

**Test Case 2.10.1: Generate Research Plan**
- [ ] Navigate to `/research-intelligence/:id`
- [ ] Generate intelligence analysis
- [ ] Navigate to "Opportunity Ranking" component
- [ ] Click "Develop Plan" button on an opportunity
- [ ] Wait for AI suggestions (may take 30-60 seconds)
- [ ] Verify ResearchPlanBuilder modal opens
- [ ] Verify plan fields populated with suggestions

**Expected Result:** Research plan suggestions generated successfully

**Test Case 2.10.2: Save Research Plan**
- [ ] In ResearchPlanBuilder modal
- [ ] Review AI suggestions
- [ ] Accept/Modify/Reject fields as needed
- [ ] Click "Save Plan" button
- [ ] Verify success message displayed
- [ ] Verify plan saved to Firestore

**Expected Result:** Research plan saved successfully

### 2.11 Generate Research Report

**Test Case 2.11.1: Generate Standard Report**
- [ ] Navigate to workspace
- [ ] Click "Generate Report" button
- [ ] Enter report topic
- [ ] Select report depth (quick/balanced/deep)
- [ ] Select report focus (broad/methods/applications/risks)
- [ ] Select papers for report
- [ ] Click "Generate Report" button
- [ ] Verify loading state displayed
- [ ] Wait for report generation (may take 1-2 minutes)
- [ ] Verify report displayed
- [ ] Verify report contains citations
- [ ] Verify report has proper structure

**Expected Result:** Standard report generated successfully

**Test Case 2.11.2: Generate Intelligence-Backed Report**
- [ ] Navigate to `/research-intelligence/:id`
- [ ] Generate and save artifact
- [ ] Click "Generate Report" button
- [ ] Select saved artifact
- [ ] Click "Generate Report" button
- [ ] Verify loading state displayed
- [ ] Wait for report generation
- [ ] Verify report displayed
- [ ] Verify report incorporates intelligence results

**Expected Result:** Intelligence-backed report generated successfully

---

## 3. SECURITY Smoke Tests

### 3.1 Unauthorized Workspace Access

**Test Case 3.1.1: Access Own Workspace**
- [ ] Login as User A
- [ ] Create workspace
- [ ] Navigate to workspace page
- [ ] Verify workspace accessible

**Expected Result:** User can access own workspace

**Test Case 3.1.2: Access Other User's Workspace**
- [ ] Login as User A
- [ ] Note workspace ID
- [ ] Logout
- [ ] Login as User B
- [ ] Navigate to User A's workspace URL
- [ ] Verify 404 error or "not found" message
- [ ] Verify workspace data not accessible

**Expected Result:** Cross-user workspace access prevented

### 3.2 Unauthorized Artifact Access

**Test Case 3.2.1: Access Own Artifact**
- [ ] Login as User A
- [ ] Generate and save artifact
- [ ] Navigate to artifact history
- [ ] Click on artifact
- [ ] Verify artifact accessible

**Expected Result:** User can access own artifact

**Test Case 3.2.2: Access Other User's Artifact**
- [ ] Login as User A
- [ ] Generate and save artifact
- [ ] Note artifact ID
- [ ] Logout
- [ ] Login as User B
- [ ] Attempt to load User A's artifact ID
- [ ] Verify 404 error or "not found" message
- [ ] Verify artifact data not accessible

**Expected Result:** Cross-user artifact access prevented

### 3.3 Unauthorized Report Access

**Test Case 3.3.1: Access Own Report**
- [ ] Login as User A
- [ ] Generate report
- [ ] Note report ID
- [ ] Navigate to report
- [ ] Verify report accessible

**Expected Result:** User can access own report

**Test Case 3.3.2: Access Other User's Report**
- [ ] Login as User A
- [ ] Generate report
- [ ] Note report ID
- [ ] Logout
- [ ] Login as User B
- [ ] Attempt to load User A's report ID
- [ ] Verify 404 error or "not found" message
- [ ] Verify report data not accessible

**Expected Result:** Cross-user report access prevented

### 3.4 Invalid IDs

**Test Case 3.4.1: Access Workspace with Invalid ID**
- [ ] Login as user
- [ ] Navigate to `/workspace/999999`
- [ ] Verify 404 error or "not found" message

**Expected Result:** Appropriate error for invalid ID

**Test Case 3.4.2: Access Artifact with Invalid ID**
- [ ] Login as user
- [ ] Attempt to load artifact with invalid ID
- [ ] Verify 404 error or "not found" message

**Expected Result:** Appropriate error for invalid ID

**Test Case 3.4.3: Access Report with Invalid ID**
- [ ] Login as user
- [ ] Attempt to load report with invalid ID
- [ ] Verify 404 error or "not found" message

**Expected Result:** Appropriate error for invalid ID

### 3.5 Expired/Invalid Authentication

**Test Case 3.5.1: Access Protected Page with Expired Token**
- [ ] Login as user
- [ ] Manually expire access token (wait 15 minutes)
- [ ] Navigate to protected page
- [ ] Verify automatic token refresh attempt
- [ ] If refresh fails, verify redirect to `/login`

**Expected Result:** Expired token handled gracefully

**Test Case 3.5.2: Access Protected Page with Invalid Token**
- [ ] Manually set invalid token in browser storage
- [ ] Navigate to protected page
- [ ] Verify redirect to `/login`
- [ ] Verify error message displayed

**Expected Result:** Invalid token handled gracefully

**Test Case 3.5.3: Access Protected Page with No Token**
- [ ] Logout
- [ ] Navigate to protected page (e.g., `/home`)
- [ ] Verify redirect to `/login`

**Expected Result:** Unauthenticated access prevented

---

## 4. AI FAILURE Smoke Tests

### 4.1 AI Timeout

**Test Case 4.1.1: AI Request Timeout**
- [ ] Navigate to `/research-intelligence/:id`
- [ ] Generate intelligence analysis
- [ ] Monitor for timeout (configured to 120 seconds)
- [ ] If timeout occurs, verify error message displayed
- [ ] Verify graceful degradation
- [ ] Verify no application crash

**Expected Result:** AI timeout handled gracefully with error message

### 4.2 AI Unavailable

**Test Case 4.2.1: AI Service Unavailable**
- [ ] Simulate AI service unavailability (disable Groq API key temporarily)
- [ ] Navigate to `/research-intelligence/:id`
- [ ] Attempt to generate intelligence
- [ ] Verify "AI service unavailable" error message
- [ ] Verify application remains functional
- [ ] Verify user can retry

**Expected Result:** AI unavailability handled gracefully

**Test Case 4.2.2: AI Rate Limit Exceeded**
- [ ] Make multiple rapid AI requests
- [ ] If rate limit exceeded, verify error message displayed
- [ ] Verify user can retry after waiting
- [ ] Verify no application crash

**Expected Result:** AI rate limit handled gracefully

### 4.3 Malformed AI Response

**Test Case 4.3.1: Invalid JSON Response**
- [ ] Simulate malformed AI response (if test environment allows)
- [ ] Navigate to `/research-intelligence/:id`
- [ ] Attempt to generate intelligence
- [ ] Verify error message displayed
- [ ] Verify graceful degradation
- [ ] Verify no application crash

**Expected Result:** Malformed AI response handled gracefully

**Test Case 4.3.2: Missing Required Fields**
- [ ] Simulate AI response missing required fields
- [ ] Navigate to `/research-intelligence/:id`
- [ ] Attempt to generate intelligence
- [ ] Verify error message displayed
- [ ] Verify graceful degradation

**Expected Result:** Missing fields handled gracefully

### 4.4 Graceful Fallback/Error State

**Test Case 4.4.1: Report Generation Fallback**
- [ ] Navigate to workspace
- [ ] Attempt to generate intelligence-backed report with invalid artifact
- [ ] Verify fallback to standard report
- [ ] Verify standard report generated successfully

**Expected Result:** Graceful fallback to standard report

**Test Case 4.4.2: Component-Level Error State**
- [ ] Navigate to `/research-intelligence/:id`
- [ ] Trigger AI error in one component (e.g., gap detection)
- [ ] Verify error message displayed in that component
- [ ] Verify other components remain functional
- [ ] Verify user can retry failed component

**Expected Result:** Component-level errors don't break entire page

**Test Case 4.4.3: Retry Mechanism**
- [ ] Trigger AI error
- [ ] Verify "Retry" button available
- [ ] Click "Retry" button
- [ ] Verify retry attempt initiated
- [ ] Verify success on retry (if AI service recovered)

**Expected Result:** Retry mechanism functional

---

## 5. Smoke Test Execution Summary

### Test Coverage

**AUTH Tests:** 9 test cases
- Registration/Login: 3
- Workspace Creation: 2
- Logout/Session Handling: 4

**RESEARCH Tests:** 11 test cases
- Search Papers: 3
- Open Paper: 2
- Add Paper to Workspace: 2
- Generate Intelligence: 2
- Save/Reload Artifact: 2
- Research Questions: 2
- Opportunity Ranking: 1
- Research Plan: 2
- Research Report: 2

**SECURITY Tests:** 8 test cases
- Unauthorized Workspace Access: 2
- Unauthorized Artifact Access: 2
- Unauthorized Report Access: 2
- Invalid IDs: 3
- Expired/Invalid Authentication: 3

**AI FAILURE Tests:** 7 test cases
- AI Timeout: 1
- AI Unavailable: 2
- Malformed AI Response: 2
- Graceful Fallback: 3

**Total:** 35 test cases

### Execution Priority

**Critical (Must Pass):**
- All AUTH tests (9)
- All SECURITY tests (8)
- AI FAILURE tests (7)

**High Priority:**
- RESEARCH tests (11)

### Expected Pass Rate

**Minimum Acceptable:** 90% (32/35 tests passing)

**Target:** 100% (35/35 tests passing)

---

## 6. Smoke Test Execution Checklist

### Pre-Execution
- [ ] Production environment deployed
- [ ] Environment variables configured
- [ ] Firebase project configured
- [ ] Firestore indexes deployed
- [ ] Test accounts created (at least 2 users)
- [ ] Test workspaces created
- [ ] AI service (Groq) accessible

### Execution
- [ ] Execute all AUTH tests
- [ ] Execute all RESEARCH tests
- [ ] Execute all SECURITY tests
- [ ] Execute all AI FAILURE tests
- [ ] Document any failures
- [ ] Document any unexpected behavior

### Post-Execution
- [ ] Review test results
- [ ] Classify failures (BLOCKER/HIGH/MEDIUM/LOW)
- [ ] Create remediation plan for failures
- [ ] Retest after fixes
- [ ] Sign off on smoke test completion

---

**Smoke Test Checklist Date:** 2026-08-21  
**Status:** READY FOR EXECUTION
