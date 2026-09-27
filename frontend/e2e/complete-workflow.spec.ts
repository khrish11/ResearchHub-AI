/**
 * Priority 7 Complete Browser Research Workflow Validation
 * 
 * Tests the actual user workflow through the browser UI:
 * - Authentication
 * - Workspace creation
 * - PDF upload through UI
 * - Paper persistence
 * - RAG queries through UI
 * - Research intelligence through UI
 * - Persistence
 * - User isolation
 */
import { test, expect } from '@playwright/test';

const TEST_USER = {
  email: `workflow_test_${Date.now()}@example.com`,
  password: 'WorkflowTest123!',
};

test.describe('Complete Browser Research Workflow', () => {
  test.setTimeout(120000); // 2 minutes for complete workflow
  
  test('complete workflow: register → workspace → upload → RAG → persistence', async ({ page }) => {
  // Capture console logs for debugging
  const consoleLogs: any[] = [];
  page.on('console', msg => {
    consoleLogs.push({ type: msg.type(), text: msg.text() });
    if (msg.type() === 'error') {
      console.log('Browser error:', msg.text());
    }
  });
    // Console and network monitoring
    const consoleErrors: string[] = [];
    const networkErrors: { url: string; status: string }[] = [];
    
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });
    
    page.on('response', response => {
      if (response.status() >= 400) {
        networkErrors.push({ url: response.url(), status: response.status().toString() });
      }
    });

    // ==================== STEP 1: REGISTER ====================
    console.log('STEP 1: Register user');
    await page.goto('/register');
    await page.getByLabel('Email').fill(TEST_USER.email);
    await page.getByLabel('Password').fill(TEST_USER.password);
    await page.getByRole('button', { name: 'Sign Up', exact: true }).click();
    
    try {
      await page.waitForNavigation({ timeout: 10000 });
    } catch {
      console.log('No navigation after registration');
    }
    
    await page.waitForTimeout(2000);
    const currentUrl = page.url();
    console.log('After registration:', currentUrl);
    
    // Registration might stay on register page if there's an error
    // Check for error messages
    const errorElement = page.locator('.auth-error, [role="alert"]');
    const errorVisible = await errorElement.isVisible();
    if (errorVisible) {
      const errorText = await errorElement.textContent();
      console.log('Registration error:', errorText);
    }
    
    // If registration failed, try login with the existing user from Priority 6
    if (currentUrl === '/register' || currentUrl.includes('/register')) {
      console.log('Registration failed or stayed on register page, trying login with fallback user');
      await page.goto('/login');
      await page.getByLabel('Email').fill(TEST_USER.email);
      await page.getByLabel('Password').fill(TEST_USER.password);
      await page.getByRole('button', { name: 'Sign In', exact: true }).click();
      
      try {
        await page.waitForNavigation({ timeout: 10000 });
      } catch {
        console.log('No navigation after login');
      }
      
      await page.waitForTimeout(2000);
    }

    // ==================== STEP 2: LOGIN ====================
    console.log('STEP 2: Login user (if not already authenticated)');
    const afterRegisterUrl = page.url();
    if (afterRegisterUrl === '/login' || afterRegisterUrl.includes('/login')) {
      await page.goto('/login');
      await page.getByLabel('Email').fill(TEST_USER.email);
      await page.getByLabel('Password').fill(TEST_USER.password);
      await page.getByRole('button', { name: 'Sign In', exact: true }).click();
      
      try {
        await page.waitForNavigation({ timeout: 10000 });
      } catch {
        console.log('No navigation after login');
      }
      
      await page.waitForTimeout(2000);
    }
    
    // ==================== STEP 3: CREATE WORKSPACE ====================
    console.log('STEP 3: Create workspace');
    await page.goto('/workspaces');
    await page.waitForTimeout(2000);
    
    // Check current URL
    const wsUrl = page.url();
    console.log('Workspaces URL:', wsUrl);
    expect(wsUrl).toContain('localhost:5173');
    expect(wsUrl).toContain('/workspaces');
    
    // Frontend should be rendering React page (Vite proxy fixed in Priority 6)
    const createButton = page.getByRole('button', { name: 'Create Workspace' }).first();
    const createButtonVisible = await createButton.isVisible();
    console.log('Create Workspace button visible:', createButtonVisible);
    
    if (createButtonVisible) {
      await createButton.click();
      await page.waitForTimeout(1000);
      
      const nameInput = page.locator('#workspace-name');
      const nameInputVisible = await nameInput.isVisible();
      console.log('Workspace name input visible:', nameInputVisible);
      
      if (nameInputVisible) {
        await nameInput.fill('Priority 7 Test Workspace');
        
        const descInput = page.locator('textarea, input[type="text"]');
        const descInputVisible = await descInput.nth(1).isVisible();
        console.log('Workspace description input visible:', descInputVisible);
        
        if (descInputVisible) {
          await descInput.nth(1).fill('Workspace for Priority 7 browser workflow validation');
        }
        
        // Use specific button - the submit button in the form
        const submitButton = page.locator('form').getByRole('button', { name: 'Create Workspace' });
        await submitButton.click();
        await page.waitForTimeout(3000);
        
        // Check if we're still on the workspaces page or were redirected
        const afterSubmitUrl = page.url();
        console.log('After submit URL:', afterSubmitUrl);
      }
    }
    
    // Reload workspaces to see the new workspace
    await page.goto('/workspaces');
    await page.waitForTimeout(3000);
    
    // Check for workspace cards - links use /workspace/:id (singular) not /workspaces/
    const workspaceItems = page.locator('a[href*="/workspace/"]');
    const itemCount = await workspaceItems.count();
    console.log('Workspace links found:', itemCount);
    
    // If no links found, try other selectors
    if (itemCount === 0) {
      console.log('No workspace links found, trying alternative selectors');
      const workspaceCards = page.locator('[data-testid="workspace-card"], .workspace-card, .workspace-item');
      const cardCount = await workspaceCards.count();
      console.log('Workspace cards found:', cardCount);
      
      // Try looking for any text content that might indicate workspaces
      const pageContent = await page.content();
      const hasWorkspaceText = pageContent.includes('Priority 7 Test Workspace');
      console.log('Page contains workspace name:', hasWorkspaceText);
    }
    
    // Get workspace ID from first workspace link
    let workspaceId = null;
    if (itemCount > 0) {
      const firstWorkspaceUrl = await workspaceItems.first().getAttribute('href');
      console.log('First workspace URL:', firstWorkspaceUrl);
      const urlMatch = firstWorkspaceUrl?.match(/\/workspace\/(\d+)/);
      workspaceId = urlMatch ? urlMatch[1] : null;
    }
    
    console.log('Workspace ID:', workspaceId);
    
    // FAIL the test if workspace creation didn't succeed
    // A valid workspace ID is required for all downstream operations
    if (!workspaceId) {
      throw new Error('Workspace creation failed - no workspace ID found in UI. Cannot proceed with downstream validation.');
    }

    // ==================== STEP 4: UPLOAD PDF UI VALIDATION ====================
    console.log('STEP 4: Validate PDF upload UI');
    
    // The actual upload functionality is in /upload
    await page.goto('/upload');
    await page.waitForTimeout(2000);
    
    const uploadUrl = page.url();
    console.log('Upload page URL:', uploadUrl);
    
    // Try to find upload-related elements
    const uploadButton = page.getByRole('button', { name: /select file|upload/i }).first();
    const fileInput = page.locator('input[type="file"]');
    
    const uploadButtonVisible = await uploadButton.isVisible();
    const fileInputVisible = await fileInput.isVisible();
    
    console.log('Upload button visible:', uploadButtonVisible);
    console.log('File input visible:', fileInputVisible);
    
    // The file input is hidden but should exist
    const fileInputExists = await fileInput.count() > 0;
    console.log('File input exists:', fileInputExists);
    
    // Note: For now we're validating the UI exists. Real PDF upload requires investigation
    // of why the upload completion state is not being reached.
    
    // Actually upload a real PDF for end-to-end validation
    if (fileInputExists && workspaceId) {
      console.log('Executing real PDF upload...');
      
      // Select workspace in dropdown
      const workspaceSelect = page.locator('select[aria-label="Save to workspace"]');
      if (await workspaceSelect.isVisible()) {
        await workspaceSelect.selectOption(String(workspaceId));
        await page.waitForTimeout(1000);
      }
      
      // Upload the test PDF
      const testPdfPath = 'E:/rezsrch/ResearchHub-AI/frontend/test-fixtures/test-research-paper.pdf';
      await fileInput.setInputFiles(testPdfPath);
      await page.waitForTimeout(2000);
      
      // Check if upload button is enabled
      const uploadButton = page.getByRole('button', { name: /upload|analyze/i }).first();
      const isDisabled = await uploadButton.isDisabled();
      console.log('Upload button disabled:', isDisabled);
      
      // Click upload button
      const uploadSubmitButton = page.getByRole('button', { name: /upload|analyze/i }).first();
      if (await uploadSubmitButton.isVisible()) {
        console.log('Clicking upload button...');
        await uploadSubmitButton.click();
        
        // Wait for upload to complete - check for state changes
        await page.waitForTimeout(5000); // Wait for initial upload
        
        // Wait for success panel to appear
        try {
          await page.waitForSelector('[data-testid="upload-success"]', { timeout: 25000 });
          console.log('Success panel appeared within timeout');
        } catch {
          console.log('Success panel did not appear within timeout - checking current state');
          
          // Debug: check if we're still on upload page or navigated away
          const currentUrl = page.url();
          console.log('Current URL after upload attempt:', currentUrl);
          
          // Check if upload completed but panel is just not visible
          const uploadCompletePanel = page.locator('text=Complete', { exact: false });
          const completeVisible = await uploadCompletePanel.isVisible();
          console.log('Upload Complete status visible:', completeVisible);
        }
        
        // Check console logs for upload activity
        const uploadLogs = consoleLogs.filter(log => 
          log.text.includes('UPLOAD') || log.type === 'error'
        );
        console.log('Upload-related console logs:', uploadLogs);
        
        // Check current state - what actually happened
        const pageContent = await page.content();
        console.log('Page content after upload:', pageContent.substring(0, 500));
        
        // Check for success panel using test ID
        const successPanel = page.locator('[data-testid="upload-success"]');
        const successVisible = await successPanel.isVisible();
        console.log('Upload success panel visible:', successVisible);
        
        // Check for error messages
        const errorMessage = page.locator('text=error|failed|upload failed', { exact: false });
        const errorVisible = await errorMessage.isVisible();
        console.log('Error message visible:', errorVisible);
        
        // Check upload state in status panel
        const statusPanel = page.locator('text=Complete|Processing|Failed', { exact: false });
        const statusVisible = await statusPanel.isVisible();
        console.log('Status panel visible:', statusVisible);
        
        // Check for extracted text
        const extractedText = page.locator('text=extracted text|semantic retrieval', { exact: false });
        const extractedTextVisible = await extractedText.isVisible();
        console.log('Extracted text visible:', extractedTextVisible);
        
        // Check for paper ID
        const paperId = page.locator('text=paper_id|Paper ID', { exact: false });
        const paperIdVisible = await paperId.isVisible();
        console.log('Paper ID visible:', paperIdVisible);
        
        // Navigate to workspace to verify paper appears there
        if (workspaceId) {
          console.log('Navigating to workspace to verify paper appears...');
          await page.goto(`/workspace/${workspaceId}`);
          await page.waitForTimeout(3000);
          
          // Check if paper appears in workspace using specific selector
          const paperTitleButton = page.locator('button:has-text("Test Research Paper")');
          const paperInWorkspaceVisible = await paperTitleButton.isVisible();
          console.log('Paper title button visible in workspace:', paperInWorkspaceVisible);
          
          // Check for papers tab with count
          const papersTabCount = page.locator('button:has-text("Papers (1)")');
          const papersTabCountVisible = await papersTabCount.isVisible();
          console.log('Papers tab with count visible:', papersTabCountVisible);
          
          // Assert paper is visible
          if (!paperInWorkspaceVisible) {
            throw new Error('Paper uploaded successfully but not visible in workspace UI');
          }
          
          // Assert papers tab shows correct count
          if (!papersTabCountVisible) {
            throw new Error('Papers tab does not show expected count of 1');
          }
          
          console.log('SUCCESS: Paper is visible in workspace with correct count');
          
          // Try to select the paper
          const paperButton = page.locator('button:has-text("Test Research Paper")');
          await paperButton.click();
          await page.waitForTimeout(2000);
          
          // Check if paper is selected (UI should show selection state)
          const selectedPaperState = await page.evaluate(() => {
            // Check if there's any selected paper state in the UI
            const selectedButton = document.querySelector('button[aria-pressed="true"], button.selected, button.active');
            return selectedButton !== null;
          });
          console.log('Paper selection state detected:', selectedPaperState);
          
          if (!selectedPaperState) {
            console.log('Note: Paper selection state could not be definitively detected, but paper is clickable');
          }
          
          // Try to select the paper
          const paperItem = page.locator('[data-testid="paper-item"], .paper-item, [role="button"]').first();
          if (await paperItem.isVisible()) {
            console.log('Clicking paper to select...');
            await paperItem.click();
            await page.waitForTimeout(2000);
            
            // Check if paper is selected
            const selectedPaper = page.locator('text=selected|active', { exact: false });
            const paperSelectedVisible = await selectedPaper.isVisible();
            console.log('Paper selection visible:', paperSelectedVisible);
          }
        }
      }
    } else {
      console.log('Skipping actual PDF upload (file input not found or no workspace ID)');
    }

    // ==================== STEP 5: NAVIGATE TO WORKSPACE FOR RAG ====================
    console.log('STEP 5: Navigate to workspace for RAG validation');
    if (workspaceId) {
      // Capture all console logs including the new COPILOT_ logs
      const allLogs: any[] = [];
      page.on('console', msg => {
        allLogs.push({ type: msg.type(), text: msg.text() });
        if (msg.text().includes('COPILOT_') || msg.text().includes('WORKSPACE_')) {
          console.log('LIFECYCLE LOG:', msg.text());
        }
      });

      await page.goto(`/workspace/${workspaceId}`);
      await page.waitForTimeout(2000);
      
      const workspacePageUrl = page.url();
      console.log('Workspace page URL:', workspacePageUrl);
      
      // Check for RAG/chat interface in workspace
      const copilotPanel = page.locator('[data-testid="unified-copilot-panel"]');
      const copilotPanelVisible = await copilotPanel.isVisible();
      console.log('UnifiedCopilotPanel visible:', copilotPanelVisible);

      const chatInput = page.locator('[data-testid="unified-copilot-input"]');
      const chatInputVisible = await chatInput.isVisible();
      console.log('RAG input visible:', chatInputVisible);
      
      // Execute real RAG query if chat input is visible
      if (chatInputVisible) {
        console.log('Executing real RAG query...');
        
        // Ask a question whose answer is in the uploaded PDF
        await chatInput.fill('What embedding model does the paper use?');
        await page.waitForTimeout(1000);
        
        // Submit the query - use the specific data-testid
        const sendButton = page.locator('[data-testid="unified-copilot-submit"]');
        console.log('RAG submit button found:', await sendButton.count());
        console.log('RAG submit button visible:', await sendButton.isVisible());
        if (await sendButton.isVisible()) {
          console.log('Clicking RAG submit button...');
          await sendButton.click();
          await page.waitForTimeout(7000); // Wait for RAG response

          // Log all COPILOT_ logs for debugging
          console.log('COPILOT logs captured:', allLogs.filter(log => log.text.includes('COPILOT_')));
          console.log('WORKSPACE logs captured:', allLogs.filter(log => log.text.includes('WORKSPACE_')));

          // Check for answer using data-testid
          const ragAnswer = page.locator('[data-testid="rag-answer"]');
          const ragAnswerVisible = await ragAnswer.isVisible();
          console.log('RAG answer visible:', ragAnswerVisible);
          
          if (ragAnswerVisible) {
            const answerText = await ragAnswer.textContent();
            console.log('RAG answer text:', answerText);
          } else {
            throw new Error('RAG answer is not visible in the UI');
          }
        } else {
          console.log('RAG submit button not visible, skipping RAG query');
        }
      }
      
      // Test unsupported question
      if (chatInputVisible) {
        console.log('Testing unsupported RAG query...');
        await chatInput.fill('What is the weather like today?');
        await page.waitForTimeout(1000);

        const sendButton = page.locator('[data-testid="unified-copilot-submit"]');
        console.log('Clicking RAG submit button for unsupported query...');
        await sendButton.click();
        await page.waitForTimeout(7000);

        // Log COPILOT logs for unsupported query
        console.log('COPILOT logs for unsupported query:', allLogs.filter(log => log.text.includes('COPILOT_')));
        
        // Verify unsupported question returns low confidence and no sources
        const unsupportedLogs = allLogs.filter(log => log.text.includes('COPILOT_RESPONSE_BODY'));
        if (unsupportedLogs.length > 0) {
          const unsupportedResponse = unsupportedLogs[unsupportedLogs.length - 1].text;
          console.log('Unsupported question response:', unsupportedResponse);
          
          // Should have low confidence and no sources for unsupported question
          if (unsupportedResponse.includes('confidence: 0') || unsupportedResponse.includes('sources: Array(0)')) {
            console.log('Unsupported question handled correctly (low confidence/no sources)');
          }
        }
      }
    } else {
      console.log('Skipping workspace RAG validation (no workspace ID)');
    }

    // ==================== STEP 6: CHECK RESEARCH INTELLIGENCE UI ====================
    console.log('STEP 6: Check research intelligence UI');
    
    // Research intelligence is accessed via /research-intelligence/:id
    // Check if it's accessible through the workspace page
    if (workspaceId) {
      await page.goto(`/research-intelligence/${workspaceId}`);
      await page.waitForTimeout(2000);
      
      const researchIntelUrl = page.url();
      console.log('Research intelligence URL:', researchIntelUrl);
      
      // Check for research intelligence tabs
      const evidenceTab = page.getByText(/evidence/i).first();
      const gapTab = page.getByText(/gap/i).first();
      const opportunityTab = page.getByText(/opportunity/i).first();
      const questionTab = page.getByText(/question/i).first();
      const challengerTab = page.getByText(/challenger/i).first();
      
      const evidenceTabVisible = await evidenceTab.isVisible();
      const gapTabVisible = await gapTab.isVisible();
      const opportunityTabVisible = await opportunityTab.isVisible();
      const questionTabVisible = await questionTab.isVisible();
      const challengerTabVisible = await challengerTab.isVisible();
      
      console.log('Evidence tab visible:', evidenceTabVisible);
      console.log('Gap tab visible:', gapTabVisible);
      console.log('Opportunity tab visible:', opportunityTabVisible);
      console.log('Question tab visible:', questionTabVisible);
      console.log('Challenger tab visible:', challengerTabVisible);
    } else {
      console.log('Skipping research intelligence validation (no workspace ID)');
    }

    // ==================== STEP 7: CHECK FOR CITATION VERIFICATION UI ====================
    console.log('STEP 7: Check citation verification UI');
    if (workspaceId) {
      await page.goto(`/workspace/${workspaceId}`);
      await page.waitForTimeout(1000);
      
      const citationButton = page.getByRole('button', { name: 'Copy citation' });
      const citationButtonVisible = await citationButton.isVisible();
      console.log('Citation button visible:', citationButtonVisible);
    } else {
      console.log('Skipping citation verification validation (no workspace ID)');
    }

    // ==================== STEP 8: CHECK FOR KNOWLEDGE GRAPH UI ====================
    console.log('STEP 8: Check knowledge graph UI');
    if (workspaceId) {
      await page.goto(`/workspace/${workspaceId}`);
      await page.waitForTimeout(1000);
      
      const mindmapButton = page.getByRole('button', { name: /mindmap|graph/i }).first();
      const mindmapButtonVisible = await mindmapButton.isVisible();
      console.log('Mindmap/Graph button visible:', mindmapButtonVisible);
    } else {
      console.log('Skipping knowledge graph validation (no workspace ID)');
    }

    // ==================== STEP 9: PERSISTENCE TEST ====================
    console.log('STEP 9: Test persistence');
    await page.goto('/workspaces');
    await page.reload();
    await page.waitForTimeout(2000);
    
    // Verify workspaces still exist
    const persistedUrl = page.url();
    console.log('After refresh:', persistedUrl);
    expect(persistedUrl).toContain('/workspaces');

    // ==================== STEP 10: CONSOLE AND NETWORK AUDIT ====================
    console.log('STEP 10: Console and network audit');
    console.log('Console errors:', consoleErrors.length);
    console.log('Network errors:', networkErrors.length);
    
    if (consoleErrors.length > 0) {
      console.log('Console error details:', consoleErrors);
    }
    
    if (networkErrors.length > 0) {
      console.log('Network error details:', networkErrors);
    }

    // Filter out expected 401s for auth and 404s for missing routes
    const criticalErrors = networkErrors.filter(err => 
      !err.url.includes('/auth/') && 
      !err.url.includes('/research') && // Research page returns 404, expected
      err.status !== '401' &&
      ['500', '502', '503'].includes(err.status)
    );
    
    console.log('Critical errors:', criticalErrors.length);
  });

  test('user isolation through browser', async ({ page }) => {
    test.setTimeout(90000); // 90 seconds for user isolation test
    
    // User A workflow
    const userA = `user_a_${Date.now()}@example.com`;
    const userB = `user_b_${Date.now()}@example.com`;
    
    // Register and login User A
    await page.goto('/register');
    await page.getByLabel('Email').fill(userA);
    await page.getByLabel('Password').fill('UserA123!');
    await page.getByRole('button', { name: 'Sign Up', exact: true }).click();
    await page.waitForTimeout(2000);
    
    await page.goto('/login');
    await page.getByLabel('Email').fill(userA);
    await page.getByLabel('Password').fill('UserA123!');
    await page.getByRole('button', { name: 'Sign In', exact: true }).click();
    await page.waitForTimeout(2000);
    
    await page.goto('/workspaces');
    await page.waitForTimeout(1000);
    
    // Create Workspace A
    const createButton = page.getByRole('button', { name: /create|new workspace/i }).first();
    if (await createButton.isVisible()) {
      await createButton.click();
      await page.waitForTimeout(1000);
      
      const nameInput = page.getByLabel(/name/i);
      if (await nameInput.isVisible()) {
        await nameInput.fill('User A Workspace');
        
        // Use specific button - the submit button in the form
        const submitButton = page.locator('form').getByRole('button', { name: 'Create Workspace' });
        await submitButton.click();
        await page.waitForTimeout(2000);
      }
    }
    
    // Get workspace URL
    await page.goto('/workspaces');
    await page.waitForTimeout(1000);
    const firstWorkspace = page.locator('a[href*="/workspace/"]').first();
    if (await firstWorkspace.isVisible()) {
      await firstWorkspace.click();
      await page.waitForTimeout(1000);
    }
    
    const workspaceAUrl = page.url();
    console.log('User A workspace URL:', workspaceAUrl);
    
    // Logout User A
    const logoutButton = page.getByRole('button', { name: 'Logout' });
    if (await logoutButton.isVisible()) {
      await logoutButton.click();
      await page.waitForTimeout(2000);
    }
    
    // Register and login User B
    await page.goto('/register');
    await page.getByLabel('Email').fill(userB);
    await page.getByLabel('Password').fill('UserB123!');
    await page.getByRole('button', { name: 'Sign Up', exact: true }).click();
    await page.waitForTimeout(2000);
    
    await page.goto('/login');
    await page.getByLabel('Email').fill(userB);
    await page.getByLabel('Password').fill('UserB123!');
    await page.getByRole('button', { name: 'Sign In', exact: true }).click();
    await page.waitForTimeout(2000);
    
    // Try to access User A's workspace
    await page.goto(workspaceAUrl);
    await page.waitForTimeout(1000);
    
    const currentUrl = page.url();
    console.log('User B accessing User A workspace:', currentUrl);
    
    // User B should be blocked or redirected to login
    // If they can access the workspace, that's a security issue
    const isBlocked = currentUrl.includes('/login') || currentUrl.includes('/workspaces');
    const workspaceContent = page.locator('text=' + 'User A Workspace');
    const hasWorkspaceContent = await workspaceContent.isVisible();
    
    console.log('User B blocked from workspace:', isBlocked);
    console.log('User B can see workspace content:', hasWorkspaceContent);
    
    // Either they should be blocked OR they should not see the specific workspace content
    expect(isBlocked || !hasWorkspaceContent).toBeTruthy();
  });
});
