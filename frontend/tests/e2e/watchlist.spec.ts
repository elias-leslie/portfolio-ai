import { test, expect } from '@playwright/test'

test.describe('Watchlist Page', () => {
  test('page loads and displays table', async ({ page }) => {
    await page.goto('/watchlist')

    // Wait for table to be visible
    await expect(page.locator('table')).toBeVisible({ timeout: 10000 })
  })

  test('displays watchlist columns', async ({ page }) => {
    await page.goto('/watchlist')

    // Wait for table to load
    await expect(page.locator('table')).toBeVisible({ timeout: 10000 })

    // Verify column headers are visible
    await expect(page.getByText('Symbol')).toBeVisible()
    await expect(page.getByText('Signal')).toBeVisible()
    await expect(page.getByText('Score')).toBeVisible()
  })

  test('can expand row for details', async ({ page }) => {
    await page.goto('/watchlist')

    // Wait for table to load
    await expect(page.locator('table')).toBeVisible({ timeout: 10000 })

    // Click first row to expand (if data exists)
    const firstRow = page.locator('tbody tr').first()
    const rowCount = await page.locator('tbody tr').count()

    if (rowCount > 0) {
      await firstRow.click()

      // Verify expanded content appears (adjust selector based on actual implementation)
      // This is an example - adjust based on your actual UI
      await expect(page.locator('[data-state="open"]')).toBeVisible()
    }
  })

  test('displays signal badges correctly', async ({ page }) => {
    await page.goto('/watchlist')

    // Wait for table to load
    await expect(page.locator('table')).toBeVisible({ timeout: 10000 })

    // Check if any signal badges are displayed
    const signalBadges = page.locator('[class*="badge"]')
    const badgeCount = await signalBadges.count()

    // If there are badges, verify they're visible
    if (badgeCount > 0) {
      await expect(signalBadges.first()).toBeVisible()
    }
  })

  test('page is responsive', async ({ page }) => {
    // Test desktop view
    await page.setViewportSize({ width: 1920, height: 1080 })
    await page.goto('/watchlist')
    await expect(page.locator('table')).toBeVisible()

    // Test mobile view
    await page.setViewportSize({ width: 375, height: 667 })
    await page.goto('/watchlist')
    // Table might be hidden or scrollable on mobile
    // Add appropriate assertions for mobile view
  })
})
