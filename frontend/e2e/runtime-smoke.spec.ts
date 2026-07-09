import { expect, test } from '@playwright/test'

const appOrigin = new URL(
  process.env.PLAYWRIGHT_BASE_URL ?? 'http://127.0.0.1:3000',
).origin

const routes = [
  ['Today', '/', /Today/],
  ['Money', '/money', /Money/],
  ['Portfolio', '/portfolio', /Investing/],
  ['Drift', '/portfolio/drift', /How am I doing on my goals/],
  ['Status', '/status', /Status/],
  ['Watchlist redirect', '/watchlist', /Investing/],
  ['Symbol detail', '/symbols/AAPL', /AAPL/],
] as const

for (const [name, path, expectedText] of routes) {
  test(`${name} renders without runtime errors`, async ({ page }) => {
    const runtimeErrors: string[] = []
    page.on('console', (message) => {
      if (message.type() === 'error') runtimeErrors.push(message.text())
    })
    page.on('pageerror', (error) => runtimeErrors.push(error.message))
    page.on('response', (response) => {
      if (new URL(response.url()).origin === appOrigin && response.status() >= 500) {
        runtimeErrors.push(`${response.status()} ${response.url()}`)
      }
    })

    const response = await page.goto(path, { waitUntil: 'domcontentloaded' })
    expect(response?.status()).toBeLessThan(500)
    await expect(page.locator('main')).toBeVisible()
    await expect(page.locator('main')).toContainText(expectedText, {
      timeout: 15_000,
    })
    await expect(page.locator('body')).not.toContainText(
      /Application error|Internal Server Error/,
    )
    expect(runtimeErrors).toEqual([])
  })
}

test('proxied detailed health returns operational database pressure', async ({
  request,
}) => {
  const response = await request.get('/health/detailed')
  expect(response.ok()).toBe(true)

  const body = await response.json()
  expect(['healthy', 'degraded']).toContain(body.status)
  expect(body.checks.database.status).toBe('ok')
  expect(body.checks.database.details.max_connections).toBeGreaterThan(0)
  expect(body.checks.database.details.utilization_pct).toBeGreaterThanOrEqual(0)
})
