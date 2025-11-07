# Status Page Screenshot Scripts

Collection of Playwright scripts for automated screenshot capture of the status page for testing and verification.

## Prerequisites

Playwright must be installed (already available in frontend/node_modules):
```bash
cd ~/portfolio-ai/frontend
# Playwright is already installed via package.json
```

## Available Scripts

### screenshot-status.js
Basic status page screenshot after waiting for SSE data to load.

**Usage:**
```bash
cd ~/portfolio-ai/frontend
node screenshot-status.js
```

**Output:** `/tmp/status-page.png`

**Use case:** Quick visual verification of overall status page layout and data

---

### screenshot-celery-tasks.js
Screenshots the Celery Tasks table after clicking the Refresh button.

**Usage:**
```bash
cd ~/portfolio-ai/frontend
node screenshot-celery-tasks.js
```

**Output:** `/tmp/celery-tasks-table.png`

**Use case:** Verify Celery Tasks table displays task names, workers, and statuses correctly

---

### screenshot-tasks-fixed.js
Same as screenshot-celery-tasks.js but with different output name for comparison.

**Usage:**
```bash
cd ~/portfolio-ai/frontend
node screenshot-tasks-fixed.js
```

**Output:** `/tmp/celery-tasks-fixed.png`

**Use case:** Compare before/after fixes to Celery Tasks table

---

### screenshot-beat-schedule.js
Screenshots the Beat Schedule card after clicking its refresh button.

**Usage:**
```bash
cd ~/portfolio-ai/frontend
node screenshot-beat-schedule.js
```

**Output:** `/tmp/beat-schedule-refreshed.png`

**Use case:** Verify Beat Schedule shows correct user-configured intervals

---

### screenshot-final.js
Comprehensive status page screenshot after waiting for all data to load.

**Usage:**
```bash
cd ~/portfolio-ai/frontend
node screenshot-final.js
```

**Output:** `/tmp/status-page-fixed.png`

**Use case:** Final verification screenshot showing all fixes working together

---

### screenshot-task-expanded.js
Screenshots an expanded Celery task to verify the result/traceback section displays correctly in dark mode.

**Usage:**
```bash
cd ~/portfolio-ai/frontend
node screenshot-task-expanded.js
```

**Output:** `/tmp/task-expanded-dark.png`

**Use case:** Verify dark mode colors for task details (result, traceback, args, kwargs)

---

## Common Patterns

### Basic Template
```javascript
const { chromium } = require('playwright');

async function takeScreenshot() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  try {
    // Navigate with domcontentloaded for SSE pages
    await page.goto('http://192.168.8.233:3000/status', {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });

    // Wait for SSE data
    await page.waitForTimeout(3000);

    // Take screenshot
    await page.screenshot({ path: '/tmp/output.png', fullPage: true });

  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await browser.close();
  }
}

takeScreenshot();
```

### Clicking Elements
```javascript
// Find and click a button
const button = page.locator('button:has-text("Refresh")').first();
await button.click();
await page.waitForTimeout(2000); // Wait for action to complete
```

### Scrolling to Element
```javascript
await page.evaluate(() => {
  const elements = Array.from(document.querySelectorAll('h3'));
  const target = elements.find(el => el.textContent?.includes('Celery Tasks'));
  if (target) {
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
});
await page.waitForTimeout(1000);
```

### Expanding UI Components
```javascript
// Click first chevron to expand
const chevron = page.locator('svg[class*="lucide-chevron"]').first();
await chevron.click();
await page.waitForTimeout(1000);
```

## Important Notes

1. **SSE Pages**: Status page uses Server-Sent Events (SSE), so use `domcontentloaded` instead of `networkidle`
2. **Wait Times**: Always add `waitForTimeout()` after navigation or clicks to let data populate
3. **Headless Mode**: Scripts run in headless mode by default (no visible browser window)
4. **IP Address**: Scripts use `192.168.8.233:3000` - adjust if running on different host
5. **Output Location**: All screenshots saved to `/tmp/` directory

## Debugging

To see browser window (non-headless mode):
```javascript
const browser = await chromium.launch({ headless: false });
```

To see console logs:
```javascript
page.on('console', msg => console.log('PAGE LOG:', msg.text()));
```

To increase timeouts:
```javascript
await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 120000 }); // 2 minutes
```

## Related

- Browser Automation Skill: `~/.claude/skills/browser-automation/`
- Status Page Component: `frontend/app/status/page.tsx`
- Celery Monitoring: `frontend/components/status/CeleryTaskTable.tsx`

---

**Last Updated:** 2025-11-07
**Purpose:** Automated testing and visual verification of status page fixes
