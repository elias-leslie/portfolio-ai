import type { Page } from '@playwright/test'
import { expect, test } from './runtime-fixtures'

async function waitForFinancialContent(page: Page, view: string) {
  await page.waitForFunction(name => performance.getEntriesByName(`portfolio-ai:usable:${name}`).length > 0, view, { timeout: 60_000 })
  const duration = await page.evaluate(name => performance.getEntriesByName(`portfolio-ai:usable:${name}`).at(-1)?.duration, view)
  await test.info().attach(`${view}-usable-content-ms`, { body: String(duration), contentType: 'text/plain' })
  const resources = await page.evaluate(() => performance.getEntriesByType('resource').filter(entry => new URL(entry.name).pathname.startsWith('/api/')).map(entry => ({ path: new URL(entry.name).pathname, duration: Math.round(entry.duration), startedAt: Math.round(entry.startTime) })))
  await test.info().attach(`${view}-requests`, { body: JSON.stringify(resources), contentType: 'application/json' })
}

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
    if (name === 'Today') await waitForFinancialContent(page, 'today')
    if (name === 'Money') await waitForFinancialContent(page, 'money-review')
    if (name === 'Symbol detail') await waitForFinancialContent(page, 'symbol-decision')
    await expect(page.locator('body')).not.toContainText(
      /Application error|Internal Server Error/,
    )
    expect(runtimeErrors).toEqual([])
  })
}

for (const width of [390, 1280]) {
  test(`monthly review and exact ledger preserve context at ${width}px`, async ({ page, request }) => {
    test.setTimeout(120_000)
    await page.setViewportSize({ width, height: 900 })
    const latest = await (await request.get('/api/household/spending')).json()
    const currentMonth: string = latest.summary.month
    const closedMonth: string | undefined = latest.available_months.filter((month: string) => month < currentMonth).at(-1)
    expect(closedMonth).toBeTruthy()
    for (const month of [closedMonth!, currentMonth]) {
      await page.goto(`/money?tab=spending&month=${month}`)
      await waitForFinancialContent(page, 'money-review')
      await page.screenshot({ path: test.info().outputPath(`review-${month}-${width}.png`) })
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
      const review = await (await request.get(`/api/household/spending?month=${month}`)).json()
      expect(review.summary.month).toBe(month)
      if (month === currentMonth) {
        expect(review.summary.is_month_to_date).toBe(true)
        await expect(page.locator('main')).not.toContainText(/came in .* under your caps/)
      }
      const category: string = review.categories[0].category
      const ledgerResponse = page.waitForResponse(response => {
        const url = new URL(response.url())
        return url.pathname === '/api/household/ledger' && url.searchParams.get('month') === month && url.searchParams.get('category') === category
      })
      await page.getByRole('link', { name: `Check ${category} in the ledger`, exact: true }).click()
      const ledger = await (await ledgerResponse).json()
      expect(ledger.review_spend_total).toBeCloseTo(review.categories[0].total_spend, 2)
      await expect(page.getByLabel('Ledger calendar month')).toHaveValue(month)
      expect(new URL(page.url()).searchParams.get('ledgerCategory')).toBe(category)
      await page.goBack()
      await expect(page.getByRole('link', { name: `Check ${category} in the ledger`, exact: true })).toBeVisible()
      expect(new URL(page.url()).searchParams.get('month')).toBe(month)
    }
  })
}

test('retirement and analysis reach a completed financial result', async ({ page }) => {
  test.setTimeout(150_000)
  const previewRequests: string[] = []
  page.on('request', request => {
    if (new URL(request.url()).pathname === '/api/retirement/preview') previewRequests.push(request.url())
  })
  await page.goto('/money?tab=retirement')
  await waitForFinancialContent(page, 'retirement')
  expect(previewRequests).toHaveLength(1)
  await page.screenshot({ path: test.info().outputPath('retirement-completed.png') })
  await expect(page.locator('main')).not.toContainText(/First depletion: None/)
  await page.goto('/portfolio?tab=analysis')
  await waitForFinancialContent(page, 'investment-analysis')
})

test('phone tabs stay reachable with the keyboard as account counts load', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/money?tab=spending')
  await waitForFinancialContent(page, 'money-review')
  await page.getByRole('tab', { name: 'Review', exact: true }).focus()
  await page.keyboard.press('End')
  const intake = page.getByRole('tab', { name: /^Intake/ })
  await expect(intake).toHaveAttribute('aria-selected', 'true')
  await expect(intake).toBeFocused()
  await expect.poll(async () => {
    const box = await intake.boundingBox()
    return Boolean(box && box.x >= 0 && box.x + box.width <= 390)
  }).toBe(true)
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390)
  await page.screenshot({ path: test.info().outputPath('intake-keyboard-phone.png') })
  await page.keyboard.press('Home')
  await expect(page.getByRole('tab', { name: 'Net worth', exact: true })).toBeFocused()
})

test('Track requires a rationale and offers actions for the current position', async ({ page, request }) => {
  await page.goto('/symbols/AAPL?tab=decision')
  await waitForFinancialContent(page, 'symbol-decision')
  await page.getByRole('tab', { name: 'Track', exact: true }).click()
  await expect(page.getByLabel('Decision rationale (required)')).toBeVisible()
  const workflow = await (await request.get('/api/symbols/AAPL/workflow')).json()
  expect(workflow.available_actions.length).toBeGreaterThan(0)
  for (const action of workflow.available_actions) {
    await expect(page.getByRole('button', { name: `Record ${action.replaceAll('_', ' ')}`, exact: true })).toBeDisabled()
  }
})

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
