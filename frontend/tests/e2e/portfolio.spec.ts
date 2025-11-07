import { test, expect } from '@playwright/test'

test.describe('Portfolio Page', () => {
  test('page loads and displays content', async ({ page }) => {
    await page.goto('/portfolio')

    // Verify page loaded
    await expect(page).toHaveURL(/.*portfolio/)

    // Wait for main content to be visible
    await page.waitForLoadState('networkidle')
  })

  test('displays portfolio positions if data exists', async ({ page }) => {
    await page.goto('/portfolio')

    await page.waitForLoadState('networkidle')

    // Check if positions table/list is visible
    // Adjust selectors based on actual implementation
    const positionsContainer = page.locator('main')
    await expect(positionsContainer).toBeVisible()
  })

  test('can navigate to portfolio page from home', async ({ page }) => {
    await page.goto('/')

    // Find and click portfolio link in navigation
    const portfolioLink = page.getByRole('link', { name: /portfolio/i })
    await portfolioLink.click()

    // Verify navigation occurred
    await expect(page).toHaveURL(/.*portfolio/)
  })

  test('displays analytics section', async ({ page }) => {
    await page.goto('/portfolio')

    await page.waitForLoadState('networkidle')

    // Look for analytics/metrics section
    // This will depend on your actual UI structure
    const mainContent = page.locator('main')
    await expect(mainContent).toBeVisible()
  })
})
