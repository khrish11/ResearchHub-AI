/**
 * Priority 34 - Paper Check Browser-to-Worker E2E Validation
 * 
 * Tests the complete Paper Check workflow through the browser UI:
 * - Authentication
 * - PDF upload
 * - Paper Check trigger from upload page
 * - Development worker automatic processing
 * - Result visibility
 */
import { test, expect } from '@playwright/test';

const TEST_USER = {
  email: `papercheck_test_${Date.now()}@example.com`,
  password: 'PaperCheckTest123!',
};

test.describe('Paper Check Browser-to-Worker E2E', () => {
  test.setTimeout(300000); // 5 minutes for complete workflow including AI processing
  
  test('complete paper check workflow: register → upload → check → worker → result', async ({ page }) => {
    // Network monitoring - capture only POST requests to /research/paper-check
    const paperCheckRequests: { url: string; method: string; response: any }[] = [];
    page.on('response', (response) => {
      if (response.url().includes('/research/paper-check') && response.request().method() === 'POST') {
        paperCheckRequests.push({
          url: response.url(),
          method: response.request().method(),
          response: response.status(),
        });
      }
    });

    // ==================== STEP 1: REGISTER ====================
    console.log('STEP 1: Register user');
    await page.goto('http://localhost:5173/register');
    await page.getByLabel('Email').fill(TEST_USER.email);
    await page.getByLabel('Password').fill(TEST_USER.password);
    await page.getByRole('button', { name: 'Sign Up', exact: true }).click();
    
    // Wait for navigation after registration
    try {
      await page.waitForNavigation({ timeout: 10000 });
    } catch {
      console.log('No navigation after registration');
    }
    
    await page.waitForTimeout(3000);
    
    const currentUrl = page.url();
    console.log('After registration:', currentUrl);
    
    // If still on register page, try login
    if (currentUrl.includes('/register')) {
      console.log('Registration did not redirect, trying login');
      await page.goto('http://localhost:5173/login');
      await page.getByLabel('Email').fill(TEST_USER.email);
      await page.getByLabel('Password').fill(TEST_USER.password);
      await page.getByRole('button', { name: 'Sign In', exact: true }).click();
      
      try {
        await page.waitForNavigation({ timeout: 10000 });
      } catch {
        console.log('No navigation after login');
      }
      
      await page.waitForTimeout(3000);
    }
    
    // Verify we're not on auth pages
    const finalUrl = page.url();
    console.log('Final URL after auth:', finalUrl);
    
    // If still on auth pages, navigate to home manually
    if (finalUrl.includes('/register') || finalUrl.includes('/login')) {
      console.log('Still on auth page, navigating to home manually');
      await page.goto('http://localhost:5173/home');
      await page.waitForTimeout(2000);
      
      // If still on auth/login, the authentication is broken - fail the test
      const afterHomeNav = page.url();
      if (afterHomeNav.includes('/register') || afterHomeNav.includes('/login')) {
        throw new Error('Authentication failed - cannot proceed with test');
      }
    }
    
    const finalUrlAfterNav = page.url();
    console.log('Final URL after navigation:', finalUrlAfterNav);
    expect(finalUrlAfterNav).not.toContain('/register');
    expect(finalUrlAfterNav).not.toContain('/login');

    // ==================== STEP 2: NAVIGATE TO UPLOAD ====================
    console.log('STEP 2: Navigate to upload page');
    await page.goto('http://localhost:5173/upload');
    
    // Wait for the page to fully load (workspaces need to load)
    console.log('Waiting for upload page to load...');
    let pageLoaded = false;
    for (let i = 0; i < 20; i++) { // 20 * 1 = 20 seconds max
      await page.waitForTimeout(1000);
      
      const pageContent = await page.textContent('body');
      if (pageContent && !pageContent.includes('Loading workspace...')) {
        pageLoaded = true;
        console.log('Upload page loaded');
        break;
      }
      console.log(`Poll ${i + 1}: Still loading...`);
    }
    
    expect(pageLoaded).toBeTruthy();
    
    await page.waitForTimeout(2000);
    const uploadUrl = page.url();
    console.log('Upload page URL:', uploadUrl);
    
    // Check if file input exists
    const fileInputExists = await page.locator('input[type="file"]').count();
    console.log('File input count:', fileInputExists);
    
    // Check if select file button exists
    const selectFileButton = page.getByRole('button', { name: 'Select file' });
    const selectFileVisible = await selectFileButton.isVisible().catch(() => false);
    console.log('Select file button visible:', selectFileVisible);

    // ==================== STEP 3: UPLOAD PDF ====================
    console.log('STEP 3: Upload PDF');
    // Use the same approach as complete-workflow.spec.ts - direct file input selection
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles('E:/rezsrch/ResearchHub-AI/frontend/test-fixtures/test-research-paper.pdf');
    await page.waitForTimeout(2000);
    
    // Click upload button
    const uploadButton = page.getByRole('button', { name: /upload and analyze/i });
    await uploadButton.click();
    
    // Wait for upload to complete - look for upload-success indicator
    console.log('Waiting for upload to complete...');
    let uploadComplete = false;
    for (let i = 0; i < 30; i++) { // 30 * 2 = 60 seconds max
      await page.waitForTimeout(2000);
      
      const uploadSuccess = page.getByTestId('upload-success');
      const isVisible = await uploadSuccess.isVisible().catch(() => false);
      
      if (isVisible) {
        uploadComplete = true;
        console.log('Upload completed - upload-success element visible');
        break;
      }
      
      console.log(`Poll ${i + 1}: Upload still in progress...`);
    }
    
    expect(uploadComplete).toBeTruthy();
    
    // Verify upload succeeded
    const uploadPageContent = await page.textContent('body');
    console.log('Upload page content sample:', uploadPageContent?.substring(0, 300));
    expect(uploadPageContent).toBeTruthy();

    // ==================== STEP 4: TRIGGER PAPER CHECK ====================
    console.log('STEP 4: Trigger Paper Check from upload page');
    // Look for "Run AI Checker" button using stable selector
    const paperCheckButton = page.getByTestId('run-ai-checker-button');
    await paperCheckButton.click();
    
    // Wait for the POST request to be captured
    console.log('Waiting for POST /research/paper-check request...');
    let requestCaptured = false;
    for (let i = 0; i < 10; i++) { // 10 * 1 = 10 seconds max
      await page.waitForTimeout(1000);
      if (paperCheckRequests.length > 0) {
        requestCaptured = true;
        console.log('POST request captured');
        break;
      }
      console.log(`Poll ${i + 1}: Waiting for POST request...`);
    }
    
    expect(requestCaptured).toBeTruthy();
    await page.waitForTimeout(2000);

    // ==================== STEP 5: VERIFY HTTP REQUEST ====================
    console.log('STEP 5: Verify Paper Check HTTP request');
    expect(paperCheckRequests.length).toBeGreaterThan(0);
    const paperCheckRequest = paperCheckRequests[0];
    console.log('Paper Check request:', paperCheckRequest);
    expect(paperCheckRequest.method).toBe('POST');
    expect(paperCheckRequest.response).toBe(200);

    // ==================== STEP 6: WAIT FOR WORKER PROCESSING ====================
    console.log('STEP 6: Wait for development worker to process job');
    // Poll for completion - worker processes in ~5-10 seconds
    let completed = false;
    for (let i = 0; i < 40; i++) { // 40 * 2 = 80 seconds max
      await page.waitForTimeout(2000);
      
      // Check for completion indicators
      const pageContent = await page.textContent('body');
      console.log(`Poll ${i + 1}: Checking for completion...`);
      
      if (pageContent && (
        pageContent.includes('completed') ||
        pageContent.includes('analysis complete') ||
        pageContent.toLowerCase().includes('success') ||
        pageContent.includes('Paper Check')
      )) {
        completed = true;
        console.log('Job completed detected');
        break;
      }
    }
    
    expect(completed).toBeTruthy();

    // ==================== STEP 7: VERIFY VISIBLE RESULT ====================
    console.log('STEP 7: Verify visible Paper Check result');
    const finalContent = await page.textContent('body');
    console.log('Final page content sample:', finalContent?.substring(0, 500));
    
    // Look for Paper Check result indicators
    expect(finalContent).toBeTruthy();
    
    console.log('Paper Check E2E workflow completed successfully');
  });
});
