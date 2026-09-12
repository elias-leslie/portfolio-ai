# Household card strategy

Task: `task-7af674d86c204915`.

## Outcome

Cards leads with a reviewable household strategy: which purchases stay on keeper cards, the next card and applicant, a feasible application window, and the evidence behind the recommendation. Approval starts tracking a saved revision. New evidence may suggest a replacement; it never silently changes the approved plan. Actual applications, opened accounts, payment changes and received bonuses remain distinct recorded events.

## Implementation

1. Derive spending from canonical, deduplicated transactions over three complete months. Exclude pending purchases, fees, irregular travel and off-card payments. Show the months, merchant reservations, cash-flow evidence, coverage gaps and conservative buffer. Reuse the household income anchor and affordability calculation; budget caps can lower this estimate, never manufacture spending.
2. Evaluate card/applicant pairs using recorded ownership, bonus history, current issuer evidence, achievable spending and conservative reward value net of annual fees and rewards available on existing cards. Include waiting, respect existing unfinished bonuses, and use real offer windows rather than fixed quarterly rotation. Unknown eligibility and stale terms are explicit checks.
3. Save immutable draft snapshots with fingerprints. Approve a concrete revision transactionally, superseding the old one only on approval. Reject stale approvals. Support pausing and linking the matching, actually opened household card; a proposed card never becomes an owned card through plan approval.
4. Track eligible posted purchases and refunds from the linked account, separately report pending spending, and use the original approved offer and actual opening/deadline dates. Never count projected bonuses as received. Reserve household spending once across concurrent existing commitments.
5. Build recurring-bill suggestions from the existing recurrence evidence. CMA-paid bills stay in place by default under the user's card-fee preference. Each bill has a persistent Automatic / Keep current payment / Consider a credit card preference, editable before plan approval and carried across plans. An exception allows consideration, without claiming a fee is zero or increasing the spending forecast. Record card acceptance, processing fees, lost discounts and benefit checks before marking a move confirmed. Verify the first matching posted charge after confirmation. Keep future bill amounts inside the spending forecast rather than adding them twice.
6. Lead Cards with plan status, progress, next recommendation and the bill checklist. Put supporting wallet/history/comparison tools below. Reuse top-bar Actions for timely follow-ups; Today must never render action cards.
7. Routine tracking makes no model calls. Reuse Agent Hub offer research, expose automatic-research and reminder controls, default automatic research off, and restrict enabled research to approaching application decisions with a persisted cooldown that also covers failed attempts.

## Verification

Exercise arithmetic, refunds/pending separation, keeper reservations, unknown terms/history, competing bonuses, date windows, stale/concurrent approval, immutable terms, pause/resume, bill confirmation/observation and failed research cooldown through focused unit and real-Postgres tests. Check Cards and header Actions in the running browser, including failure/empty states and mobile layout. Run managed checks, rebuild, publish scoped changes and confirm CI. Leave the actual financial strategy awaiting user approval.


## Synced-account coverage correction

The user clarified that empty successful syncs must count as coverage throughout Portfolio AI. Shared account controls now expose completion evidence from Plaid transaction cursors and SnapTrade's paginated activity coverage. Account freshness, standalone portfolio accounts, household reviews, dashboard/Jenny freshness and header Actions consume this evidence. Balance-only refreshes, invalid responses and unfinished pagination cannot certify transaction coverage. Quiet months are observations, not proof of missing transactions. Actual last activity dates remain separate from coverage dates in Accounts. Successful empty SnapTrade results are complete, and both providers reject malformed or non-advancing activity pages.

Actions remain exclusively in the top navigation and are available across Money, Investing, Today and Status. Regression tests cover both navigation availability and the absence of action cards from Today.

## Current household proposal

A draft is saved for Mariana to consider Capital One Venture, with a modeled $4,000 requirement over 90 days and a suggested September 12–26 application window. The ledger-derived allowance is $1,820.86/month after keeper reservations, the additional Costco grocery shift and a 10% buffer. Existing Sapphire bonuses remain recorded as received. Public issuer terms were checked against the [Venture offer](https://www.capitalone.com/credit-cards/venture/) and [Autograph Journey offer](https://creditcards.wellsfargo.com/autograph-journey-visa-credit-card/). The Venture family exclusion covers a Venture or Venture X bonus within 48 months; personal eligibility and cash-flow approval remain user checks. Conditional travel credits are excluded from estimated net value. No actual financial strategy was approved or card account created by this implementation.

## Completion evidence

- Managed full gate: 2,815 backend tests and 564 frontend tests passed; Python/TypeScript checks, formatting and architecture checks passed.
- Focused real-Postgres strategy and term-review tests: 16 passed, including concurrent/stale approvals and immutable snapshots.
- Live Plaid sync: two Chase connections, three accounts; first refresh added four transactions and removed one, then a second refresh returned zero changes with no errors. Successful empty activity responses remain valid coverage.
- Runtime Cards, Accounts and header Actions checked; mobile Cards/popout at 390px had no page overflow. Today retained the header control and no action cards in its content.
- Ordinary tracking uses no model calls. Automatic research remains off. Saved proposal remains a draft awaiting household approval.
