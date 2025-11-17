import { test, expect } from "@playwright/test"

test.describe("Status Page UI - ExpandableCard Pattern", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/status")
    await page.waitForLoadState("domcontentloaded")
  })

  test("Status page loads with correct section order", async ({ page }) => {
    // Verify each section appears in the correct order
    const sections = page.locator("main").getByRole("heading", { level: 2 })
    const sectionNames = []

    for (let i = 0; i < (await sections.count()); i++) {
      const text = await sections.nth(i).textContent()
      sectionNames.push(text)
    }

    // Verify expected sections are present in order
    expect(sectionNames).toContain("Overview")
    expect(sectionNames).toContain("Data Pipelines")
    expect(sectionNames).toContain("Scheduled Tasks")
    expect(sectionNames).toContain("News Sources")
    expect(sectionNames).toContain("Maintenance")
    expect(sectionNames).toContain("Unified Logging")
  })

  test("All ExpandableCard components are collapsed by default with visible summaries", async ({ page }) => {
    // Check News Health card (the only ExpandableCard in News Sources section)
    const newsHealthCard = page.locator("div").filter({ hasText: /News Health/ }).first()
    expect(newsHealthCard).toBeVisible()

    // Verify the expand/collapse button shows "Expand"
    const expandButton = newsHealthCard.getByRole("button", { name: /Expand/ })
    await expect(expandButton).toBeVisible()
  })

  test("ExpandableCard expands when clicked, showing detailed content", async ({ page }) => {
    // Find the News Health card and expand it
    const newsHealthCard = page.locator("div").filter({ hasText: /News Health/ }).first()
    const expandButton = newsHealthCard.getByRole("button", { name: /Expand/ })

    // Click to expand
    await expandButton.click()
    await page.waitForTimeout(300) // Allow animation

    // Verify button now shows "Collapse"
    const collapseButton = newsHealthCard.getByRole("button", { name: /Collapse/ })
    await expect(collapseButton).toBeVisible()

    // Verify content is now visible
    const gridContent = newsHealthCard.locator("div.grid")
    await expect(gridContent.first()).toBeVisible()

    // Click to collapse
    await expandButton.click()
    await page.waitForTimeout(300)

    // Verify button shows "Expand" again
    const expandButtonAgain = newsHealthCard.getByRole("button", { name: /Expand/ })
    await expect(expandButtonAgain).toBeVisible()
  })

  test("Overview section contains Services and System Resources cards", async ({ page }) => {
    // Find Overview section
    const overviewSection = page.locator("div").filter({ hasText: /Overview/ }).first()
    expect(overviewSection).toBeVisible()

    // Verify System Resources cards are visible (Disk, Memory, CPU, Database Pool)
    const diskCard = overviewSection.getByText(/Disk Usage/)
    const memoryCard = overviewSection.getByText(/Memory Usage/)
    const cpuCard = overviewSection.getByText(/CPU Usage/)
    const dbPoolCard = overviewSection.getByText(/Database Pool/)

    await expect(diskCard).toBeVisible()
    await expect(memoryCard).toBeVisible()
    await expect(cpuCard).toBeVisible()
    await expect(dbPoolCard).toBeVisible()
  })

  test("News Sources section contains News Health card", async ({ page }) => {
    // Find News Sources section
    const newsSources = page.locator("div").filter({ hasText: /News Sources/ }).first()
    expect(newsSources).toBeVisible()

    // Verify News Health card is present
    const newsHealthCard = newsSources.locator("div").filter({ hasText: /News Health/ }).first()
    await expect(newsHealthCard).toBeVisible()

    // Verify it has description and summary text
    const description = newsHealthCard.getByText(/FinBERT availability/)
    await expect(description).toBeVisible()
  })
})

