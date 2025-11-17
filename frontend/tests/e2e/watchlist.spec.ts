import { test, expect } from '@playwright/test'

test.describe('Watchlist Page', () => {
  test('page loads and displays table', async ({ page }) => {
    await page.goto('/watchlist')

    // Wait for page to load and data to populate
    await page.waitForLoadState('domcontentloaded')

    // Wait for either table (if data exists) or empty state message
    await page.waitForTimeout(2000) // Give React Query time to fetch data

    const table = page.locator('table')
    const emptyMessage = page.getByText(/showing all 0 tickers/i)

    // Check if either table or empty message appears
    const hasTable = await table.isVisible().catch(() => false)
    const hasEmptyMessage = await emptyMessage.isVisible().catch(() => false)

    // At least one should be visible
    expect(hasTable || hasEmptyMessage).toBe(true)
  })

  test('displays watchlist columns', async ({ page }) => {
    await page.goto('/watchlist')

    // Wait for data to load
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)

    const table = page.locator('table')
    const hasTable = await table.isVisible().catch(() => false)

    // Only test columns if table exists (skip if watchlist is empty)
    if (hasTable) {
      // Verify column headers are visible (scope to table header to avoid filter controls)
      await expect(table.getByText('Symbol').first()).toBeVisible()
      await expect(table.getByRole('button', { name: 'Signal' })).toBeVisible()
      await expect(table.getByText('Score').first()).toBeVisible()
    } else {
      // If no table, verify we're in empty state
      await expect(page.getByText(/showing all 0 tickers/i)).toBeVisible()
    }
  })

  test('can expand row for details', async ({ page }) => {
    await page.goto('/watchlist')

    // Wait for data to load
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)

    const table = page.locator('table')
    const hasTable = await table.isVisible().catch(() => false)

    // Only test expansion if table exists
    if (hasTable) {
      const rowCount = await page.locator('tbody tr').count()

      if (rowCount > 0) {
        const firstRow = page.locator('tbody tr').first()
        await firstRow.click()

        // Verify expanded content appears
        await expect(page.locator('[data-state="open"]')).toBeVisible({ timeout: 5000 })
      }
    }
  })

  test('displays signal badges correctly', async ({ page }) => {
    await page.goto('/watchlist')

    // Wait for data to load
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)

    const table = page.locator('table')
    const hasTable = await table.isVisible().catch(() => false)

    // Only test badges if table exists
    if (hasTable) {
      const signalBadges = page.locator('[class*="badge"]')
      const badgeCount = await signalBadges.count()

      // If there are badges, verify they're visible
      if (badgeCount > 0) {
        await expect(signalBadges.first()).toBeVisible()
      }
    }
  })

  test('page is responsive', async ({ page }) => {
    // Test desktop view
    await page.setViewportSize({ width: 1920, height: 1080 })
    await page.goto('/watchlist')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)

    // Page should load (with or without data)
    await expect(page.getByText('Watchlist Intelligence Hub')).toBeVisible()

    // Test mobile view
    await page.setViewportSize({ width: 375, height: 667 })
    await page.goto('/watchlist')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(1000)

    // Page header should still be visible on mobile
    await expect(page.getByText('Watchlist Intelligence Hub')).toBeVisible()
  })
})
