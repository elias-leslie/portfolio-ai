const { chromium } = require('playwright');

async function testMarketConditions() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  try {
    console.log('1. Navigating to dashboard...');
    await page.goto('http://192.168.8.233:3000', {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(5000);

    console.log('2. Taking initial screenshot...');
    await page.screenshot({ path: '/tmp/dashboard-initial.png', fullPage: true });

    console.log('3. Looking for Market Conditions card...');
    const hasMarketConditions = await page.locator('text=Market Conditions').count() > 0;
    console.log(`   Market Conditions found: ${hasMarketConditions}`);

    console.log('4. Looking for breakdown button...');
    const breakdownButton = page.locator('button', { hasText: /Show.*Breakdown/i }).first();
    const buttonExists = await breakdownButton.count() > 0;
    console.log(`   Breakdown button found: ${buttonExists}`);

    if (buttonExists) {
      console.log('5. Clicking breakdown button...');
      await breakdownButton.click();
      await page.waitForTimeout(2000);

      console.log('6. Checking for Sector Performance...');
      const hasSectors = await page.locator('text=/Sector Performance/i').count() > 0;
      console.log(`   Sector Performance found: ${hasSectors}`);

      console.log('7. Taking expanded screenshot...');
      await page.screenshot({ path: '/tmp/market-conditions-expanded.png', fullPage: true });
      console.log('   Screenshot saved!');
    }

  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await browser.close();
  }
}

testMarketConditions();
