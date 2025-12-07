# Task: Fix Missing Bars in Recharts Capture

**Context**: The `capture-evidence.js` script (Playwright) captures screenshots of the `/agents` page. The "Daily Runs" chart (Recharts `BarChart`) renders correctly in a normal browser but **fails to render bars** (showing only grid lines) in the headless capture.

**File**: `.claude/skills/browser-automation/scripts/capture-evidence.js`

**The Issue**:
- The chart container size might be initializing to 0/0 or -1/-1, causing Recharts to skip rendering.
- Animations might be playing during the capture instant, resulting in 0-height bars.
- Existing fixes (Viewport resize hack, CSS animation disable, waiting for `.recharts-rectangle` with height > 0) have **failed** to consistently show the bars in the screenshot.

**Instructions**:
1.  Analyze `capture-evidence.js` and the "Daily Runs" chart implementation in `frontend/app/agents/page.tsx`.
2.  Implement a robust fix to ensure Recharts bars are fully rendered before screenshot.
3.  Consider:
    - Injecting a script to force `isAnimationActive={false}` on the Recharts instances if possible (though difficult with compiled React).
    - Using `page.evaluate()` to manually trigger a window resize event *after* a delay.
    - identifying if `ResponsiveContainer` needs a specific non-percentage height in the capture environment.
    - Adding a specific wait condition that checks the *SVG path data* (`d` attribute) of bars to ensure they are not empty/zero-height, rather than just checking for element existence.
4.  Verify the fix by running the capture script `node .claude/skills/browser-automation/scripts/capture-evidence.js http://localhost:3000/agents FEAT-110 ac-001` and inspecting the resulting `screenshot.png` to ensure bars are visible.
