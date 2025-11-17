const { chromium } = require('playwright');

async function captureSchedule() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  try {
    console.log('Navigating to status page...');
    await page.goto('http://192.168.8.233:3000/status', {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(3000);

    // Scroll to Beat Schedule
    await page.evaluate(() => {
      const elements = Array.from(document.querySelectorAll('*'));
      const beatCard = elements.find(el => el.textContent?.includes('Beat Schedule'));
      if (beatCard) {
        beatCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    });
    await page.waitForTimeout(1000);

    // Find and click the refresh button in Beat Schedule card
    console.log('Clicking Beat Schedule refresh button...');
    const cards = await page.locator('[class*="Card"]').all();
    for (const card of cards) {
      const text = await card.textContent();
      if (text?.includes('Beat Schedule')) {
        const refreshBtn = card.locator('button').first();
        await refreshBtn.click();
        console.log('Clicked refresh button');
        await page.waitForTimeout(3000);
        break;
      }
    }

    console.log('Taking screenshot...');
    await page.screenshot({ path: '/tmp/beat-schedule-refreshed.png', fullPage: false });
    console.log('Screenshot saved');

  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await browser.close();
  }
}

captureSchedule();