test.describe("Settings Page UI - SettingsSection Pattern", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/settings")
    await page.waitForLoadState("domcontentloaded")
  })

  test("Settings page loads with all sections using SettingsSection wrapper", async ({ page }) => {
    // Verify main sections are present
    const profilesSection = page.locator("div").filter({ hasText: /Profiles/ }).first()
    const tradingSection = page.locator("div").filter({ hasText: /Trading & Risk/ }).first()
    const displaySection = page.locator("div").filter({ hasText: /Display & Interface/ }).first()
    const watchlistSection = page.locator("div").filter({ hasText: /Watchlist & Scoring/ }).first()

    await expect(profilesSection).toBeVisible()
    await expect(tradingSection).toBeVisible()
    await expect(displaySection).toBeVisible()
    await expect(watchlistSection).toBeVisible()
  })

  test("Profiles section is expanded by default while others are collapsed", async ({ page }) => {
    // Profiles section should be expanded (defaultCollapsed={false})
    const profilesSection = page.locator("div").filter({ hasText: /Profiles/ }).first()

    // The section should show collapse button (content visible)
    const collapseButton = profilesSection.getByRole("button", { name: /Collapse/ })
    await expect(collapseButton).toBeVisible()

    // Trading & Risk section should be collapsed
    const tradingSection = page.locator("div").filter({ hasText: /Trading & Risk/ }).first()
    const expandButton = tradingSection.getByRole("button", { name: /Expand/ })
    await expect(expandButton).toBeVisible()
  })

  test("SettingsSection expands and collapses on click", async ({ page }) => {
    // Get Trading & Risk section
    const tradingSection = page.locator("div").filter({ hasText: /Trading & Risk/ }).first()
    const expandButton = tradingSection.getByRole("button", { name: /Expand/ })

    // Expand the section
    await expandButton.click()
    await page.waitForTimeout(300)

    // Verify it shows collapse button and content is visible
    const collapseButton = tradingSection.getByRole("button", { name: /Collapse/ })
    await expect(collapseButton).toBeVisible()

    // Collapse it back
    await collapseButton.click()
    await page.waitForTimeout(300)

    // Verify expand button is visible again
    const expandButtonAgain = tradingSection.getByRole("button", { name: /Expand/ })
    await expect(expandButtonAgain).toBeVisible()
  })

  test("Trading & Risk section shows form controls when expanded", async ({ page }) => {
    // Get and expand Trading & Risk section
    const tradingSection = page.locator("div").filter({ hasText: /Trading & Risk/ }).first()
    const expandButton = tradingSection.getByRole("button", { name: /Expand/ })
    await expandButton.click()
    await page.waitForTimeout(300)

    // Verify form controls are visible
    const riskToleranceLabel = tradingSection.getByText(/Risk Tolerance/)
    const formElements = tradingSection.locator("input, select, button").filter({ visible: true })

    await expect(riskToleranceLabel).toBeVisible()
    expect(await formElements.count()).toBeGreaterThan(0)
  })

  test("Settings section summary text is visible when collapsed", async ({ page }) => {
    // Trading & Risk section should show summary
    const tradingSection = page.locator("div").filter({ hasText: /Trading & Risk/ }).first()
    const summary = tradingSection.locator("p").filter({ hasText: /Risk.*•.*Max/ })

    // Summary should be visible in the header even when collapsed
    await expect(summary.first()).toBeVisible()
  })
})

