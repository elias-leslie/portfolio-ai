/**
 * Dialog helper utilities for maintenance and confirmation dialogs.
 *
 * Consolidates duplicate shouldShowDialog implementations across components.
 */

/**
 * Determine if a confirmation dialog should be shown.
 *
 * Logic:
 * - Always returns true on server-side (SSR safety)
 * - Always returns true for live operations (confirmation required)
 * - Otherwise checks localStorage for user preference
 *
 * @param storageKey - localStorage key for user's "don't show again" preference
 * @param isLiveOperation - If true, dialog is always shown (default: false)
 * @returns true if dialog should be shown
 */
export function shouldShowDialog(
  storageKey: string,
  isLiveOperation: boolean = false
): boolean {
  // SSR safety
  if (typeof window === "undefined") return true;

  // Live operations always show confirmation
  if (isLiveOperation) return true;

  // Check user preference
  return !localStorage.getItem(storageKey);
}
