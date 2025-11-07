const { chromium } = require('playwright');

async function captureCeleryTasks() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  try {
    console.log('Navigating to status page...');
    await page.goto('http://192.168.8.233:3000/status', {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(3000);

    // Scroll to Celery Tasks section
    console.log('Scrolling to Celery Tasks...');
    await page.evaluate(() => {
      const elements = Array.from(document.querySelectorAll('h3'));
      const celeryTasksHeader = elements.find(el => el.textContent?.includes('Celery Tasks'));
      if (celeryTasksHeader) {
        celeryTasksHeader.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
    await page.waitForTimeout(1500);

    // Click the Refresh button in Celery Tasks section
    console.log('Clicking Celery Tasks refresh button...');
    const refreshButton = page.locator('h3:has-text("Celery Tasks")').locator('xpath=following::button[contains(., "Refresh")]').first();
    await refreshButton.click();
    console.log('Clicked refresh, waiting for data...');
    await page.waitForTimeout(5000);

    console.log('Taking screenshot...');
    await page.screenshot({ path: '/tmp/celery-tasks-fixed.png', fullPage: false });
    console.log('Screenshot saved to /tmp/celery-tasks-fixed.png');

  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await browser.close();
  }
}

captureCeleryTasks();