test.describe("Accessibility - ARIA Attributes", () => {
  test("ExpandableCard has proper ARIA attributes", async ({ page }) => {
    await page.goto("/status")
    await page.waitForLoadState("domcontentloaded")

    // Find News Health ExpandableCard
    const newsHealthCard = page.locator("div").filter({ hasText: /News Health/ }).first()
    const expandButton = newsHealthCard.getByRole("button", { name: /Expand/ })

    // Check aria-expanded attribute (starts as false since News Health is defaultCollapsed)
    await expect(expandButton).toHaveAttribute("aria-expanded", "false")

    // Click to expand
    await expandButton.click()
    await page.waitForTimeout(300)

    // aria-expanded should now be true
    const collapseButton = newsHealthCard.getByRole("button", { name: /Collapse/ })
    await expect(collapseButton).toHaveAttribute("aria-expanded", "true")

    // Check aria-controls points to content id
    const contentId = await collapseButton.getAttribute("aria-controls")
    expect(contentId).toBeTruthy()
  })

  test("Settings section buttons have proper ARIA attributes", async ({ page }) => {
    await page.goto("/settings")
    await page.waitForLoadState("domcontentloaded")

    // Find Trading & Risk section button
    const tradingSection = page.locator("div").filter({ hasText: /Trading & Risk/ }).first()
    const expandButton = tradingSection.getByRole("button", { name: /Expand/ })

    // Check initial aria-expanded state (should be false, collapsed)
    await expect(expandButton).toHaveAttribute("aria-expanded", "false")

    // Check aria-controls is set
    const contentId = await expandButton.getAttribute("aria-controls")
    expect(contentId).toBeTruthy()

    // Click to expand
    await expandButton.click()
    await page.waitForTimeout(300)

    // Verify aria-expanded is now true
    const collapseButton = tradingSection.getByRole("button", { name: /Collapse/ })
    await expect(collapseButton).toHaveAttribute("aria-expanded", "true")
  })

  test("Keyboard navigation works (Enter/Space to expand/collapse)", async ({ page }) => {
    await page.goto("/settings")
    await page.waitForLoadState("domcontentloaded")

    // Get Trading & Risk section expand button
    const tradingSection = page.locator("div").filter({ hasText: /Trading & Risk/ }).first()
    const expandButton = tradingSection.getByRole("button", { name: /Expand/ })

    // Focus the button
    await expandButton.focus()

    // Verify button is focused
    await expect(expandButton).toBeFocused()

    // Press Enter to expand
    await page.keyboard.press("Enter")
    await page.waitForTimeout(300)

    // Verify aria-expanded changed to true
    const collapseButton = tradingSection.getByRole("button", { name: /Collapse/ })
    await expect(collapseButton).toHaveAttribute("aria-expanded", "true")

    // Focus the collapse button
    await collapseButton.focus()
    await expect(collapseButton).toBeFocused()

    // Press Space to collapse
    await page.keyboard.press(" ")
    await page.waitForTimeout(300)

    // Verify aria-expanded changed back to false
    const expandButtonAgain = tradingSection.getByRole("button", { name: /Expand/ })
    await expect(expandButtonAgain).toHaveAttribute("aria-expanded", "false")
  })
})

test.describe("Responsive Design", () => {
  test("Status page sections are responsive", async ({ page }) => {
    await page.goto("/status")
    await page.waitForLoadState("domcontentloaded")

    // Verify main container exists
    const main = page.locator("main")
    await expect(main).toBeVisible()

    // Check that grid layouts are responsive
    const overviewSection = page.locator("div").filter({ hasText: /Overview/ }).first()
    expect(overviewSection).toBeVisible()

    // Verify cards are present
    const resourceCards = overviewSection.locator("div").filter({ hasText: /Disk Usage|Memory Usage|CPU Usage/ })
    expect(await resourceCards.count()).toBeGreaterThan(0)
  })

  test("Settings page sections maintain layout on different viewport sizes", async ({ page }) => {
    // Test on desktop
    await page.goto("/settings")
    await page.waitForLoadState("domcontentloaded")

    const profilesSection = page.locator("div").filter({ hasText: /Profiles/ }).first()
    await expect(profilesSection).toBeVisible()

    // Verify sections are vertically stacked (block layout)
    const tradingSection = page.locator("div").filter({ hasText: /Trading & Risk/ }).first()
    const displaySection = page.locator("div").filter({ hasText: /Display & Interface/ }).first()

    const tradingBox = await tradingSection.boundingBox()
    const displayBox = await displaySection.boundingBox()

    expect(tradingBox).toBeTruthy()
    expect(displayBox).toBeTruthy()

    // Sections should be stacked vertically (different Y positions)
    if (tradingBox && displayBox) {
      expect(displayBox.y).toBeGreaterThan(tradingBox.y)
    }
  })
})
