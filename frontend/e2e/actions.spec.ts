import { expect, test } from './runtime-fixtures'

// The app's service worker can own subsequent requests and bypass route fixtures.
test.use({ serviceWorkers: 'block' })

for (const width of [390, 1280]) {
  test(`Actions stays in the top bar and answers in place at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const questions = [
      { id: 'synthetic-shopping', title: 'Synthetic shop: regular groceries?', format: 'boolean', options: [] },
      { id: 'synthetic-cadence', title: 'Synthetic membership: billing frequency?', format: 'single_select', options: ['Monthly', 'Annually'] },
      { id: 'synthetic-age', title: 'Synthetic retirement age?', format: 'integer', options: [] },
    ]
    const answers: Record<string, string> = {}
    await page.route('**/api/home/action-queue*', route => route.fulfill({ json: {
      generated_at: new Date().toISOString(), summary: 'Synthetic test queue.',
      actions: questions.filter(q => !(q.id in answers)).map(q => ({
        id: q.id, source: 'household', category: 'household', priority: 'medium',
        title: q.title, detail: 'Synthetic evidence; no real household records.',
        action_label: 'Answer question', href: '/money?tab=intake', question: q,
      })),
    } }))
    // Intercept every answer write: this journey cannot update household records.
    await page.route('**/api/household/questions/*/answer', route => {
      const id = new URL(route.request().url()).pathname.split('/').at(-2)!
      expect(questions.some(q => q.id === id)).toBe(true)
      answers[id] = route.request().postDataJSON().answer_text
      return route.fulfill({ json: { id, status: 'answered', answer_text: answers[id] } })
    })
    await page.goto('/')
    await expect(page.getByRole('button', { name: 'Action Queue, 3 open' })).toBeVisible()
    await expect(page.locator('main [data-action-queue-item]')).toHaveCount(0)
    await expect(page.locator('main')).not.toContainText('Needs attention')
    await expect(page.getByText(questions[0].title)).toHaveCount(0)
    await page.getByRole('button', { name: 'Action Queue, 3 open' }).click()
    const popover = page.getByRole('dialog', { name: 'Action Queue' })
    await expect(popover.getByRole('button', { name: 'Yes', exact: true })).toBeVisible()
    await popover.getByRole('button', { name: 'Yes', exact: true }).click()
    await expect(popover.getByText(questions[0].title)).toHaveCount(0)
    await popover.getByRole('button', { name: 'Annually', exact: true }).click()
    await expect(popover.getByText(questions[1].title)).toHaveCount(0)
    await popover.getByLabel(`Your answer to ${questions[2].title}`).fill('62')
    await popover.getByRole('button', { name: 'Save answer' }).click()
    await expect(popover).toContainText('All clear')
    await expect(page.getByRole('button', { name: 'Action Queue, 0 open' })).toBeVisible()
    expect(answers).toEqual({ 'synthetic-shopping': 'yes', 'synthetic-cadence': 'Annually', 'synthetic-age': '62' })
    expect(new URL(page.url()).pathname).toBe('/')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.keyboard.press('Escape')
    await expect(popover).toHaveCount(0)
    await expect(page.locator('main [data-action-queue-item]')).toHaveCount(0)
  })
}
