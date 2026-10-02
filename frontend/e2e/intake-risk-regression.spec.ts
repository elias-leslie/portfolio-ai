import type { PortfolioAnalytics } from '../lib/api/portfolio'
import { toSnakeCaseKeys } from 'es-toolkit'
import { expect, test } from './runtime-fixtures'

// Every upload response is synthetic; service workers must not bypass interception.
test.use({ serviceWorkers: 'block' })

const unavailableAnalytics: PortfolioAnalytics = {
  portfolioValue: { totalValue: 100, totalCostBasis: 100, totalGain: 0, totalGainPct: 0 },
  cashBalanceTotal: 0,
  cashInclusiveTotalValue: 100,
  effectiveTotalValue: 100,
  householdTotalValue: 100,
  householdInvestedTotalValue: 100,
  householdCashReserve: 0,
  householdInvestmentAccountsCount: 1,
  householdTotalsTrusted: true,
  accountControlStatus: 'clear',
  accountControlSummary: 'Synthetic reconciled account.',
  accountControlBlockingIssueCount: 0,
  portfolioBeta: 1,
  portfolioVolatility: null,
  sharpeRatio: null,
  concentration: { topHoldingPct: 100, top3Pct: 100, top10Pct: 100, herfindahlIndex: 10000, lookthroughCoveragePct: 0 },
  sectorExposure: { Technology: 100 },
  riskProfile: null,
  diversificationScore: null,
  topPerformers: [],
  bottomPerformers: [],
  numPositions: 1,
  numSymbols: 1,
}

function wireDocument(metadata: Record<string, unknown> = {}) {
  return {
    id: 'synthetic-browser-document', filename: 'synthetic-browser-evidence.csv',
    source_type: 'retirement', document_type: 'retirement_statement', status: 'staged',
    account_label: 'Synthetic account', file_size_bytes: 20, content_type: 'text/csv',
    classification_confidence: 0.95, review_status: null, review_summary: null,
    review_confidence: null, statement_start: null, statement_end: null,
    uploaded_at: '2026-05-02T20:00:00Z', parsed_at: null, metadata,
  }
}

for (const width of [390, 1280]) {
  test(`missing volatility renders unavailable risk at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const writes: string[] = []
    await page.route('**/api/**', async route => {
      const request = route.request()
      if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) {
        writes.push(`${request.method()} ${new URL(request.url()).pathname}`)
        return route.abort('blockedbyclient')
      }
      if (new URL(request.url()).pathname === '/api/portfolio/analytics') {
        return route.fulfill({ json: toSnakeCaseKeys(unavailableAnalytics) })
      }
      return route.continue()
    })
    await page.goto('/portfolio?tab=analysis')
    const risk = page.getByText('Risk posture', { exact: true }).locator('..')
    await expect(risk).toContainText('Unavailable', { timeout: 15000 })
    await expect(risk).toContainText('Beta 1.00 · volatility —.')
    await expect(risk).not.toContainText('0.0%')
    await expect(page.locator('main')).not.toContainText('Low volatility')
    expect(writes).toEqual([])
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: test.info().outputPath(`risk-unavailable-${width}.png`) })
  })

  for (const outcome of ['duplicate', 'applied', 'rebound'] as const) {
    test(`intake ${outcome} feedback follows wire metadata at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      let uploaded = false
      let interceptedUploads = 0
      const writes: string[] = []
      const initialMetadata = outcome === 'duplicate'
        ? { duplicate_detected: true }
        : outcome === 'rebound'
          ? { duplicate_detected: true, duplicate_rebound: true, duplicate_rebound_at: '2026-05-02T20:00:02Z' }
          : {}
      await page.route('**/api/**', async route => {
        const request = route.request()
        const path = new URL(request.url()).pathname
        if (path === '/api/intake/evidence' && request.method() === 'POST') {
          expect(request.postDataBuffer()?.includes(Buffer.from('synthetic-browser-evidence.csv'))).toBe(true)
          interceptedUploads += 1
          uploaded = true
          return route.fulfill({ json: wireDocument(initialMetadata) })
        }
        if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) {
          writes.push(`${request.method()} ${path}`)
          return route.abort('blockedbyclient')
        }
        if (path === '/api/intake/evidence') {
          return route.fulfill({ json: { items: uploaded ? [wireDocument({
            ...initialMetadata,
            ...(outcome !== 'duplicate' ? { application_summary: { status: 'applied' }, application_summary_updated_at: '2026-05-02T20:00:04Z' } : {}),
          })] : [], total: uploaded ? 1 : 0 } })
        }
        return route.continue()
      })
      await page.goto('/money?tab=intake#add-evidence-upload')
      const composer = page.locator('#add-evidence-upload')
      await expect(composer).toBeVisible({ timeout: 15000 })
      await composer.getByLabel('Files', { exact: true }).setInputFiles({
        name: 'synthetic-browser-evidence.csv', mimeType: 'text/csv',
        buffer: Buffer.from('symbol,shares\nSYNTHETIC,1\n'),
      })
      await composer.getByRole('button', { name: 'Upload file', exact: true }).click()
      if (outcome === 'duplicate') {
        await expect(page.getByText('synthetic-browser-evidence.csv already exists in evidence intake.', { exact: true })).toBeVisible()
        await expect(page.getByText('synthetic-browser-evidence.csv staged for evidence intake.', { exact: true })).toHaveCount(0)
      } else {
        if (outcome === 'rebound') {
          await expect(page.getByText('synthetic-browser-evidence.csv already exists; reapplying to selected account.', { exact: true })).toBeVisible()
        }
        await expect(page.getByText('synthetic-browser-evidence.csv applied to money views.', { exact: true })).toBeVisible({ timeout: 10000 })
      }
      expect(interceptedUploads).toBe(1)
      expect(writes).toEqual([])
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
      await page.screenshot({ path: test.info().outputPath(`intake-${outcome}-${width}.png`) })
    })
  }
}
