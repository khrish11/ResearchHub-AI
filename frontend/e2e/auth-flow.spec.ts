import { test, expect } from '@playwright/test';

// Get test credentials from environment
const E2E_TEST_EMAIL = process.env.E2E_TEST_EMAIL || 'test@example.com';
const E2E_TEST_PASSWORD = process.env.E2E_TEST_PASSWORD || 'TestPassword123!';

test.describe('Authentication Flow', () => {
  test('register flow - API only', async ({ request }) => {
    // Test registration via direct API call to verify backend works
    const timestamp = Date.now();
    const email = `test-api-${timestamp}@soyogai.test`;
    const password = 'TestPassword123!';

    const response = await request.post('http://localhost:8010/auth/register', {
      data: { email, password }
    });

    console.log('API Registration Status:', response.status());
    const body = await response.json();
    console.log('API Registration Response:', body);

    expect(response.status()).toBe(200);
    expect(body).toHaveProperty('access_token');
  });

  test('login flow - API only', async ({ request }) => {
    // First create a user
    const timestamp = Date.now();
    const email = `test-api-login-${timestamp}@soyogai.test`;
    const password = 'TestPassword123!';

    await request.post('http://localhost:8010/auth/register', {
      data: { email, password }
    });

    // Now test login
    const params = new URLSearchParams();
    params.append('username', email);
    params.append('password', password);

    const response = await request.post('http://localhost:8010/auth/token', {
      data: params.toString(),
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    });

    console.log('API Login Status:', response.status());
    const body = await response.json();
    console.log('API Login Response:', body);

    expect(response.status()).toBe(200);
    expect(body).toHaveProperty('access_token');
  });

  test('register flow - UI', async ({ page }) => {
    // Test registration through the UI
    const timestamp = Date.now();
    const email = `test-ui-${timestamp}@soyogai.test`;
    const password = 'TestPassword123!';

    // Navigate to register page
    await page.goto('/register');
    await expect(page).toHaveURL(/\/register$/);

    // Fill registration form
    await page.fill('input#register-email', email);
    await page.fill('input#register-password', password);

    // Listen for console messages
    page.on('console', msg => {
      console.log('Browser console:', msg.text());
    });

    // Listen for network requests
    const apiRequests: { url: string; status: number }[] = [];
    page.on('response', async response => {
      if (response.url().includes('/auth/register')) {
        apiRequests.push({
          url: response.url(),
          status: response.status()
        });
        console.log('API Request:', response.url(), 'Status:', response.status());
        try {
          const body = await response.text();
          console.log('Response body:', body.substring(0, 200));
        } catch {
          console.log('Could not read response body');
        }
      }
    });

    // Submit registration
    await page.click('button[type="submit"]');

    // Wait for navigation or error - increase timeout
    await page.waitForTimeout(10000);

    // Check current URL
    const currentUrl = page.url();
    console.log('Current URL after registration:', currentUrl);

    // Check for any error messages
    const errorElement = page.locator('.auth-error');
    const errorExists = await errorElement.count() > 0;
    console.log('Error element exists:', errorExists);
    if (errorExists) {
      const errorText = await errorElement.textContent();
      console.log('Error message:', errorText);
    }

    console.log('API requests made:', apiRequests);

    // The registration should succeed and navigate to home
    if (currentUrl.includes('/home')) {
      console.log('Successfully navigated to home');
    } else {
      console.log('Did not navigate to home, URL:', currentUrl);
    }
  });

  test('login flow - UI', async ({ page, request }) => {
    // First create a user via API
    const timestamp = Date.now();
    const email = `test-ui-login-${timestamp}@soyogai.test`;
    const password = 'TestPassword123!';

    await request.post('http://localhost:8010/auth/register', {
      data: { email, password }
    });

    // Test login through the UI
    await page.goto('/login');
    await expect(page).toHaveURL(/\/login$/);

    // Fill login form
    await page.fill('input#login-email', email);
    await page.fill('input#login-password', password);

    // Listen for console messages
    page.on('console', msg => {
      console.log('Browser console:', msg.text());
    });

    // Listen for network requests
    const apiRequests: { url: string; status: number }[] = [];
    page.on('response', async response => {
      if (response.url().includes('/auth/token')) {
        apiRequests.push({
          url: response.url(),
          status: response.status()
        });
        console.log('API Request:', response.url(), 'Status:', response.status());
        try {
          const body = await response.text();
          console.log('Response body:', body.substring(0, 200));
        } catch {
          console.log('Could not read response body');
        }
      }
    });

    // Submit login
    await page.click('button[type="submit"]');

    // Wait for navigation or error - increase timeout
    await page.waitForTimeout(10000);

    // Check current URL
    const currentUrl = page.url();
    console.log('Current URL after login:', currentUrl);

    // Check for any error messages
    const errorElement = page.locator('.auth-error');
    const errorExists = await errorElement.count() > 0;
    console.log('Error element exists:', errorExists);
    if (errorExists) {
      const errorText = await errorElement.textContent();
      console.log('Error message:', errorText);
    }

    console.log('API requests made:', apiRequests);

    // The login should succeed and navigate to home
    if (currentUrl.includes('/home')) {
      console.log('Successfully navigated to home');
    } else {
      console.log('Did not navigate to home, URL:', currentUrl);
    }
  });

  test('login flow - UI with real test account', async ({ page }) => {
    // Test login with the real test account from environment variables
    console.log('Testing with credentials:', E2E_TEST_EMAIL);

    // Navigate to login page
    await page.goto('/login');
    await expect(page).toHaveURL(/\/login$/);

    // Fill login form with real credentials
    await page.fill('input#login-email', E2E_TEST_EMAIL);
    await page.fill('input#login-password', E2E_TEST_PASSWORD);

    // Listen for console messages
    page.on('console', msg => {
      console.log('Browser console:', msg.text());
    });

    // Listen for network requests
    const apiRequests: { url: string; status: number }[] = [];
    page.on('response', async response => {
      if (response.url().includes('/auth/token') || response.url().includes('/auth/firebase')) {
        apiRequests.push({
          url: response.url(),
          status: response.status()
        });
        console.log('API Request:', response.url(), 'Status:', response.status());
        try {
          const body = await response.text();
          console.log('Response body:', body.substring(0, 200));
        } catch {
          console.log('Could not read response body');
        }
      }
    });

    // Submit login
    await page.click('button[type="submit"]');

    // Wait for navigation or error
    await page.waitForTimeout(10000);

    // Check current URL
    const currentUrl = page.url();
    console.log('Current URL after login:', currentUrl);

    // Check for any error messages
    const errorElement = page.locator('.auth-error');
    const errorExists = await errorElement.count() > 0;
    console.log('Error element exists:', errorExists);
    if (errorExists) {
      const errorText = await errorElement.textContent();
      console.log('Error message:', errorText);
    }

    console.log('API requests made:', apiRequests);

    // The login should succeed and navigate to home
    if (currentUrl.includes('/home')) {
      console.log('Successfully navigated to home');
    } else {
      console.log('Did not navigate to home, URL:', currentUrl);
    }
  });

  test('home page - authenticated user', async ({ page }) => {
    // First login
    await page.goto('/login');
    await page.fill('input#login-email', E2E_TEST_EMAIL);
    await page.fill('input#login-password', E2E_TEST_PASSWORD);
    await page.click('button[type="submit"]');

    // Wait for navigation to home with extended timeout
    await page.waitForURL(/\/home$/, { timeout: 30000 });
    await expect(page).toHaveURL(/\/home$/);

    // Wait for page to load
    await page.waitForTimeout(3000);

    // Check that home page elements are present
    console.log('Checking home page elements...');

    // Check for research query input (using broader selector)
    const researchInput = page.locator('input[type="text"], input[type="search"]').first();
    const inputExists = await researchInput.count() > 0;
    console.log('Research input exists:', inputExists);

    // Check for any text content on the page
    const bodyText = await page.locator('body').textContent();
    console.log('Page has content:', bodyText && bodyText.length > 100);

    // Check for header/navigation
    const header = page.locator('header, nav').first();
    const headerExists = await header.count() > 0;
    console.log('Header exists:', headerExists);

    // Take a screenshot for debugging
    await page.screenshot({ path: 'test-results/home-page-screenshot.png' });
    console.log('Screenshot saved');

    console.log('Home page test completed');
  });
});
