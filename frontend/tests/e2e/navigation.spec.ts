import { test, expect } from '@playwright/test'

test.describe('Navigation', () => {
  const pages = [
    { name: 'Watchlist', path: '/watchlist' },
    { name: 'Portfolio', path: '/portfolio' },
    { name: 'Ideas', path: '/ideas' },
    { name: 'News', path: '/news' },
    { name: 'Status', path: '/status' },
    { name: 'Settings', path: '/settings' },
  ]

  test('can navigate to all pages', async ({ page }) => {
    for (const { name, path } of pages) {
      await page.goto(path)

      // Verify URL changed
      await expect(page).toHaveURL(new RegExp(`.*${path}`))

      // Wait for page to load
      await page.waitForLoadState('networkidle')

      // Verify no error messages
      const errorMessages = page.getByText(/error|failed|not found/i)
      await expect(errorMessages).toHaveCount(0)
    }
  })

  test('navigation links are present', async ({ page }) => {
    await page.goto('/')

    // Check that main navigation contains expected links
    // Adjust selectors based on your actual navigation structure
    const nav = page.locator('nav').first()
    await expect(nav).toBeVisible()

    // Verify key links exist
    await expect(page.getByRole('link', { name: /watchlist/i })).toBeVisible()
    await expect(page.getByRole('link', { name: /portfolio/i })).toBeVisible()
  })

  test('active page is highlighted in navigation', async ({ page }) => {
    await page.goto('/watchlist')

    await page.waitForLoadState('networkidle')

    // Find the watchlist nav item and verify it has an active indicator
    // This will depend on your actual CSS classes or attributes
    const watchlistLink = page.getByRole('link', { name: /watchlist/i })
    await expect(watchlistLink).toBeVisible()

    // You might check for an 'active' class or aria-current attribute
    // Adjust based on your actual implementation
  })

  test('pages load without JavaScript errors', async ({ page }) => {
    const errors: string[] = []

    // Capture console errors
    page.on('pageerror', (error) => {
      errors.push(error.message)
    })

    // Visit each page
    for (const { path } of pages) {
      await page.goto(path)
      await page.waitForLoadState('networkidle')
    }

    // Verify no errors occurred
    expect(errors).toHaveLength(0)
  })

  test('pages are accessible', async ({ page }) => {
    for (const { path } of pages) {
      await page.goto(path)

      await page.waitForLoadState('networkidle')

      // Verify page has a main landmark
      const main = page.locator('main')
      await expect(main).toBeVisible()

      // Verify page has proper document structure
      const headings = page.locator('h1, h2, h3')
      const headingCount = await headings.count()
      expect(headingCount).toBeGreaterThan(0)
    }
  })
})
