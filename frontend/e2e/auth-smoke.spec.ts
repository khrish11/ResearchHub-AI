import { expect, test } from '@playwright/test'

test('landing page renders and routes to register', async ({ page }) => {
  await page.goto('/')
  
  // Verify landing page loads with appropriate content
  // Use a more flexible selector that works across desktop and mobile
  await expect(page.getByRole('heading', { name: /soyog ai/i }).first()).toBeVisible()
  
  // Verify Create Account link exists and is clickable
  const createAccountLink = page.getByRole('link', { name: /create account/i }).first()
  await expect(createAccountLink).toBeVisible()
  await createAccountLink.click()
  
  await expect(page).toHaveURL(/\/register$/)
  await expect(page.getByRole('heading', { name: /create your account/i })).toBeVisible()
})

test('login page renders credentials form', async ({ page }) => {
  await page.goto('/login')

  await expect(page.getByRole('heading', { name: /sign in to your account/i })).toBeVisible()
  await page.getByLabel('Email').fill('qa@example.com')
  await page.getByLabel('Password').fill('Passw0rd!')
  await expect(page.getByRole('button', { name: /^Sign In$/ })).toBeVisible()
})
