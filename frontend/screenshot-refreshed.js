const { chromium } = require('playwright');

async function takeScreenshots() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  try {
    console.log('Navigating to status page...');
    await page.goto('http://192.168.8.233:3000/status', {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(3000);

    // Scroll to Celery Monitoring section
    console.log('Scrolling to Celery Monitoring...');
    await page.evaluate(() => {
      const element = document.querySelector('h2:has-text("Celery Monitoring")');
      if (element) element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    await page.waitForTimeout(1000);

    // Click Beat Schedule refresh
    console.log('Clicking Beat Schedule refresh...');
    const beatRefreshButton = page.locator('text=Beat Schedule').locator('xpath=ancestor::div[contains(@class, "Card")]').locator('button').first();
    await beatRefreshButton.click();
    await page.waitForTimeout(3000);

    // Click Celery Tasks refresh
    console.log('Clicking Celery Tasks refresh...');
    const tasksRefreshButton = page.locator('text=Celery Tasks').locator('xpath=following::button[contains(., "Refresh")]').first();
    await tasksRefreshButton.click();
    await page.waitForTimeout(5000);

    console.log('Taking screenshot of refreshed section...');
    await page.screenshot({ path: '/tmp/status-celery-section.png', fullPage: false });
    console.log('Screenshot saved to /tmp/status-celery-section.png');

  } catch (error) {
    console.error('Error:', error.message);
    throw error;
  } finally {
    await browser.close();
  }
}

takeScreenshots().catch(error => {
  console.error('Fatal error:', error);
  process.exit(1);
});
