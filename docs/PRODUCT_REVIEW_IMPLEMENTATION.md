# September 2026 product review implementation

The approved review concentrates Portfolio AI on a short household money review, evidence-based investment decisions, owner-aware retirement planning, and useful purchase savings. Existing specialist tools remain available in context.

## Implemented behavior

| Area | Result |
| --- | --- |
| Merchant identity | Generic bank prefixes cannot merge unrelated merchants. Controlled repairs preserve raw descriptions and manual classifications. Cash movements keep their source type. |
| Monthly Review | Money opens at Review. Current months and uncertain feed coverage use qualified language. Income and planned asset withdrawals remain distinct. Categories open the exact named-month included ledger slice; Back preserves context. Up to three agreed changes and later outcomes can be saved. |
| Cards | Issuer terms are sourced and staged for review. Actual card/bonus history and ordinary planned spending seed the model. Opening and renewal fees, retained cards, closure assumptions, credits and overlapping commitments use consistent baseline conventions. Spending requirements and awarded bonuses are separate states. |
| Retirement | Account owners and birth cohorts carry through shared deterministic and simulation withdrawal rules. Missing basis is disclosed with confirmation and sensitivity paths. The last completed result remains visible while an updated preview runs. |
| Investment performance | Returns use aligned account history and verified external flows. Insufficient coverage suppresses Sharpe. Benchmark context discloses its price-return basis. Unknown allocation exposure is not reported as a certain zero. |
| Today and navigation | A short ranked action queue leads Today and groups related evidence repairs. Secondary setup is expandable; unopened Money tabs do not fetch their full data. Navigation and long tab rails reserve space for utilities. |
| Intake | The queue includes pending decisions across older evidence. Exact source excerpts, receipt arithmetic, proposed updates and remaining questions appear together. Known duplicate and obsolete questions are filtered without editing stored answers. API/manual records do not pretend to have lost an uploaded file. |
| Family capture | Signed identity is verified by the backend. Children can only capture and review their own captures. Local drafts, retry, chat state and push subscriptions are scoped to the member. Contributor, purchaser, beneficiary and outcome are distinct. |
| Shopping pilot | A bounded staple set uses known units, equivalent packages, current confirmed offers, availability, coupons, fees and membership conditions. Recommendations use meaningful dollars. Old receipt prices are not current shopping-list offers; expired or withdrawn evidence invalidates saved estimates. Actual outcomes require evidence. |
| Investing decisions | Model drivers, missing evidence and review triggers replace repeated conclusions and unsupported style precision. Track requires rationale and retains server-captured evidence. Actions match whether the asset is held. Held positions link to recorded lots and basis coverage. |
| News | Company identity and explicit business relationships distinguish direct, peer and broad-market evidence. Unsupported associations are suppressed, including old cached articles. A labeled regression set covers observed false positives. |
| Jenny and assumptions | Chat receives the selected review month, canonical figures, funding explanation, live account scope and evidence links. Unsupplied browser scenario overrides remain unknown. Saved profile changes retain exact previous and new values atomically; the history is available in Assumptions. |
| Read performance | Rendering no longer triggers expensive household inference/registry/question writes. Small summaries, lazy queries and preview/action coalescing remove unnecessary work. Full portfolio history is not recomputed merely to get a total. Symbol reads use cached quotes and enrich only that symbol; explicit refresh remains available. Indexed report reconciliation preserves the exact survivors and exclusion reasons. Retirement waits for source defaults to settle before starting its first calculation. |

## Verification and limits

Regression tests cover the demonstrated financial defects, owner-specific rules, cash flows, missing evidence, package mismatches, role restrictions and failed draft uploads. Database tests use an isolated test database; they cover exact staged acceptance, deduplication, audit rollback and evidence revocation. Browser journeys use the managed browser, wait for usable content, and check named-month Review → Ledger → Back at 390px and 1280px, completed retirement/analysis results, and Track's required rationale.

The final managed checks passed 2,785 tests in the quick backend suite, all 547 frontend tests, and type, formatting and architecture checks. The full database integration and watchlist suite also passed all 411 tests. All 13 browser journeys passed, including exactly one initial retirement-preview request. The final local usable-content samples were 0.43–0.80 seconds for Review, 4.87 seconds for the first symbol decision, 6.98 seconds for Retirement, and 1.66 seconds for Analysis. Earlier samples before the final read optimizations were 14.29, 21.62 and 6.24 seconds for those last three views. These are single-run observations with varying cache state, not controlled performance guarantees.

An isolated comparison across 4,042 household report rows retained identical survivors and exclusion reasons while reducing reconciliation from 1.15 to 0.09 seconds. Simulation trial count and financial rules were unchanged by the performance optimization.

The labeled news cases are regression evidence, not a production precision estimate. Timing samples are observations, not latency percentiles. The specialist tax/backtest engines have not received blanket numerical certification.

Remote browser checks seed a clearly marked synthetic two-month household and a degraded macro snapshot in their isolated test database. Sign-in boundary tests mock the verification response and cover both rejection and an unavailable verifier. These tests do not depend on the local household or a running local backend.

Actual family-phone sign-in, native camera behavior and push delivery still require those devices. No live notification was sent by this review. The shopping pilot has no demonstrated realized savings until comparable purchases and outcomes are recorded. Missing basis, original offer terms and unknown purchase ownership are not filled with guesses.

## Current direction

Keep one Review, one investment decision history and the existing web-push channel. Do not revive the retired investment committee, expand unverified shopping recommendations, infer behavior from missing captures, or add dashboards to duplicate these jobs. The older card milestones are superseded by this implementation: their stale fees, direct catalog overwrites, quarter-only fee treatment and Telegram assumptions are not current requirements.
