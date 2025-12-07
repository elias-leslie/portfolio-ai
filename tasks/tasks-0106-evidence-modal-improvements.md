# Task: Evidence Modal UI Improvements

**Source**: User feedback on EvidenceViewerModal
**Complexity**: Medium
**Effort**: LOW
**Environment**: Local Dev
**Created**: 2025-12-07

---

## Summary

**Goal**: Fix layout and sizing issues in the EvidenceViewerModal component so it properly fills the browser viewport and each section scrolls independently.

**Current Issues**:
1. Modal doesn't expand to full browser height
2. Screenshot is zoomed out / degraded instead of true-to-life size
3. Sections can overlay each other when content is large
4. No scroll bars for oversized content within sections
5. Click-to-zoom feature is unnecessary and should be removed

---

## Requirements

### 1. Modal Size & Responsiveness

- Modal MUST fill the browser viewport vertically (top to bottom)
- Modal should have a fixed max-width (e.g., `max-w-5xl` or `max-w-6xl`)
- Modal MUST resize dynamically when browser window is resized
- Use `h-[100vh]` or similar to ensure full height
- Account for any padding/margins so content touches top and bottom

### 2. Screenshot Tab

- Display screenshot at **true-to-life size** (1:1 pixel ratio)
- NO zoom out, NO visual degradation, NO scaling down
- NO click-to-zoom feature - remove any zoom-related code
- Container should have `overflow: auto` for both horizontal and vertical scrollbars
- If screenshot is larger than container, user scrolls to see all of it
- Screenshot should be displayed as `<img>` with `width: auto; height: auto;`

### 3. Console Tab

- Display console errors and warnings in a scrollable container
- Container should have `overflow-y: auto` with a fixed max height
- Each error/warning should be its own contained block
- Preserve current styling (red for errors, yellow for warnings)

### 4. Network Tab

- Display failed requests and slow requests in a scrollable container
- Container should have `overflow-y: auto` with a fixed max height
- Each request should be its own contained block

### 5. Page State Tab

- Display page info, key elements, performance, and content preview
- Container should have `overflow-y: auto` if content exceeds space
- Each subsection should be clearly separated

### 6. Section Containment

- **CRITICAL**: No section should overlay another
- Each tab content area should be bounded within its container
- User review section at bottom must ALWAYS be visible (not covered)
- Use proper flex layout to ensure sections don't bleed into each other

---

## File to Modify

`frontend/components/capabilities/EvidenceViewerModal.tsx`

---

## Implementation Steps

### Step 1: Read Current Implementation

Read the file and understand the current structure:
- How is DialogContent sized?
- How is ScrollArea used?
- What state variables exist for zoom/expand features?

### Step 2: Remove Zoom/Expand Features

- Remove `screenshotExpanded` state variable
- Remove any zoom-related state (`zoom`, `pan`, etc.) if present
- Remove click handlers for expanding screenshots
- Remove the expanded overlay div

### Step 3: Fix Modal Size

Update DialogContent to fill viewport:
```tsx
<DialogContent className="max-w-5xl w-full h-[95vh] flex flex-col">
```

### Step 4: Fix Tab Content Layout

Each TabsContent should:
```tsx
<TabsContent value="screenshot" className="flex-1 overflow-hidden">
  <div className="h-full overflow-auto">
    <img
      src={data?.screenshot_url}
      alt="Screenshot"
      style={{ width: 'auto', height: 'auto' }}
    />
  </div>
</TabsContent>
```

### Step 5: Fix Overall Layout Structure

```tsx
<DialogContent className="max-w-5xl w-full h-[95vh] flex flex-col p-0">
  <DialogHeader className="p-4 border-b shrink-0">
    {/* Title and badges */}
  </DialogHeader>

  {/* Version nav and actions - fixed height */}
  <div className="p-2 border-b shrink-0">
    {/* Version controls, refresh button, etc. */}
  </div>

  {/* Tabs - takes remaining space */}
  <Tabs className="flex-1 flex flex-col overflow-hidden">
    <TabsList className="shrink-0">
      {/* Tab triggers */}
    </TabsList>

    {/* Tab content - scrollable */}
    <div className="flex-1 overflow-hidden">
      <TabsContent className="h-full overflow-auto">
        {/* Content */}
      </TabsContent>
    </div>
  </Tabs>

  {/* User review section - fixed at bottom */}
  <div className="p-4 border-t shrink-0">
    {/* Approve/Reject buttons, notes textarea */}
  </div>
</DialogContent>
```

### Step 6: Test Each Tab

After changes, verify:
1. Screenshot tab: Large screenshot shows scrollbars, no zoom
2. Console tab: Many errors show scrollbar, content doesn't overflow
3. Network tab: Many failures show scrollbar, content doesn't overflow
4. Page state tab: Content is contained within its section
5. User review section: Always visible at bottom

---

## Verification Checklist

- [ ] Modal fills browser viewport vertically (95vh or similar)
- [ ] Modal resizes when browser window resizes
- [ ] Screenshot displays at true 1:1 size (no scaling)
- [ ] Screenshot container has scrollbars when image is larger than container
- [ ] No zoom or click-to-expand functionality exists
- [ ] Console tab content scrolls independently
- [ ] Network tab content scrolls independently
- [ ] Page State tab content scrolls independently
- [ ] User review section is ALWAYS visible at bottom
- [ ] No section overlays another
- [ ] TypeScript compiles without errors

---

## Test URLs

Use these to test the modal:

```bash
# Capture evidence for a test feature
node ~/portfolio-ai/.claude/skills/browser-automation/scripts/capture-evidence.js \
  http://192.168.8.233:3000/watchlist FEAT-TEST ac-test

# Then open /capabilities → Features → expand a row → click Evidence button
```

---

## Notes

- The modal uses shadcn Dialog component
- Tab component uses controlled state (`value`, `onValueChange`)
- Current file location: `frontend/components/capabilities/EvidenceViewerModal.tsx`
- Related file: `frontend/components/capabilities/FeaturesTab.tsx` (opens the modal)

---

**Version**: 1.0.0 | **Created**: 2025-12-07
