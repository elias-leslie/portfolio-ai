
const { chromium } = require('playwright');
const fs = require('fs');

async function debugChart() {
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });

    console.log('Navigating...');
    await page.goto('http://192.168.8.233:3000/agents');

    console.log('Waiting for network idle...');
    await page.waitForLoadState('networkidle');

    console.log('Waiting for chart surface...');
    try {
        await page.waitForSelector('.recharts-surface', { timeout: 10000 });
    } catch (e) {
        console.log('No .recharts-surface found!');
    }

    // Force resize trick again just in case
    await page.setViewportSize({ width: 1281, height: 721 });
    await page.waitForTimeout(500);
    await page.setViewportSize({ width: 1280, height: 720 });

    console.log('Waiting 5s for animation...');
    await page.waitForTimeout(5000);

    // Dump Chart HTML
    const chartHtml = await page.evaluate(() => {
        const charts = document.querySelectorAll('.recharts-surface');
        if (charts.length === 0) return 'NO CHARTS FOUND';

        // The "Daily Runs" chart is likely the first or second one.
        // Let's dump the one that looks bar-like (contains rects or paths in a bar group)
        // Or just dump all of them to be sure.

        return Array.from(charts).map((c, i) => `--- CHART ${i} ---\n${c.outerHTML}`).join('\n\n');
    });

    console.log('--- HTML DUMP START ---');
    console.log(chartHtml);
    console.log('--- HTML DUMP END ---');

    // Check data
    const dataExists = await page.evaluate(() => {
        // Check specifically for Daily Runs
        const dailyRunsHeader = Array.from(document.querySelectorAll('h3, h4, div')).find(el => el.innerText === 'Daily Runs');
        if (!dailyRunsHeader) return 'Header "Daily Runs" not found';

        // Navigate to expected chart container sibling
        // Based on screenshots, it's: Daily Runs (header) -> div (chart)
        // But structure might vary. Let's look for rects globally.

        const rects = document.querySelectorAll('path.recharts-rectangle, rect.recharts-rectangle');
        return `Found ${rects.length} total recharts-rectangle elements on page.`;
    });

    console.log(dataExists);

    await browser.close();
}

debugChart().catch(console.error);
