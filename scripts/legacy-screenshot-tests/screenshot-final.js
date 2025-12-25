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
    await page.waitForTimeout(5000); // Wait for SSE data

    console.log('Taking full status page screenshot...');
    await page.screenshot({ path: '/tmp/status-page-fixed.png', fullPage: true });
    console.log('Screenshot saved to /tmp/status-page-fixed.png');

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
