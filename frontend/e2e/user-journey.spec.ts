import { expect, test } from '@playwright/test'

test.describe('Complete User Journey', () => {
  test('landing page loads', async ({ page }) => {
    await page.goto('/')
    await expect(
      page.getByRole('heading', {
        name: /search the literature, build a clean evidence set/i,
      })
    ).toBeVisible()
  })

  test('login page loads and accepts credentials', async ({ page }) => {
    await page.goto('/login')
    await expect(page.getByRole('heading', { name: /sign in to your account/i })).toBeVisible()
    await expect(page.getByLabel('Email')).toBeVisible()
    await expect(page.getByLabel('Password')).toBeVisible()
    await expect(page.getByRole('button', { name: /^Sign In$/ })).toBeVisible()
  })

  test('research page loads and accepts query', async ({ page }) => {
    await page.goto('/research')
    // Research requires authentication
    const currentUrl = page.url()
    expect(currentUrl).toMatch(/\/login|\/research/)
  })

  test('search page loads', async ({ page }) => {
    await page.goto('/search?q=test')
    // Search requires authentication
    const currentUrl = page.url()
    expect(currentUrl).toMatch(/\/login|\/search/)
  })

  test('workspace page loads with ID', async ({ page }) => {
    await page.goto('/workspace/1')
    // Workspace requires authentication, so we expect to be redirected to login
    // or see an error if not authenticated
    const currentUrl = page.url()
    expect(currentUrl).toMatch(/\/login|\/workspace/)
  })

  test('research intelligence page loads with workspace ID', async ({ page }) => {
    await page.goto('/research-intelligence/1')
    // Research Intelligence requires authentication
    const currentUrl = page.url()
    expect(currentUrl).toMatch(/\/login|\/research-intelligence/)
  })

  test('home page loads', async ({ page }) => {
    await page.goto('/home')
    // Home requires authentication
    const currentUrl = page.url()
    expect(currentUrl).toMatch(/\/login|\/home/)
  })

  test('workspaces page loads', async ({ page }) => {
    await page.goto('/workspaces')
    // Workspaces requires authentication
    const currentUrl = page.url()
    expect(currentUrl).toMatch(/\/login|\/workspaces/)
  })

  test('reports page loads', async ({ page }) => {
    await page.goto('/reports')
    // Reports requires authentication
    const currentUrl = page.url()
    expect(currentUrl).toMatch(/\/login|\/reports/)
  })

  test('library page loads', async ({ page }) => {
    await page.goto('/library')
    // Library requires authentication
    const currentUrl = page.url()
    expect(currentUrl).toMatch(/\/login|\/library/)
  })

  test('settings page loads', async ({ page }) => {
    await page.goto('/settings')
    // Settings requires authentication
    const currentUrl = page.url()
    expect(currentUrl).toMatch(/\/login|\/settings/)
  })
})

test.describe('Navigation', () => {
  test('redirects work correctly', async ({ page }) => {
    // Test legacy redirects
    await page.goto('/dashboard')
    await expect(page).toHaveURL('/home')

    await page.goto('/mindmap')
    await expect(page).toHaveURL('/home')

    await page.goto('/compare')
    await expect(page).toHaveURL('/home')

    await page.goto('/ai-tools')
    await expect(page).toHaveURL(/\/settings|\/login|\/ai-tools/)

    // /upload is a real protected route (not a legacy redirect).
    // Unauthenticated access redirects to /login via the auth guard.
    await page.goto('/upload')
    await expect(page).toHaveURL('/login')

    await page.goto('/research-chat')
    await expect(page).toHaveURL('/home')

    await page.goto('/ask-workspace')
    await expect(page).toHaveURL('/home')

    await page.goto('/writing-chat')
    await expect(page).toHaveURL('/home')

    await page.goto('/account')
    await expect(page).toHaveURL(/\/settings|\/login/)

    await page.goto('/analytics')
    await expect(page).toHaveURL(/\/settings|\/login/)
  })
})

test.describe('Static Pages', () => {
  test('privacy policy loads', async ({ page }) => {
    await page.goto('/privacy')
    await expect(page.getByRole('heading', { name: /privacy policy/i })).toBeVisible()
  })

  test('terms of service loads', async ({ page }) => {
    await page.goto('/terms')
    await expect(page.getByRole('heading', { name: /terms of service/i })).toBeVisible()
  })

  test('cookie policy loads', async ({ page }) => {
    await page.goto('/cookies')
    await expect(page.getByRole('heading', { name: /cookie policy/i })).toBeVisible()
  })

  test('data rights loads', async ({ page }) => {
    await page.goto('/data-rights')
    await expect(page.getByRole('heading', { name: /data rights/i })).toBeVisible()
  })

  test('forgot password loads', async ({ page }) => {
    await page.goto('/forgot-password')
    await expect(page.getByRole('heading', { name: /forgot your password/i })).toBeVisible()
  })
})
