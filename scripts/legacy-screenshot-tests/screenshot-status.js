const { chromium } = require('playwright');

async function takeScreenshots() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();

  try {
    // Status page
    console.log('Navigating to status page...');
    const statusPage = await context.newPage();
    await statusPage.goto('http://192.168.8.233:3000/status', {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    console.log('Waiting for initial load...');
    await statusPage.waitForTimeout(3000);

    // Click refresh on Beat Schedule
    console.log('Refreshing Beat Schedule...');
    try {
      const beatRefresh = await statusPage.locator('text=Beat Schedule').locator('..').locator('button:has-text("Refresh")').first();
      await beatRefresh.click();
      await statusPage.waitForTimeout(2000);
    } catch (e) {
      console.log('Could not click Beat Schedule refresh:', e.message);
    }

    // Click refresh on Celery Tasks
    console.log('Refreshing Celery Tasks...');
    try {
      const taskRefresh = await statusPage.locator('text=Celery Tasks').locator('..').locator('button:has-text("Refresh")').first();
      await taskRefresh.click();
      await statusPage.waitForTimeout(3000);
    } catch (e) {
      console.log('Could not click Celery Tasks refresh:', e.message);
    }

    console.log('Taking status page screenshot...');
    await statusPage.screenshot({ path: '/tmp/status-page.png', fullPage: true });
    console.log('Status page screenshot saved to /tmp/status-page.png');

    await statusPage.close();

    // Settings page (already captured)
    console.log('\nSettings page already captured at /tmp/settings-page.png');

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
