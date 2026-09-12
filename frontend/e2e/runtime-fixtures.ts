import { chromium, expect, test as base, type Browser } from '@playwright/test'

// A managed ST browser can be reused without starting another Chrome instance.
// Obtain the endpoint with `st browser --local-ai get cdp-url`.
const endpoint = process.env.ST_BROWSER_CDP_ENDPOINT
export const test = endpoint
  ? base.extend<{}, { browser: Browser }>({
      browser: [async ({}, use) => {
        const browser = await chromium.connectOverCDP(endpoint)
        await use(browser)
        await browser.close() // Disconnect this client from the managed browser.
      }, { scope: 'worker' }],
    })
  : base

export { expect }
