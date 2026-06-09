/** Shared UI-state types for the Money accounts panel and its child sections. */

/** Which area of the accounts panel the user is focused on. */
export type MoneyAccountsFocus = 'coverage' | 'discovered' | null

/** Why the panel is open (drives evidence vs. review affordances). */
export type MoneyAccountsIntent = 'evidence' | 'review' | null
