# Money Workspace Revamp — Plan & Working Doc

**Status:** PHASES 0, 1 AND 2 COMPLETE — Phase 0's and Phase 1's exit tests both
pass (§7). Phase 0 landed 15 of 16 tasks; 0.13 (the staged receipts) waits on the
household's approval and on the Costco/Walmart order-page parser in Phase 4.2.
The review screen now answers the month in one place, and the screens that
answered it a second time are gone. **Phase 3 is live**: the income anchor (3.1)
is in, and the caps, savings state and sinking funds are priced off it.
**Owner:** Elias Leslie
**Started:** 2026-08-22
**Last updated:** 2026-08-24 (Phase 3: income anchored to the median of the last
three complete months, $6,067/mo; saving is a declared state; the four sinking
funds are priced from their own trailing spend and print their arithmetic)

> **Handoff contract:** this file is the single source of truth for the Money
> revamp. Anyone picking this up cold should read it top to bottom and be able to
> continue without re-deriving the audit. Update it at every phase change.
>
> **Visual proposal (approved shape):**
> https://claude.ai/code/artifact/c4239539-653c-4915-912e-3a3596382efe
> — IA before/after, the Review screen mockup on real July 2026 data, the Prices
> subsystem, and the tab disposition table.
>
> **Read order for a cold start:** §1 goal → §4 diagnosis → §7 the plan → §6
> decisions (D1–D23) for the *why* behind any phase → §3 findings for evidence.
>
> **§5 is empty by design** — every open question is resolved. Do not re-open
> them; start at Phase 0. **Nothing is waiting on the household.** Do not ask for
> a decision that §6 already records.
>
> **Pick up here — §2a "Next actions" is the live queue.** It names the next
> piece of work, in order, with the evidence behind each. Work the top item,
> update the §8 work log, then re-order the queue. **Phases 0, 1 and 2 are
> closed — Phase 0's and Phase 1's exit tests pass; Phase 3 is the live work.**

---

## 1. Goal (user's words)

> "I need to be able to sit down with my wife routinely and go over our budget
> easily without unnecessary complication. I want something that's streamlined
> and works very well and consistently."

Secondary asks:
- Full review of the Money section, especially **Dashboard, Budget, Purchases,
  Levers, Ledger** tabs.
- Identify what to **improve / fix / remove / consolidate**.
- Recommend the best way to **visualize** it.
- Fix the trust problem: "I don't really trust the data or processes yet."

**Success test (proposed):** Elias + Mariana sit down, open one screen, and
within 5 minutes agree on (a) what came in, (b) what went out, (c) whether the
month is OK, (d) the 1–3 things to change — with no number on screen that
contradicts another number on screen.

---

## 2a. Next actions (live queue — work top down)

**Phases 0, 1 and 2 are complete; Phase 0's and Phase 1's exit tests pass**
(Phase 0's table is at the end of §7's Phase 0 block; Phase 1's is at the end of
its own). **1.1–1.10 and 2.1–2.7 are all done.**

Work top down through §7 Phase 3 — plan, funds, and alerts:

1. **3.2 Income-anchored cap setup** (D6) — anchor (3.1, done) − savings (3.3,
   done) − sinking funds (3.4, done, **$1,349/mo**), distributed across
   categories by historical shape and adjusted in one pass. Re-propose on
   material drift. Every input it subtracts now exists.
2. **3.5 Card commitments in Plan** (P0-20) — annual-fee dates, welcome-bonus
   deadlines, balances owed; adding a card must be routine (D22).
3. **Carried in from Phase 0:** the API's `balance` field is `null` on every
   portfolio-origin account row while `current_value` carries the number. Pick
   one field.

**The review inbox is as clear as it can get without the household** — 17 → 12,
and each of the 12 is waiting on a person, not on a bug:
- **11 receipts** (7 Walmart order pages, 4 Costco) staged 2026-08-22, each with
  real proposed changes at 0.92–0.98 confidence. These are **0.13**, and they are
  held on purpose — the household asked that nothing be ingested until approved.
  The Walmart pages still need one dated transaction per order before their spend
  can be trusted (see P0-27); the Costco parser is Phase 4.2.
- **`image.png`** — brokerage screenshot staged in March. Its file is gone from
  disk and nothing from it ever applied, so it genuinely needs a re-upload. It
  now says that instead of the generic review failure (P0-31).

**Still open for the household** (surfaced in the money inbox, blocking nothing):
- What is the **·4635 card**? Five Walmart receipts name it and no account
  matches. Answering it links those rows to a real account (P0-30).
- Who owns each of the two **Fidelity 529s** (·6273 and ·6277)?

**Recently cleared** (kept for a few sessions so a cold start can see the arc):
- 3.4 **The four sinking funds are priced from their own trailing spend**, each
  printing its arithmetic: Travel **$815/mo** ($9,785 over 12 months), Home
  repair **$291**, Insurance/taxes/registration **$243**, and Gifts & holidays
  **undeclared** — nothing in the ledger is filed as gifts, so it asks instead
  of reporting $0. The largest purchase in each window can be set aside as
  one-time (Travel drops to $639 without the $2,111 cruise). The property tax
  is filed under Home and is counted as a *tax*, not a repair.
- 3.3 **Saving is a declared state, not a $0 target reporting success.** Four
  states: *active* (says what the amount leaves of the anchor, never a
  compliance grade), *paused* (dated, with a reason and the income level that
  ends it), *time to resume* (the anchor has reached that level), and *not
  decided* — which is what the live profile is, because a $0 target is not a
  plan. The restart trigger reads the same anchor 3.1 built, so the pause and
  the screen cannot disagree about income.
- 3.1 **The income anchor is the median of the last three complete months**:
  **$6,067/mo** from May ($6,067), June ($7,985) and July ($2,804), with the
  months listed so the arithmetic can be checked. The saved take-home target of
  $6,283 is shown beside it, $216 above what actually arrives. A declared
  anchor is dated and outranks the median without replacing it on screen.
  **P1-37**: the $506.31/mo note income (P0-23) stopped on 2026-03-02 and its
  rows are `transfer_in`, not income, so it could not have reached the anchor
  even if it had continued.
- 2.7 **The second copies are gone.** The Decision Board is deleted: its Free to
  spend card was the same figure 2.5 had already put on the review screen, and
  its watch list re-printed the pace sentence sitting three inches above it. The
  allocation donut moved to Investing → Holdings, where "where do the assets
  sit" is the question being asked. The budget stat row went **ten tiles → 3**.
  The one thing the board carried that nothing else did — the refresh inbox,
  capped at 2 items — is now its own card showing **all 5**.
- 2.6 **The retirement block asks the question its phase calls for**, and asking
  it surfaced that the plan's retirement age of 49 arrived this January. It now
  reads: spending runs $10,231/mo against the $6,428/mo that $1,542,811 supports
  at the household's own 5% rule; the plan assumes $7,500/mo. It also refuses to
  call that a withdrawal verdict, because no account in the ledger is labelled
  as a retirement account and a drawdown that cannot be seen cannot be graded.
- 2.5 **Free to spend** is on the review screen, as the subtraction rather than
  a lone figure: $30,495 − $88 − $1,129 − $17,336 = **$11,941**. The word over
  it (`estimate`/`tight`/`hold`) is now the server's, not a `< 150` threshold
  living in a React hook, and the stale-data line names the input that is behind
  instead of saying "stale account data".
- 2.4 **New this month** groups July's 34 first-time merchants into two outings
  and two loners, instead of 34 unfamiliar names that read like a fraud report.
- 2.3 **What changed** answers D2's third sentence: July spent $3,004 more than
  June *and* July's everyday spending was $8,629 less, both stated, with the
  movers attributed by category and a toggle that sets the one-time purchases
  aside on both sides.
- 2.1/2.2 the Budget screen answers D2's first two sentences: a verdict line at
  the top, and category rows judged on the month with the over/under netting to
  one total. P1-36 fell out of building it — purchase items kept their own
  essentiality classifier, so Household arrived as two rows.
- P0-35 the reversal netting that never once ran on live data: the July Pinellas
  clawback was filtered out of the candidate set before pairing could see it, so
  income carried a $1,102.23 paycheque that was taken back the next day.
- P0-34 the Ledger and the spend totals disagreed by $71.03 on July because the
  Ledger collapsed transactions against imported receipt lines and the totals do
  not. Both now report 112 rows and $16,708.01.
- P1-13 `visibility_score: 99` is gone. **What we can see** scores four
  components — balances by money, spending feeds by account, connections and
  classification — and a component reads 100 only when nothing about it is
  wrong (1.9).
- P1-8 needs/wants adds up: the **mixed** bucket is named and shown, so the three
  shares exhaust the spend instead of two of them silently not summing to 100%
  (1.10).
- P0-4 the three vacuous verdicts are gone: the budget snapshot says
  `plan_incomplete` and names the missing target, the Lifestyle lane says
  "Inferred from spending" instead of "Configured", and the retirement tracker
  stops passing a $0 target against $0 contributions (1.5).
- P0-2 Safe to Spend is now **Free to spend**, and it is cash minus what is owed:
  $30,494.75 − $88.38 bills − $1,290.32 essentials still to come − $17,287.71 on
  cards = **$11,828.34**. The card shows the subtraction, names what it could not
  count, and the green "Safe" badge is gone (1.4).
- P0-3 the recurring detector is rebuilt: the list is now Frontier, Duke Energy,
  T-Mobile, Waste Pro, P C Utilities, the declared HOA, then four subscriptions.
  Airbnb, Avis, Lufthansa and Costco are gone (1.3).
- P0-1 one canonical spend definition, complete calendar months only, sliding
  chips retired (1.1) and the Pinellas reversal netted out (1.2) — `8e70c8136`.
- P1-12 statement merchants normalise: "DIRECT DEBIT DUKEENERGY BILL PAY (Cash)"
  is Duke Energy, and the three spellings of Frontier are one merchant
  (`efc4ca2fb`). This was half of P0-3 — a bill split across three spellings
  never accumulates enough sightings to prove a cadence.
- P0-33 two rollover IRAs both named "Rollover IRA" are now ·2283 and ·8698,
  and the mask fallback closes that class for good (`e497b3e9b`).
- P0-32 a document proposing zero changes no longer waits for an approval the
  system itself refuses (`6eabc9379`).
- P0-31 four applied Wells Fargo statements left the queue after five months of
  telling the household to re-upload files that no longer exist (`f9461b85b`).
- P0-27 receipt dating — four mis-dated rows retired, silent drop is now a hold
  (`c231a3b4b`).
- 0.3 identity override reaches every read path — the ledger filter offers 8
  accounts, not 10 (`3391408e4`).
- 0.14 receipt↔card-feed reconciliation — 6 receipts / $677.20 retired against
  7 charges, line items carried to the surviving charge (`b5094ec5a`).

**Known-but-deliberately-deferred** (do not treat as bugs to fix on sight):
- Purchase items cannot span charges, so a split order keeps its line items on
  the retired receipt rather than restating their prices against one leg
  (0.14). Phase 4.

---

## 2. What exists today

Route: `frontend/app/money/page.tsx` — 9 tabs in one `WorkspaceTabs`.

| Tab | value | Panel | LOC |
|---|---|---|---|
| Dashboard | `dashboard` | `MoneyOverviewPanel` | 7.2k |
| Budget | `spending` | `MoneyBudgetPanel` | 14.6k |
| Purchases | `purchases` | `MoneyPurchasesPanel` | 8.7k |
| Levers | `levers` | `MoneyLeversPanel` | 20.6k |
| Cards | `cards` | `MoneyCardsPanel` | 5.2k |
| Retirement | `retirement` | `MoneyRetirementPanel` | **201k** |
| Accounts | `accounts` | `MoneyAccountsPanel` | 6.9k |
| Ledger | `ledger` | `MoneyLedgerPanel` | 11.8k |
| Intake & Review | `intake` | `HouseholdDocumentCenter` + `JennyQuestionInbox` | — |

`frontend/components/money/` holds **80 files**. Backend household services:
**~36k LOC across 60+ modules**.

Rendered page heights (1280px viewport, live data):
Dashboard 2469px · Budget 4595px · Levers 4617px · Purchases 4588px · Ledger 1129px.

### Live data state (2026-08-22)

- 2,723 household transactions; **1,722 flagged `removed`** (63%).
- Date range 2025-08-27 → 2026-08-20; usable spend coverage really starts 2025-12.
- 25 household accounts, but only **2 spending accounts covered** in the current month.
- 19 `category_budget:*` facts exist; **only 2 carry a real `monthlyTarget`**
  (Gas $375, Groceries $1,525). The other 17 are `monthlyTarget: null`.
- 2,194 products / 3,067 purchase items / 462 merchants / 74 documents.
- 0 open clarification questions.

---

## 3. Audit findings

Severity: **P0** = actively misleading a real financial decision · **P1** =
blocks the "sit down together" workflow · **P2** = clutter / cost / polish.

### P0-1 — The same question gets four different answers depending on a chip

`GET /api/household/spending` per window:

| Window | Avg monthly spend | Avg monthly income | Net cash flow | Savings rate | Accounts |
|---|---|---|---|---|---|
| 1M | $7,421 | $3,300 | **−$4,121** | **−125%** | 2 |
| 3M | $9,378 | $5,842 | **−$10,609** | **−61%** | 2 |
| 6M | $8,041 | $5,588 | **−$14,713** | **−44%** | 5 |
| 12M | $5,184 | $5,415 | **+$2,763** | **+4%** | 7 |

Dashboard reports a fifth number: `average_monthly_spend = $8,103`.

Root cause: each window divides by its own coverage months while including a
different account set. The 12M window captures old statement-CSV *income* but
almost no matching *spend* (Aug–Oct 2025 has 3 transactions total), so it
manufactures a positive savings rate. **A couple flipping 3M→12M goes from
"we're bleeding $3.5k/month" to "we're saving 4%."** This alone destroys trust.

### P0-2 — "Safe to Spend" is not safe, and not spendable

Dashboard shows **Safe to Spend $1,283**, badge **"Safe"** (green).
`budget_snapshot.safe_to_spend_constraint = "plan_residual"`, i.e.
`monthly_income_target (6,283) − monthly_plan_total (5,000)`. It is arithmetic
on two assumptions. It ignores that `actual_monthly_spend = $8,103`.

The card itself admits it: *"Limited by income minus your monthly plan (a
target, not cash on hand)."* A green "Safe" badge on a number the UI
simultaneously disclaims is the single most dangerous element on the page.

**RESOLVED in 1.4.** The figure is now arithmetic on money only, and the card
shows the whole subtraction so it can be checked rather than trusted:

```
cash on hand                            30,494.75
less bills due through Sep 6                88.38
less essentials still to come            1,290.32
less owed on cards                      17,287.71
less committed to sinking funds               0.00   (not yet counted)
                                        ---------
free to spend                           11,828.34
```

Four decisions worth recording. The **horizon** is the rest of the calendar
month *or* the next fortnight, whichever reaches further — ask on the 30th and a
pure month frame would show next week's bills as invisible. **Essentials still to
come** is the larger of what is left of the baseline and the remaining days
charged at the baseline's own daily rate; August's $5,000 was already spent by
the 23rd, and answering "nothing left to buy" with eight days of groceries ahead
would be false. The result is **not floored at zero** — a household that cannot
cover what it owes needs the size of the hole, not a $0 that reads as "spend
nothing more". And inputs the system does not have are **named** rather than
treated as zero: sinking-fund balances have no home yet (D7 is Phase 3), so the
card says so.

`plan_residual` and `discretionary_cap` are gone as constraints; the only one
left is `cash_after_commitments`. The green **Safe** badge is retired — the
status can be `estimate`, `tight`, `hold` or `review`, and never approves.

### P0-3 — Recurring bills detector is inverted (0% precision, ~0% recall)

`recurring_commitments` returns exactly 4 items, all wrong:

| Merchant | Cadence claimed | Avg | Annualized | Status |
|---|---|---|---|---|
| Airbnb | likely weekly | $766 | **$39,833** | overdue (−46d) |
| Avis | likely weekly | $343 | $17,857 | overdue (−41d) |
| Lufthansa | likely bi-weekly | $566 | $14,715 | overdue (−6d) |
| Costco | likely weekly | $247 | $12,845 | overdue (−27d) |

All four are **one vacation**, typed as `commitment_type: "bill"`, annualized to
**$85,250/yr of phantom bills**.

Meanwhile the household's *actual* metronomic bills are in the data and are
completely missed: Duke Energy (monthly), T-Mobile (monthly ~15th), Frontier
($34.99 monthly), P C Utilities, Waste Pro.

This feeds `due_soon_bills_total = $1,922`, which is displayed as *"$1,922 of
recurring bills are due inside 14 days"* — every one of them is in the past —
and is an input to the Safe-to-Spend cash constraint.

**RESOLVED in 1.3.** Three things were wrong and each had to be fixed
separately. The *evidence bar* was two sightings, which describes one gap, and
one gap cannot tell a monthly bill from two unrelated purchases five weeks
apart. The *ranking* was `ORDER BY average_amount DESC`, so merchants were sorted
by size before anything asked whether they recurred — which is precisely how a
vacation reached the top of a list of bills. And nothing tested *amount
stability*, so Lufthansa's $90 / $91 / $1,041 read as a cadence.

`_household_recurrence.py` now requires three distinct sightings, a median gap
that lands in a named cadence, an observed span of 55+ days across 3+ calendar
months, and 70% of both the gaps and the amounts within 35% of the merchant's own
median. Same-day duplicate rows collapse to the day's largest charge rather than
summing (Duke Energy has two rows dated 2026-01-07). A series last seen two full
cycles ago is dropped rather than reported as overdue: a monthly bill last seen
in June is not "late by fifty days", it is a series that ended.

Each of the four false positives now fails for its own reason, and the reasons
are worth keeping: **Airbnb** kept a *perfect* weekly cadence — but for fourteen
days inside a single month, so only the span bar catches it; **Avis** was seen
once; **Lufthansa** ranged $90–$1,041; **Costco** was neither regular nor stable.
All five real bills are detected, and P C Utilities is filed **bimonthly** on its
true 61-day cycle rather than rounded to quarterly, which would have set its
sinking fund a third short.

Separately, `commitment_type` is now decided by category — travel, retail,
groceries and fuel become `recurring_purchase`, never `bill` — and only bills and
subscriptions count toward `due_soon_bills_total` or get a sinking fund. The
totalling also stopped reading a truncated list: cutting to the top six before
summing meant the subscriptions that sorted below the utilities were simply
missing from "due inside 14 days".

### P0-4 — Headline verdicts contradict the arithmetic under them

`budget_snapshot`: `status: "on_track"`, summary *"The current monthly spending
profile is inside the available budget guardrails."*
Same object: `actual_monthly_spend 8,103` vs `monthly_plan_total 5,000` vs
`monthly_income_target 6,283`. Also `pace_status: "partial_plan"` — two
different verdicts in one payload.

`budget_readiness`: `status: "ready_for_budgeting"`, all three lanes
("Essentials", "Lifestyle", "Savings") reported **"Configured"** — while 17 of
19 categories have no cap at all.

**RESOLVED in 1.5.** Three separate vacuous verdicts, one cause: `on_track` and
`Configured` were both fall-through values, reached by *not* failing a check
rather than by passing one.

`budget_snapshot.status` no longer falls through. A partial plan now returns
`plan_incomplete` and says what is missing — *"No verdict yet: the monthly plan
has no discretionary target, so total spending of $10,085/mo cannot be judged
against it"* — and a complete plan that the total still overruns returns
`above_plan`, because the lanes do not have to add up to the plan and each one
can sit under its cap while the total misses. `on_track` is now only reachable
when a complete plan exists and the spending actually fits inside it.

`budget_readiness` distinguishes a target the household **set** from one the
system **inferred**. The Lifestyle lane read "Configured" off an inferred
$4,073.26, which is simply the discretionary spending the household already
does, handed back as a cap. It now reads **"Inferred from spending"**, the status
is `partially_configured`, and the summary names the lane. The lane label is
tinted by state rather than always rendering in the primary colour.

`retirement_contribution_tracker` stops reporting `on_track` from a $0 target
against $0 contributions. A zero target is either unset or a decision the system
cannot record yet — D17 makes `paused` a first-class state in Phase 3 — and
until then the tracker says *"there is nothing to measure contributions
against"* rather than passing.

### P0-5 — Ledger totals and Budget totals differ by ~4x with no reconciliation

Ledger "All dates": **Debits $319,381 · Credits $193,797 · Net debit $125,584**.
Budget 6M: total spend $48,243 · income $33,530.
Ledger 6M alone: debits $180,341 / credits $107,568.

Ledger sums raw direction including inter-account transfers, brokerage buys and
card payments; Budget applies spend filters. Both render as large currency in
the same visual idiom, on adjacent tabs, with no bridge. "Net debit $125,584"
reads as a household loss.

### P1-6 — Spend exclusions are invisible, hardcoded and unappealable

`backend/app/services/_household_spend_filters.py` silently drops rows matching
a literal string list: `"zelle to"`, `"zelle from"`, `"atm withdrawal"`,
`"payroll"`, `"ui benefit"`, `"online transfer"`, `"moneyline"`, … plus
categories `{transfers, income, cash, debt payments}`.

Zelle to a tutor, or an ATM withdrawal that became groceries, is real spend and
vanishes with no UI affordance to see or override it. 138 of 996 ledger rows
are "excluded" with no roll-up of what that cost.

**RESOLVED in 1.7.** Three separate things were missing and only one of them was
the string list. There was **no total** -- nothing anywhere said what exclusion
cost. There was **no reason a person could read** -- the ledger said
`cash_movement`, which names a category of decision rather than the decision.
And there was **no way to disagree**, which is what made the other two matter:
a number you cannot check and cannot appeal has to be trusted rather than
believed.

`spend_exclusions` on the dashboard now publishes the counterpart to every spend
total: how many rows were held out, what they came to, grouped by the rule that
held them, with the merchants under each rule named. Live it reads **139 of
1,000 rows ($448,762)** -- which is the finding's own "138 of 996", arrived at
independently.

Getting that number right required widening the scope past the ticket. Rolling
up only the literal string list gave **11 rows**, because most exclusions never
reach the string list at all -- they are dropped earlier for flow type. Eleven
would have answered "why is this Zelle payment missing?" while leaving "why is
my spend total smaller than my transactions?" unanswered, and the second
question is the one a person actually arrives with. Every reason a row leaves a
total is now reported: flow type, non-positive amount, category, and the string
patterns.

The appeal is a nullable `spend_override` column (migration `b2c3d4e5f6a7`),
three-valued on purpose -- `include` restores a dropped row, `exclude` drops a
counted one, and clearing it hands the row back to the rules, because an appeal
that cannot be withdrawn is a worse trap than the filter it corrects. It is a
column rather than a metadata key because the spend predicate is built in SQL
and evaluated in several queries; an override invisible to SQL would apply on
the Ledger and not on the Dashboard, which is the exact defect class Phase 1
exists to remove. `non_spend_sql_predicate` therefore applies it centrally
rather than leaving each query to remember.

Only rules that match on **wording** invite an appeal (`zelle to`, `atm
withdrawal`, `online transfer`, `inst xfer`, category `cash`). A row excluded
because it is income or a transfer is not a filter's guess about a string, and
offering to overrule it would be offering the wrong argument.

Verified live end to end: appealing the $400 ATM withdrawal of 2026-03-16 moved
the roll-up to **138 rows / $448,362** -- exactly $400 -- reported it as *"1
restored, $400.00"* under Cash withdrawals, and flipped the row's own SQL
verdict from dropped to counted. Withdrawing the appeal restored 139 /
$448,762. The test override was withdrawn; live data is as it was found.

One presentation defect surfaced during verification and was fixed in the same
task: "income" is reachable both as a flow type and as a category, so the card
listed **"Money coming in" twice** -- the doubled legend of P1-7, reproduced one
surface over. Rules are now grouped by what they mean rather than by which rule
matched, and transfer in/out share one line, because the card answers "why is
this not in my spend total?" and direction adds a row without adding a decision.

### P1-7 — Category taxonomy is doubled and polluted

Live category legend on the Budget tab shows **"Transportation" twice** and
**"Household" twice** — series are keyed `category + essentiality`, and the same
category carries different essentiality across rows (Travel: discretionary *and*
mixed; Transportation: essential *and* discretionary; Household: mixed *and*
discretionary).

Raw Plaid taxonomy leaks in beside the curated set: **"General Services
Storage"**, **"General Services Insurance"** sit next to "Insurance" and "Bills".

Consequence: needs/wants is unstable, and the same dollar can move between
"needs" and "wants" with no user action.

**RESOLVED in 1.6.** The root cause was that essentiality was a *second free
field* stored next to the category, so nothing forced two "Transportation" rows
to agree — whichever classifier wrote a row decided its essentiality
independently, and the legend faithfully drew both answers.

`_household_taxonomy.py` makes essentiality a **function of the category**, not a
field beside it. `CATEGORY_ESSENTIALITY` names one reading for each of the 23
curated categories, `essentiality_for()` is the only way to get one, and every
classifier path — `_classification_for_flow`, `_canonical_category_from_taxonomy`,
`_effective_transaction_classification`, and Plaid's `_transaction_category` —
now routes through it. A category the household invented ("Girls") is kept as
written and gets a stable `mixed`; only a recognised alias or a SCREAMING_SNAKE
Plaid enum is rewritten, so the fix cannot quietly flatten a real label.

Two of the four doubled series were doubled by a single row each. **Home** held
a $2,144.48 Pinellas County property tax and an HOA payment; those were its only
"essential" rows and they are what dragged the category between needs and wants
depending which row was read. `BILL_CONCEPTS` re-homes property tax and HOA dues
to **Bills**, after which Home is honestly discretionary. Plaid leakage is
mapped rather than displayed: "General Services Insurance" → Insurance, "General
Services Storage" → Household, "Bank Fees Other Bank Fees" → Bills, with prefix
rules covering the rest of the enum space.

Existing rows are repaired in place by `_canonicalize_stored_essentiality`,
running inside `repair_transaction_system` and reporting `essentiality_aligned`.
It rewrites *only* essentiality, keyed by distinct category, so it can never move
a transaction between categories on a re-run.

Live: the census is **23 categories in 23 rows** — one essentiality each, no
Plaid labels left — a second repair pass reports `essentiality_aligned = 0`, and
`reports.category_breakdown` returns six rows with no duplicate category. Note
that Household, at 24.6% of spend, is the largest single series and is `mixed`;
that is exactly the bucket 1.10 has to make visible.

One row is knowingly left alone: the Harbor Hills HOA charge does not match by
name and stays in Household/mixed until P2-26 re-homes it.

### P1-8 — Needs/wants split doesn't add up

Decision Board: **$3,217 / $4,074**, badge *"Wants leading 50%"*, body *"(50% vs
40%)"*. 3,217 + 4,074 = 7,292, but average monthly spend is 8,103 — the $811
`mixed` bucket is invisible, so the two shares sum to 90% and the card labels
itself "Want vs need" while displaying needs first.

**RESOLVED in 1.10.** The `mixed` bucket was computed nowhere and displayed
nowhere: the executive report summed `essential` and `discretionary` and simply
never asked what the remainder was. `average_monthly_mixed` is now published,
and taken as **the remainder** rather than as a third sum over a third label —
so a category carrying some unforeseen essentiality shows up as unclassified
instead of vanishing from the split, which is the failure mode being fixed.

Task 1.6 made this larger rather than smaller. With Household given one honest
`mixed` reading it is the household's biggest single category, so live the split
is **needs $3,154 (30.8%) / wants $4,253 (41.6%) / mixed $2,823 (27.6%)**,
summing to exactly $10,230.57 and 100.0%. The invisible slice was a quarter of
the money, not the $811 tail this finding describes.

The card is renamed **"Needs, wants and mixed"** — it displayed needs first while
calling itself "Want vs need" — shows all three amounts and all three shares, and
says what mixed means: *a Household or Cash row can be a repair or a treat*.

### P1-9 — Signal quality: a vitamin bottle is presented as a budget driver

Decision Board, verbatim: *"Now Foods Supplements, Zinc (Zinc Gluconate) 50 mg,
Supports Enzyme Functions, Immune Support, 100 Tablets, Yellow/Gold is
pressuring the budget via unit price up."* — next to $7,094 of month-to-date
spend. No materiality threshold; full Amazon SEO titles used as headlines.

### P1-10 — Levers costs more than it returns

Levers headline: **"Additive trim $262/mo"** against $9,378/mo spend and
−$10,609 3M net cash flow. That is ~2.8% of spend, from a 4,617px page with 5
lanes, a price-check runner, trendlines, Category Pressure and Merchant Drag
tables, ~1,000 LOC of frontend and a dedicated backend price-check service.

"Last price check 6/19/2026 · `completed_with_errors` · 2 quotes · 0 findings" —
two months stale, errored, zero output, raw enum shown to the user.

Lane contents are Amazon product titles (bone broth powder, magnesium,
toothpaste), not household budget levers.

### P1-11 — Ledger row = data-repair console, not a review surface

Every row carries: category combobox + "Merchant rule" checkbox + essentiality
+ Owner combobox + "Merchant owner rule" checkbox + status badge + evidence
chip + Audit toggle + source line. Plus 5 filter controls and a 5-tile summary
above. This is an admin tool. It is the correct tool for *fixing* data and the
wrong one for *reviewing* money.

### P1-12 — Merchant names are half-clean

Plaid rows normalize ("Get Fitness"). Statement rows do not: *"DIRECT DEBIT
DUKEENERGY BILL PAY (Cash)"*, *"DIRECT DEBIT PINELLAS COUNTREVERSAL (Cash)"*,
*"Check Paid # 1002 (Cash)"* ($3,606 — very likely housing, opaque).
Merchant Drag / merchant aggregation therefore treat one biller as several.

### P1-13 — "Strong household visibility 99%" while covering 2 spending accounts

`overview.visibility_score = 99`, label *"Strong household visibility"*, while
`monthly_spend_detail` says *"reflects 2 covered spending accounts"* and
`net_worth_status = "stale"` with 2 accounts needing refresh. The confidence
signal is anti-correlated with actual coverage.

**RESOLVED in 1.9.** The score was anti-correlated because it was never a
coverage measure. It was a **setup checklist**: 10 points for having told the
system an income target, 5 for a retirement age, 10 for owning taxable assets.
80 of its 100 points were reachable without a single account being current, so
answering questions raised "visibility" while the accounts behind the numbers
went stale.

`_household_coverage.py` measures observable facts instead, in four published
components:

| Component | Weight | What it observes |
|---|---|---|
| Balances current | 30 | Share of tracked asset **value** in accounts whose balance is fresh |
| Spending feeds reporting | 30 | Share of `spend_driver` accounts still delivering transactions |
| Known accounts connected | 20 | Connected accounts against connected + discovered-but-unlinked |
| Spend classified | 20 | Share of expense rows carrying a category |

Two of the weightings are deliberate opposites. Balances are weighted **by
money**, because a $572,782 brokerage going stale and a $0 rollover going stale
are not the same event and counting accounts would call them equal. Spending
feeds are weighted **by account**, because weighting those by balance would rank
a card by what is owed on it rather than by how much spending flows through it —
a paid-off card can still be the one the household actually uses.

A component only reads 100 when nothing about it is wrong. Money-weighting alone
rounded $6,793 of stale balances against $1.56M to 100%, which would have printed
a perfect score directly above a line naming two stale accounts — the same
anti-correlation one level down. Small is not absent.

Live the score is **91, "Strong coverage"**, and every component states its own
evidence: balances 99 (*2 of 15 accounts are stale, holding $6,793 of
$1,561,142*), spending feeds 75 (*1 of 4 spending accounts has gone quiet — Chase
Sapphire Preferred ·8054*), connected accounts 94 (*Visa Credit ****4635 is not
connected*), spend classified 100 (*all 641 rows carry a category*). The summary
names the **weakest component rather than the score**, because "91%" tells nobody
what to do and "a spending account has gone quiet" does.

The old checklist scorer, its label function and the freshness cap that existed
to stop it claiming strength over stale accounts are **deleted**, not left
beside the new one. The card — *"What we can see"* — publishes the components,
for the same reason the spend exclusions publish their roll-up: a single figure
that cannot be broken down is exactly how "99% visibility" survived beside a
stale net worth for as long as it did.

### P2-14 — Account registry has duplicates and test junk

`household_accounts` (25 rows) contains: **"Wells Fargo checking activity
export" twice**, **"FRS Investment Plan" twice**, a **"Codex archive smoke"**
test account, and three overlapping Wells Fargo checking identities ("LESLIE E
EVERYDAY CHECKING" *7312, "Wells Fargo Everyday Checking" *4222, "Wells Fargo
closed checking"). Two 529s are filed under `asset_group: taxable`.
Likely a direct cause of the 63% `removed` transaction rate.

### P2-15 — Dashboard carries investment allocation that belongs in Investing

Account Allocation donut ($905k retirement / $636k taxable / $6.8k education)
occupies prime dashboard real estate on a page whose job is household cash flow,
and duplicates `/portfolio`.

### P2-16 — Tile inflation

Budget tab opens with **10 stat tiles**; 5 of them describe the app's own state
("Suggested cap total", "Confirmed cap total", "Budgeted categories", "Over
budget", "Unknown purchases") rather than the household's money.
Levers opens with 5 more. Ledger 5 more. Dashboard 3 + 4 decision cards.

### P2-17 — Purchases' flagship feature is empty

"Buy Guide → No buy-size gaps yet" despite 483 products with package-unit data
and 2,194 products total. Product Catalog is a 2,194-row browsable table with no
stated connection to the budget.

### P2-18 — Stale cross-references and dead code

- Levers: *"Same canonical spend math as the Spending tab"* — tab is now labelled
  "Budget" (value is still `spending`).
- Levers: a whole SectionCard whose only content is "Price Signals moved to
  Purchases" + a link.
- `PrimaryTilesGrid` lives in `components/home/today/` but is now used **only**
  by Money, and only with `hideSpendPace`, so the Spend Pace tile is dead.
- Tab value/label mismatch (`spending`→"Budget") forces URL rewrite shims in
  `page.tsx` for legacy `?tab=review` / `?utility=evidence`.

---

### P0-21 — Only two accounts have a live feed; everything else is a dead upload

```
source_system         count    last transaction
plaid                   867    2026-08-20   <- live  (Prime Visa)
snaptrade                46    2026-08-20   <- live  (Fidelity CMA Joint WROS)
statement_csv          1570    2026-05-08   <- one-time file, stopped
statement_activity      185    2026-04-10   <- one-time file, stopped
bank_statement           41    2026-02-27   <- one-time file, stopped
```

This is the **root cause of P0-1**. The 12M window blends a live card feed with
checking uploads that died in February, so it reports income without the
matching spend and manufactures a +4% savings rate. Every window comparison is
invalid until coverage is uniform.

Not a defect on its own: the Wells Fargo accounts were **closed** (D22) and the
household consolidated onto the Fidelity CMA. The defect is that the app still
counts the dead accounts inside rolling windows as if they were live.

### P0-22 — The same insurance premium is booked as income and as expense

```
2026-02-17  PROG SELECT INS  INS PREM ... Elias Elias Leslie   276.99  flow_type=income   Wells Fargo closed checking
2026-02-17  Prog Select Ins Ins Prem ... Elias Elias Leslie    276.99  flow_type=expense  Wells Fargo Everyday Checking
```

One Progressive payment, ingested twice from two statement files under two
account labels, with **opposite flow types**, both `removed=false`. A $554 swing
on a single premium. The casing differs, so text-based dedup missed it.

### P0-23 — The spend filters delete real recurring income

The household **receives** $506.31/mo on a seller-financed note:

```
Zelle From Michael Wiley ... "13th Mortgage Payment on The Property at 8..."   506.31
RECURRING TRANSFER ... "MORTGAGE PAYMENT FROM MIKE"                            506.31
```

Both descriptions match `_household_spend_filters.py` patterns (`"zelle from"`,
`"recurring transfer"`), so the payments are dropped before any total is
computed. The filters were written to remove transfers; they are also removing
**income**. Compounding it, each month appears twice (once per account label),
both `removed=false`.

Payments stop after 2026-03-02 because the receiving account closed — either
they now land somewhere untracked or the note ended. Needs confirmation.

### P1-24 — 19 account labels for roughly 7 real accounts

`Cash Management (Joint WROS)` / `Cash Management Account (CMA)` /
`Cash Management account (CMA)` are one account. So are
`Chase Visa ending 9728` / `Visa credit 9728` / `CHASEVISA-9728`, and
`Visa Credit ****4635` / `Visa credit ending 4635` / `Visa ending 4635`.
`Chase Amazon card` and `Prime Visa` are the **same physical card** (D22).

Account-level filtering, per-account coverage checks and the ledger's account
chip are all unreliable until labels resolve to `household_accounts` rows.

### P1-25 — The ledger cannot be searched by amount

`backend/app/services/household_ledger_service.py:135-151` defines
`_LEDGER_SEARCH_FIELDS` with 16 fields — `account_label`, `merchant`,
`description`, `category`, `essentiality`, `owner_name`, `owner_source`,
`source_document_filename`, `source_document_id`, `external_row_id`,
`source_type`, `document_type`, `flow_type`, `exclusion_reason`, `row_hash`.

**`amount` is absent.** Searching `2144.48` returns nothing, which is exactly
how the user tried to locate a known property-tax payment and concluded the data
was missing. The frontend placeholder is honest about it
(`MoneyLedgerPanel.tsx:277`, "Search merchant, account, category, or evidence")
but the omission makes the ledger unusable for the most natural lookup a person
performs. Fix is additive: match a numeric query against `amount`.

### P2-26 — The HOA charge is duplicated six times and miscategorized

`HARBOR HILLS PROPERTY` $104.13 appears **6 times** for February 2026 — five
`removed=true`, one live. The live row is categorized `Subscriptions`; the
removed ones say `Household`. It is an HOA fee and belongs in housing. Only
February exists despite continuous card coverage every month since 2025-12,
so either the charge is not monthly or later months were dropped.

---

### P0-27 — Four receipt rows were dated to the day their file was read, and one was two orders added together

**[fixed — data retired; the silent path closed]**

Reconciling receipts against the card feed (0.14) exposed four rows whose
`transaction_date` equalled their document's **upload date** while their own
summaries named a different month:

- `$313.20` dated 2026-06-13 — *"two grocery orders (May 20, 2026 and May 26,
  2026)"*. The feed has `$174.98` on 2026-05-22 and `$138.22` on 2026-05-28.
  **$174.98 + $138.22 = $313.20.** One row stood for two orders five weeks
  earlier, and its $138.22 leg was already counted from the feed.
- `$162.23` dated 2026-06-13 — *"two Walmart grocery receipts from May 2026"*.
- `$170.81` dated 2026-06-13 — a single order; the feed carries exactly $170.81
  on 2026-06-04.
- `$133.70` dated 2026-08-22 — *"purchases dated 2026-08-10"*.

**The current parser no longer produces these.** Replaying the $313.20
document's structured data through `extract_transactions` today yields **zero**
transactions: the review returned two orders with 19 and 27 line items, all with
`date`, `amount` and `merchant` null, so structured extraction skips them and
the summary fallback finds no date either. The rows are residue from an older
path.

But zero was its own defect — **silence**. A receipt naming a merchant, a total
and two orders produced no spend, no warning, and a document reported as applied
while none of its money was recorded. Guessing a date is worse (that is what
made these four wrong), so the receipt is now **held**: the reason is written to
the document's `date_quality_summary` alongside the future-dated holds, and a
`household_receipt_held_without_a_date` warning is logged. The held reason reads
*"The receipt describes 2 orders, and 2 of them carry no purchase date. Booking
them on the day the file was read would put the spend in the wrong month."*

The four stale rows are retired — `removed = TRUE` with
`metadata.date_quality.reason = "dated_to_the_day_the_file_was_read"`, never
deleted, and their documents stay in the queue to be re-read. Live receipt rows:
15 → 5, and every one of the 5 is genuinely pre-feed or genuinely unmatched.

**Remaining, and it belongs with the Costco parser in Phase 4.2 (0.13):** teach
the review to read `"May 20, 2026 order"` off a Walmart order page and emit one
dated transaction per order. Until then those receipts hold instead of lying.

### P0-28 — An annual bill could not be a recurring commitment at any confidence

Confirming the HOA cadence exposed that `annual` was not a cadence the system
had. `_RECURRING_CADENCES` was `{monthly, biweekly, weekly, quarterly}`, and the
multiplier and next-date tables matched it, so a commitment that bills once a
year was dropped before it was built — not mis-sized, absent.

Two further bars sat under it:

- Cadence is inferred from **two or more sightings**. Six months of card coverage
  cannot contain two occurrences of an annual bill, so inference returns nothing
  and the merchant reads as `irregular`.
- The recurring query required `HAVING COUNT(*) >= 2`, so a once-a-year merchant
  was never a candidate in the first place.

This is exactly the failure D18 and D23 describe from the other end: an annual
obligation that never lands drags its sinking fund down by a twelfth of itself
every month, and the shortfall only surfaces when the bill arrives. The property
tax was seeded by hand precisely because of this; the HOA would have needed the
same workaround forever.

Fixed in 0.11: `annual` added to the cadence vocabulary (multiplier 1, next date
+1 year), a `cadence_override` on the merchant that outranks inference, and
admission to the recurring set on one sighting when a cadence has been declared.

**Not fixed, and still P0-3:** the detector's inferred labels remain wrong —
Costco reads "likely weekly, $61,113/yr annualized", Airbnb "likely weekly".
Declaring a cadence is a way around that for known bills, not a repair of it.

---

### P0-29 — An operator override the dashboard never read

The registry lets an operator overrule a provider that is wrong about an account
— `classification_override` exists because Fidelity reports both 529s as
`Taxable` on **every** sync, so correcting the row once would not hold.

The override was written, reapplied after every evidence refresh, and read back
only inside the registry. The dashboard builds its account summaries from the
*portfolio* account and derives `asset_group` from the provider's account type,
so both 529s were filed as taxable no matter what the registry said. $29,858.44
sat under the wrong heading while education read as $6,793.17 — a fifth of its
real size.

Fixed in 0.4: `fetch_registry_classification_overrides` threads overridden rows
through `gather_service_data` → `build_account_summaries` →
`_build_portfolio_summary`, which now prefers the override for `asset_group`,
`account_type`, `money_role` and balance-freshness thresholds. **Only overridden
rows are affected** — a registry classification that merely agrees with the
provider changes nothing, so no total moves that nobody asked to move.

Generalisable lesson, worth carrying into Phase 1: *an override is not applied
until every read path honours it.* The identity override added in 0.3 has the
same shape and the same exposure — the ledger's account filter still lists
`Visa Credit ****4635`, `Visa credit ending 4635` and `Visa ending 4635` as three
accounts because it builds its options from raw `account_label` rather than the
registry, and the 529 summaries still show the provider's label
`Individual - 529` with no mask instead of `Fidelity - Individual - 529 *6273`.
Classification is fixed; **label and mask are not** — that is 0.3's remainder.

---

### P0-30 — An account the household spends *from* could never be discovered

`detect_unknown_accounts` only read transfer and payment **descriptions** — it
finds accounts money was sent *to*. A card is never a transfer description, so a
card the household actually spends on, named on five Walmart receipts, was
invisible to it.

The signal was sitting in plain view: those transactions carry an
`account_label` that resolved to no registry account. Five rows named a Visa
ending 4635 across 2025-08-27 to 2026-04-27 and nothing ever asked about it, so
the money sat outside every account total while the ledger filter split it into
three.

Detection now also reads unresolved transaction labels, grouped by trailing
mask — the only part of a merchant's spelling that identifies anything — and
skips any mask already on file. The inbox item reads: *"5 transactions were spent
from an account ending 4635 between 2025-08-27 and 2026-04-27, and it matches no
account on file. The source spells it 3 different ways… Until it is identified
these rows sit outside every account total."*

**Still open, and it is the household's to answer:** what is the ·4635 card?
Confirming it links those five receipts to a real account. Until then the ledger
shows them under one honest, unidentified name.

### P0-31 — Four applied statements sat in the review queue for five months telling the household to re-upload them

**[fixed]**

`012726`, `013026`, `022526` and `022726 WellsFargo.pdf` all read
`status: needs_review`, `review_status: failed`, summary *"Jenny could not
finish reviewing this document yet. Re-upload or add more context."*

Their spend was in the ledger the whole time — **41 transactions** spanning
2025-12-26 to 2026-02-27 — and their own metadata said so:
`application_summary.status = "applied"`,
`reconciliation_summary.review_strategy = "recovered_without_source"`. Only the
PDFs had gone: their recorded `stored_path` points under a home directory that
no longer exists.

The maintenance pass already detected exactly this and wrote both summaries —
and then stopped, never touching `status` or `review_status`. So the false alarm
was permanent, and the one action it recommended was the one thing that could
double-count spend the ledger already held.

Recovery now settles the document: `parsed`, `complete`, and a summary that says
the file is gone and its rows are already counted. The count in that sentence is
read back from `household_transactions` inside the helper rather than passed in,
so the reassurance cannot outlive its evidence.

The other half is a document whose file is gone and which **never** applied —
`image.png`, staged in March, zero transactions, 33% review confidence.
Re-uploading really is the fix there, so it stays in the queue, but it now says
the file is missing instead of repeating the generic failure on every pass.

Incidentally this is also where the two Wells Fargo checking accounts show
themselves: `012726` and `013026` are the *same weeks of the same month for two
different accounts*, and their $506.31 "Recurring Transfer to / From Leslie E"
rows on 2026-01-02 are the two sides of one internal transfer. Both are already
classified as transfers, not spend, so nothing is double-counted (P0-22's fix
holds).

---

### P0-32 — A document that changes nothing was held open waiting for approval

**[fixed]**

The Amazon `Order History.csv` reads 3,056 rows, finds all 3,051 known ones
already imported and **0 new**, 0 unreadable, and proposes nothing:
`proposed_changes: []`, confidence 0.98.

Approval already refuses a proposal in that state — *"This review has no explicit
money-data changes to approve. Reject it or re-run review with clearer
evidence."* So the only decision available was Reject, and rejecting changes
exactly as much as approving would. The document was pinned in the queue asking
for a decision whose two outcomes are identical.

It got there because a **general preference question** — *"Should Jenny treat
Amazon orders like this as part of regular household spending?"* — sets
`ambiguity_remaining`, and that gates the document regardless of whether the file
has anything left to apply. A nice-to-know question was holding a finished file.

A proposal with an empty `proposed_changes` now settles the document instead of
binding a decision, read from the same field the approval path refuses on, so a
proposal can never be both un-approvable and held open awaiting approval. The
review's questions are inserted whether or not the document is held, so the
preference is still asked — it just stops pinning a finished file.

---

### P0-33 — Two accounts, one name, and no way to tell which held the money

**[fixed]**

SnapTrade reports both of the household's Fidelity rollover IRAs as
`Rollover IRA`. The accounts list rendered that name twice: one row at
**$9,596.29**, the other at **$0.00** with no mask at all. Nothing on either row
said which was which, and the empty one read *"Fresh"*.

They are genuinely two accounts (·2283 at $0.00, ·8698 funded), not a duplicate —
so hiding one would have been wrong. This is the same shape as the two Chase
Sapphire cards Chase reports as `Ultimate Rewards`, and as the two Fidelity 529s:
both of those were corrected by hand, one account at a time, with an
`identity_override`. Nobody should have to.

The registry already recorded both masks at sync time. A portfolio-origin summary
now falls back to the registry's mask when no override set one — filling an empty
field, not renaming an account — and a final pass appends the mask **only where
two labels actually collide**. An account whose name is already unique keeps
exactly the name the provider or the operator gave it, and a colliding account
with no mask is left ambiguous rather than given an invented suffix.

Net worth before and after: **$1,530,455.18** both times. A labelling fix, not a
valuation change.

### P0-34 — The Ledger said $71.03 of July was excluded; every total counted it

**[fixed]**

Three surfaces agreed on July 2026 spend — the spending summary, the monthly
trend and the month comparison all said **$16,708.01**. The Ledger, listing the
same month row by row, counted **$16,636.98** across 109 rows. Three Amazon
charges were marked *excluded as a duplicate* on the one screen built to explain
why a row does or does not count.

The totals decide spend over transaction rows alone; the Ledger ran its dedup
pass over transactions **and** imported receipt lines together. An import row
never reaches a spend total itself, so letting one suppress a charge removed
real money from exactly one surface — P0-1's defect, one screen down, on the
screen a person would open to check P0-1.

The Ledger now runs two passes. Spend inclusion is decided over transaction rows
only, exactly as `_spend_rows_between` does it. The combined pass still runs, but
its result is a **`duplicate_note`** — provenance, the sentence that says an
imported receipt line describes this same purchase — and not a reason to drop
the row. The three Amazon charges count and keep their note.

Ledger and totals now both report **112 rows / $16,708.01**, difference $0.00,
with no id counted on one side and not the other.

---

### P0-35 — The reversal netting was written for July and never fired on July

**[fixed]**

`_household_reversal_pairs.py` opens by naming its reference case: a $1,102.23
Pinellas deposit on 2026-07-09 and a $1,102.23 "COUNTREVERSAL" debit on the
10th. Its unit tests pair exactly that. On live data it returned **7 pairs, none
of them in July** — the matcher had never been shown the second leg.

Candidates came from the spend rows plus the income rows. An outflow filed under
`Income` is dropped from spend by the `category:income` rule long before pairing
runs, so the deposit was offered a partner that had already been discarded. The
charge was kept out of spend by that rule — the right answer for the wrong
reason — while the deposit sat in income permanently. July income read
**$3,906.59** gross when a paycheque worth $1,102.23 of it had been taken back
the next day.

Pairing now also reads the outflows filed under income, on the same terms
`_income_rows` reads the inflows, and dedupes by id. Deliberately that one
category rather than the whole non-spend list: the household's transfers between
its own accounts are same-amount opposite-direction twins by construction and
must not annihilate each other, but an expense filed as income is not a
transfer — it is a deposit being taken back.

Live pairs: **7 → 8**. July income **$3,906.59 → $2,804.36**. July spend
unchanged at $16,708.01, because the charge was already excluded; it is now
excluded for the reason that is true.

### P1-36 — One category, two rows, because purchase items kept a second opinion

**[fixed]**

1.6 made essentiality a **function of the category** and repaired every stored
transaction to match. Purchase items were not told. `suggest_essentiality` kept
its own three-name list (`Groceries`, `Gas`, `Bills` are essential, everything
else is discretionary) and could never return `mixed` at all, and
`load_item_splits` grouped by the essentiality stored on the item row.

So the budget table carried **Household** twice for July 2026: `mixed` at
$12,985.32 from its transactions, and `discretionary` at $71.03 from the items
of three Amazon charges. Two rows, one category — the doubling P1-7 closed,
reappearing through the one path that had its own classifier. It is worse than
cosmetic here: a cap on Household would have been compared against whichever of
the two rows the reader happened to be looking at.

Splits now derive essentiality from their category like everything else, the
grouping key drops the stored value, and `_canonicalize_stored_essentiality`
repairs `household_purchase_items` alongside `household_transactions`. Live:
**3,042 rows aligned**, zero on a second pass, no duplicate category in the
spending view, and July's total unchanged at $16,708.01 — Household is now one
row at $13,056.35.

### P1-37 — The note income the anchor was told to look for is not arriving, and could not have been seen if it were

**[confirmed — no code change; the household has to answer the second half]**

3.1 was told to confirm whether the **$506.31/mo seller-financed note** from
Michael Wiley (P0-23) is still being paid, and to include it in the income
anchor if it is. It is not: the last payment in the ledger is **2026-03-02**,
five complete months before the anchor's window opens, and nothing since has
landed on any tracked account. The receiving Wells Fargo account closed in
March, so either the note ended or the money now lands somewhere the system
cannot see. Only the household can say which.

The second half is the part worth keeping. Every one of those payments is
classified **`transfer_in`**, not `income` — the Zelle and recurring-transfer
descriptions that P0-23 stopped the *spend* filters from eating still keep the
row out of `flow_type = 'income'`. So even if the note resumed tomorrow on a
tracked account, the income anchor would not see it, because the anchor reads
income and this arrives as a transfer. That is the right behaviour for the
transfer between the household's own accounts it looks like, and the wrong
answer for money a third party pays them.

Not fixed here, deliberately: reclassifying it requires knowing that Michael
Wiley is not the household, which is exactly the account-ownership question D15
is blocked on. The **declared anchor** covers the case in the meantime — a
household that knows $506.31 is arriving somewhere untracked can say so, dated,
and the card will show it beside what the ledger can actually measure.

---

## 4. Diagnosis in one line

The Money section is a **data-engineering console wearing a dashboard's
clothes**. Enormous machinery (levers, price checks, product catalog, buy guide,
shopping lists, trust badges, decision boards) sits on top of a budget where 17
of 19 categories have no cap, income is partially captured, one vacation is
being annualized as $85k of bills, and the same question has five answers. The
fix is not more surface — it is **one trustworthy number pipeline, one review
screen, and everything else demoted to a place you visit only when fixing
something.**

---

## 5. Open questions — ALL RESOLVED

All seven questions from the audit are closed. Three were answered from the data
(Q6 529s, Q7 the check, and the housing/coverage question), four by the user on
2026-08-22. See D16–D23.

| # | Question | Resolution |
|---|---|---|
| 1 | Savings target | **D17** — paused with a declared restart trigger |
| 2 | Income anchor | **D16** — trailing 3-month median, manual override |
| 3 | Sinking fund list | **D18** — Travel, Home repair, Insurance/taxes/registration, Gifts; amounts auto-derived |
| 4 | Mariana's phone/OS | **D19** — both adults on Android; the iOS blocker is void |
| 5 | Alert thresholds | **D19** — projected overage, novelty, category 100%, better-price |
| 6 | The extra 529 rows | **D20** — CollegeAmerica/VCSP is the pre-transfer Fidelity identity; four accounts, $36,651.61 |
| 7 | The $3,606 check | **D21** — cruise repayment to Mariana's mother + travel cash; Travel, not Bills |

Two questions surfaced *during* the resolution and are answered in the same pass:
housing (**D22** — Wells Fargo closed, CMA is the hub, no mortgage; the household
*receives* note income per P0-23) and the missing property tax (**D23** — it
predates every feed and must be seeded manually).

**Nothing is blocking. The plan is ready to build.**

One item to confirm in passing rather than block on: whether the $506.31/mo note
income from Michael Wiley is still being paid after the receiving account closed
in March (P0-23). If it is, it belongs in the income anchor (D16).

---

## 6. Decisions log

### D1 — Review mode: retrospective, not envelope
User: *"probably item 1, but if there's a better way let me know... i'd also want alerts that can go to mariana and i on our phone."*
**Decided:** retrospective review is the spine. Rejected zero-based envelopes —
income is lumpy and partly uncaptured, and 19 manual caps is the exact
"unnecessary complication" being complained about. Forward safety comes from
**alerts**, not envelopes. Three modes replace nine tabs: **Review** (monthly,
together) · **Alerts** (continuous, phone) · **Fix it** (on demand, out of the way).

### D2 — Review must answer four specific sentences
User's own target conversations, treated as acceptance criteria:
1. *"We did good this month, we're under budget overall."* → needs an **overall
   under/over verdict**.
2. *"Overspent on groceries but underspent on gas and overall we're under."* →
   needs **per-category over/under that visibly nets out**.
3. *"We were over budget because of this one purchase but everything else was
   under."* → needs **outlier isolation / contribution-to-variance**, and an
   "excluding largest purchase" view.
4. *"We were over because of these 4 items Mariana bought that she never
   buys."* → needs **novelty detection** (new merchant/product vs history)
   **plus working owner attribution**. Today owner attribution is 91% "Family",
   so requirement 4 is currently impossible.

### D3 — Cadence: any time, but always whole-month comparisons
User: *"sometimes weekly... sometimes monthly... trending up or down based on
previous month and average month over all and in the various budget categories."*
**Decided:** the sliding 1M/3M/6M/12M chips are the bug (they produce the four
contradictory answers in P0-1) and are removed. Replaced by a **month selector**
(current or any closed month) with two fixed comparators: **prior month** and
**all-month average**. Month-to-date is explicitly labelled and paced against
the same day of prior months — never compared to a full month.

### D4 — Telegram is rejected as the alert channel
User: *"i don't like the telegram alerting for this. i'd prefer something custom
and streamlined and simple for my wife. telegram usually has other people trying
to spam and reach out to us on it."*
**Decided:** `TelegramNotifier` is not the channel for household alerts. The
two-sink pattern in `spend_alert_service.py` (UI sink + push sink + per-crossing
dedupe marker) is sound and should be reused; only the transport changes.
Channel TBD (see open questions). Note: it must support **two recipients**
(Elias, Mariana) — today `Notifier.send()` has no recipient parameter and
agent-hub owns a single shared chat.

### D5 — Unit-price comparison is IN scope and must be made correct
User: *"very important that we have accurate feedback on when we're buying
something somewhere that's over priced... take into account bulk savings and use
accurate pricing for products that have a per count/oz."*
**Decided:** Buy Guide is NOT deleted. It is rebuilt. Sub-audit findings below.

---

## 6a. Unit-price sub-audit (`household_buy_guide_service.py`, 424 LOC)

Formula is correct: `unit_cost = total_price / package_quantity`, grouped by
`package_unit` so oz never compares to count. The user's worked example
(32oz@$32 = $1.00/oz vs 64oz@$60 = $0.9375/oz) resolves correctly *in principle*.
Three defects make it unusable in practice:

**U-1 — The user's own example is below the surfacing threshold.**
`MIN_UNIT_SAVINGS_PCT = 0.10`. The example is 6.25% savings and would be
silently dropped. Also gated by `MIN_PACKAGE_SAVINGS = 2.0` and
`MIN_MONTHLY_SAVINGS = 1.0`.

**U-2 — Package-size extraction is wrong on real catalog rows.** Live examples:

| `canonical_name` | parsed | truth | error |
|---|---|---|---|
| Nature Made Triple Omega **3-6-9** … Value Size **150 Ct** | `6 x 9 softgels` → 54 `count` | 150 ct | unit cost **2.8x** off |
| MoKo Case for Fire HD **10 Tablet** … | `10 tablets` → 10 `count` | a phone case | priced per "tablet" |
| TrendPlain Olive Oil **Dispenser Bottle** 16oz/470ml | 16 `weight_oz` | empty bottle, not oil | wrong item *and* wrong unit |

Unit assignment is also inconsistent across the same shelf: honey stored as
`weight_oz`, olive oil as `volume_fl_oz` — incomparable by design.

**U-3 — Architecturally cannot compare different products.**
`_best_candidate()` only searches observations sharing the same `product_id`.
There is no product-family / substitute / size-variant grouping
(`household_product_identifiers` carries only `normalized_key` and `asin`).
"Is the 64oz of the same thing cheaper per oz" is therefore unanswerable unless
both sizes happen to be the same product row.

**Data density confirms the guide cannot fire:**
- 2,194 products; only **479 (22%)** have `package_normalized_quantity`.
- **1,886 products have exactly one price observation.**
- Only **131** product+unit groups clear `MIN_ACTUAL_OBSERVATIONS = 2` *and* have package data.
- Result: Buy Guide renders "No buy-size gaps yet."

**Rebuild requires:** (a) trustworthy package extraction with a confidence gate
and manual override, (b) unit normalization to one comparable base per shelf
(mass vs volume vs count, with density out of scope), (c) substitute/size-variant
grouping, (d) thresholds set from materiality in dollars/month, not a flat 10%.

### D6 — Caps are income-anchored, not history-anchored
User chose income-anchored/history-shaped, and raised two follow-ups (D7, D8).
**Decided:** plan total derives from take-home minus a savings target, then is
distributed across categories using historical shape, adjusted in one setup pass.
Rationale: recent normal is $8,103/mo vs ~$5,588/mo take-home. History-derived
caps would make "under budget" and "going broke" compatible — the verdict has to
mean *lived within income*.

### D7 — Lumpy categories use sinking funds with a visible balance
User: *"how do we handle inconsistent categories like travel when there are
months where we won't travel and months when we'll spend thousands?"*
**Decided:** lumpy categories (Travel, Insurance, registration, Christmas,
Home repair) get an **annual amount + monthly accrual + a running fund balance**.
A vacation month **draws the fund down** rather than counting as an overage:
review line reads *"Travel $2,800 — drew from fund, $200 left"*, not *"over budget"*.

**The mechanism already exists and is broken.** `dashboard.sinking_funds` is fed
by the same defective recurring-commitment detector (P0-3) and currently proposes:

| Fund | Monthly target | Derived from |
|---|---|---|
| Airbnb buffer | **$3,319/mo** | annualized $39,833 |
| Avis buffer | $1,488/mo | annualized $17,857 |
| Lufthansa buffer | $1,226/mo | annualized $14,715 |
| Costco buffer | $1,070/mo | annualized $12,845 |

**$7,104/mo of proposed sinking funds — more than total take-home — all from one
vacation.** Fixing P0-3 is a prerequisite for D7; funds must also be user-declared,
not merchant-inferred.

### D8 — Cash is surfaced, and "can we afford this" becomes a real check
User: *"should we also show our cash account (fidelity cma) here or somewhere so
we can decide if we have enough to make a large purchase?"*
**Finding (good news):** cash is already correct. `Cash Management (Joint WROS)`
= the Fidelity CMA, **$30,494.75**, `money_role: spend_driver`, freshness `fresh`.
Spend drivers are exactly two accounts: the CMA and `Amazon Chase (CC)`. Every
other tracked account is `net_worth_only`. `invested + cash = total_tracked` holds
(1,517,248.14 + 30,494.75 = 1,547,742.89) — no double count there.

**Decided:** show cash on the review screen, and add an explicit affordability
check: `cash − bills actually due − rest-of-month essentials − committed fund
balances = free to spend`. This replaces the current Safe-to-Spend, which is bound
by `plan_residual` and never touches the $30k (P0-2).

---

## 6b. Receipt-source sub-audit (triggered by "13 Walmart/Costco PDFs")

- **Walmart: supported.** `_household_document_baseline._classify_walmart` fires on
  `"walmart" + "order details"` in text, or `walmart` in filename; confidence 0.84.
  12 Walmart files already ingested, 17 purchase items linked.
- **Costco: never ingested — 0 Costco documents exist.** No Costco classifier;
  falls through to the generic keyword row
  `(["receipt","walmart","target","costco"], "receipt", "receipt", 0.8)`.
- **Warehouse-club instant-savings markdowns ARE handled** — the `4.50-` line
  under an item is covered in `_household_document_llm.py:169` and
  `_household_document_pipeline_receipt.py:53`.
- **Risk:** Costco line items are abbreviated (`KS ORG PNT BTR 2/28OZ`). Package
  extraction already misreads clean Amazon titles (U-2), so it will do worse here.
  Treat Costco as build-and-verify, not drop-in. Upside: Costco is the ideal test
  corpus for the unit-price rebuild, since bulk-vs-unit is the whole point there.

### U-4 — The item layer is disconnected from the money layer
`household_purchase_items`: 3,067 rows. **Only 81 (2.6%) have a `transaction_id`.**
All 3,067 have `document_id`, `product_id` and `unit_price`. Item-level detail
therefore has no account, no ledger date, and no owner for 97.4% of rows.

**This makes D2 requirement 4 ("the 4 items Mariana bought that she never buys")
impossible today**, and it is why the product catalog (2,194 products) cannot be
tied back to budget categories or to actual spend.

### P2-19 — ~~Duplicate accounts inflate net worth~~ **RETRACTED — see D12**
Original claim (529s and Rollover IRAs were duplicates overstating net worth) was
**wrong**: distinct account masks, and the user confirms two 529s per daughter.
The real defect is the `asset_group` misfiling recorded in **D12**. Kept here only
so the retraction is visible; do not act on the struck text.

### D9 — Retirement stays in Money; the defect was flatness, not placement
User challenged the proposal to move it out. **Decided:** it stays.
Counter-evidence that overturned the original recommendation: profile targets
`target_retirement_age: 49` at `target_retirement_spend: $7,500/mo`, against
current spend $8,103 and take-home $5,588. **The monthly budget is the retirement
model's primary input** — savings rate is what makes 49 feasible. Separating them
hides the strongest causal link in the household's finances.

The real defect is nine flat peers. New IA — one primary, three supports, one
long-horizon:
- **Primary:** Review (default; the routine sit-down screen)
- **Supporting:** Plan · Prices · Fix it
- **Long horizon:** Retirement, with a two-way link to Review
(Size context, for the record: `MoneyRetirementPanel.tsx` 201KB +
`retirement-planner-model.ts` 46KB + `RetirementResults.tsx` 37KB ≈ 284KB, versus
~60KB for all five tabs under review. Mass argued for splitting; causality won.)

### D10 — Prices is a real subsystem: multi-store unit cost, camera capture, "Should I buy this?"
User: *"track per item cost accurately with count and oz across multiple stores…
camera capture capability… take pictures of the price cards which typically have
per oz/count pricing… a 'Should I buy this' feature… routinely scrape/check
costco/walmart/amazon/aldi/etc."*

**Already built (better than expected):**
- `household_product_price_observations` carries `merchant_id`, `unit_price`,
  `package_normalized_quantity`, `package_normalized_unit` — **the multi-store
  per-unit matrix is already the schema.**
- `household_vendor_profiles` holds all five named stores (aldi, amazon, costco,
  publix, walmart), all `enabled`, each with `delivery_fee`, `pickup_fee`,
  `free_delivery_threshold`, `membership_monthly_fee`, `membership_active` —
  fee-aware comparison is modelled.
- `_price_firecrawl_lookup.py` has adapters for amazon.com, walmart.com, aldi.us,
  costco.com + sameday.costco.com, publix.com. `ST_WEB_FOCUS_QUERY` is already
  tuned to *"package size unit price ounce oz fl oz lb count ct"*, with
  `_UNIT_PRICE_PATTERN` parsing `$0.42 / oz`.

**Why it yields nothing:** of 3,075 observations — **2,991 order_history (Amazon),
76 receipt, 8 vendor_quote.** Essentially no cross-store data. Plus no
product-family grouping (U-3), all vendor fees unset, and Costco
`membership_active: false` despite receipts printing member 111772590689.

**Key insight — the shelf tag is the join key.** A Costco receipt gives an item
number + abbreviated name with no size (`1272413 KS ORG OAT`). A Costco shelf tag
prints the same item number, full description, package size, **and the per-ounce
price**. Photographing tags builds the item-number→product map that makes every
past and future Costco receipt line resolvable, and populates the price matrix at
the same time. The camera is not a side feature — it is the cheapest path to the
data the comparison depends on, captured exactly when the decision is being made.

**No camera capture exists today** — the only image input is `accept="image/*,.pdf"`
on `AddCardDialog` (file picker, no `capture` attribute).

**Proposed order:** package extraction → product-family grouping → Costco
item-number map from shelf tags → scraping as a routine → in-store "Should I buy
this?" screen. Camera-first would produce photographs nothing can compare.

### D11 — Alert channel: web push via the PWA that already ships
Replaces the rejected Telegram transport (D4). **Finding:** the PWA is real and
live — `manifest.json` linked in `layout.tsx`, `sw.js` registered at scope `/`,
`display: standalone`, 192/512 icons present. Portfolio AI installs to a phone
home screen today. Missing: only a `push` handler in the service worker (no
`push`/`notificationclick` listeners) and subscription storage.

Fits every stated constraint: custom, streamlined, nobody can message them on it,
lands in the app holding the data. **Recipient routing comes free** — each device
subscribes separately, so Elias and Mariana can receive different alerts, which
`Notifier.send()` (no recipient param, one shared agent-hub chat) cannot do.
**Constraint to flag:** iOS web push requires the PWA be added to the home screen
(iOS 16.4+) — one-time setup for Mariana if she's on iPhone.

Reuse `spend_alert_service.py`'s proven shape: evaluate → two sinks
(`jenny_notifications` + push) → per-crossing dedupe marker. Swap transport only.

### P0-20 — Two credit cards and ~$11,500 of debt are invisible
User: *"we have two other credit cards we just got to split a ~11500 AC
replacement… chase saphire preferred, ~120k and 100k points… we haven't paid
those off yet."*

**Neither card exists in the system.** Only credit account is
`Chase Prime Visa / Amazon card *9728`. **`household_credit_cards` has 0 rows** —
so the entire Cards tab (welcome-bonus/MSR tracking, rotation, annual-fee alerts)
has never run against real data; `DEFAULT_MONTHLY_CAP = 6500.0` is the fallback.
The $11,500 AC purchase is absent from the ledger (largest recorded expenses:
$3,606 check, $2,111 Carnival, $1,545 Wayfair).

Consequences:
- `liabilities_total` reads **$5,423.66** against roughly **$16,900** owed →
  **net worth overstated by ~$11,500**.
- All spend on those cards since opening is missing from spend, categories, pace
  and the needs/wants split — compounding the "2 covered spending accounts"
  problem (P1-13) that already sits behind a *"Strong household visibility 99%"* label.
- Money left on the table: 220k points implies MSRs were met; Sapphire Preferred
  annual fees fall due at the 1-year mark. `_welcome_alerts` and
  `_annual_fee_alerts` (with downgrade-not-cancel guidance) are built and idle.

**Disposition change:** Cards is *not* demoted to Fix it. Card commitments are
plan-shaped (annual fees, welcome deadlines, balances owed) → **Plan**, with its
alerts folded into the alert stream.

**Also corrects the affordability panel:** cash $30,495 − bills due $395 −
rest-of-month essentials $1,840 − committed funds $2,150 − **card balances
$16,924** = **$9,186 free**, not $26,110.

### D12 — Correction logged
Earlier claim that the two `Individual - 529` rows were duplicates inflating net
worth was **wrong** — masks `*6273` / `*6277`, one per daughter (user confirms two
529s each: two Fidelity, two Merrill Edge, to be consolidated into Fidelity).
The real defect: **both Fidelity 529s carry `asset_group: taxable`**, so education
reads $6,793 (Merrill only) instead of ~$36,651 — understated ~5x, taxable
overstated by $29,858. Two legacy CollegeAmerica/VCSP 529 rows also exist and
need confirming during accounts cleanup.

### D13 — Retirement block is phase-aware and measures plan feasibility, not contribution compliance
User: *"49 might change so that shouldn't be static… we may or may not care about
saving further per month (what does this section look like when we're in
retirement? …what about if we're not in retirement but not saving because our
assets are growing well enough on their own?)"*

**Finding — the current tracker reports a meaningless pass.**
`retirement_contribution_tracker` returns `status: "on_track"` with
`monthly_target: 0.0`, `estimated_monthly_contributions: 0.0`, `monthly_gap: 0.0`
and *"Recent retirement contributions are keeping up with the savings target."*
Zero trivially keeps up with zero — the same defect class as
`budget_snapshot.status: "on_track"` (P0-4): a green verdict from an unset input.
Driven by `profile.monthly_savings_target: 0.0`.

**Finding — contribution framing is quantitatively wrong for this household.**
Net worth trend runs **+8.5% Feb–Aug** on ~$1.5M invested ≈ **$19,800/mo** of asset
growth. Against a $300/mo contribution that is ~**66×**. Reporting "$0 saved — miss"
would be noise.

**Decided:** the block answers *"is the plan still on track"*, driven by three
phases, with `profile.target_retirement_age` read live (never hardcoded):

| Phase | Question | Shows |
|---|---|---|
| Accumulating, contributions binding | Are we still going to make the target age? | Needs $X/mo, added $Y, projection moved to age Z |
| Accumulating, growth carrying it *(current state)* | Do we even need to save more? | Plan holds at 0% savings rate; contributions noted, not judged |
| In retirement, drawing down | Is this withdrawal sustainable? | Withdrew $X · rate% · guardrail status · phase + years to next phase |

Phase transition is `current_age` vs `target_retirement_age`, so changing 49 moves
the boundary and nothing else. **The drawdown state needs no new profile inputs** —
`withdrawal_strategy: "guardrails"`, `withdrawal_initial_rate: 0.05`,
`phase_slow_go_age: 75` / `phase_no_go_age: 85` with their spend percentages, and
`social_security_payable_ratio: 0.77` all already exist.

**Two-way link:** the plan assumes `target_retirement_spend: $7,500/mo`; actual
averages $8,103. Review is where that gap becomes visible — a retirement fact
discovered by a budget screen.

### D14 — Sequencing: trust pipeline first, nothing dropped
User: *"item 1 (trust pipeline first) but don't ignore everything else that needs
to be built and drop it from the plan. that's just what's first."*
**Decided:** phases below. Nothing from D1–D13 is descoped; ordering only.
Also confirmed: **the Retirement tab is NOT removed** — it stays in Money, ceasing
to be a flat peer and gaining the Review link.

### D15 — Family-wide capture is the data strategy, and identity is the unlock
User: *"i definitely want the 'should i buy it' stuff and ability to easily take
pictures with whichever phone (my kids have iphones). if we can get all four of us
to use that when we're out shopping then it could really start to build some good
data…even data that helps us understand our shopping habits and identify any bad
habits."*

**Decided:** shelf-tag capture is a **four-person** capability (Elias, Mariana,
Nadia, Sophia), not a solo tool. "Should I buy this?" is confirmed in scope
(Phase 5.7) and is the reason anyone opens the camera; the price matrix is the
byproduct.

**Finding — identity is authenticated and then discarded.**
`frontend/middleware.ts` verifies a Cloudflare Access JWT and reads
`payload.email`, then returns `NextResponse.next()` **without forwarding it**. No
backend endpoint reads `cf-access-jwt-assertion` or any user header. The app
authenticates individuals and then treats every action as anonymous.

**Finding — the owner vocabulary already exists, unpopulated.**
`household_members` holds all four (Elias 1977 primary · Mariana 1982 spouse ·
Nadia 2012 child/dependent · Sophia 2012 child/dependent, all `confirmed`).
`frontend/components/money/owner-options.ts` already names them plus Oksana, Cats
and combinations. Yet attribution runs **91% "Family"** because nothing populates it.

**Consequence — this reorders Phases 4 and 5.** Propagating the authenticated
identity is a small change that makes **owner attribution a byproduct of capture**
rather than a separate build: whoever photographs the tag or uploads the receipt
is recorded automatically. Phase 4.4 (owner attribution) therefore depends on
Phase 5.0 (identity propagation), not the other way round.

**Requirement — capture must be a scoped surface.** Nadia and Sophia are 14. They
need a **capture-only view**: camera + "Should I buy this?" and nothing else — no
net worth, no account numbers, no ledger, no retirement. Cloudflare Access gates
by email; the app needs a role check mapping email → `household_members.role`, with
`child` restricted to the capture surface.

**Auth decision (user-confirmed):** all four have Gmail accounts and will
authenticate through **Cloudflare Access with Google as the IdP**. `payload.email`
becomes the owner key.

**The four identities.** This repo is **public** — the real Gmail addresses are
deliberately NOT recorded here, and two of the four belong to minors. The
addresses live outside version control (see below); this table is the shape only.

| Email | `household_members` | Role | Money access |
|---|---|---|---|
| `<elias-email>` | Elias (1977) | `primary` | Full |
| `<mariana-email>` | Mariana (1982) | `spouse` | Full |
| `<nadia-email>` | Nadia (2012) | `child` | **Capture only** |
| `<sophia-email>` | Sophia (2012) | `child` | **Capture only** |

> **Where the real addresses live — already provisioned, do not ask the user:**
> `.env.local` → `HOUSEHOLD_MEMBER_EMAILS`, a JSON map of Access `payload.email`
> → `household_members.display_name`. That file is gitignored (`.gitignore:43-45`),
> mode 600, and already loaded by `backend/app/config/__init__.py:31-33`, so the
> value reaches `Settings` with no new plumbing. `.env.example` carries the key
> with placeholder values as documentation.
>
> Rules: resolve by `display_name`, failing loudly on a missing or ambiguous
> name. Access tier is **not** in the env value — derive it from
> `household_members.role` (`primary`/`spouse` → full Money, `child` → capture
> only). Never log, echo, commit or transmit the addresses; two belong to minors.
> Once Phase 5.0 lands the `household_members.email` column, **the DB column is
> authoritative** and the env var is only the seed source.

**Gap to close:** `household_members` has **no email column** (id, display_name,
role, relationship, birth_year, is_dependent, lives_in_household, notes,
confirmation_status, provenance, evidence_note, source_document_id, timestamps).
Needs a migration adding a unique email field. The migration adds the column
only — the four addresses are seeded at run time from `HOUSEHOLD_MEMBER_EMAILS`
(see above), never written into the migration file. Then: Access JWT → `payload.email` → `household_members` row →
`owner_name` on every capture, receipt upload and manual edit.

**Access policy shape:** one policy admitting all four emails to the capture
route; a second admitting only Elias + Mariana to the rest of Money. Belt and
braces — enforce the same rule app-side off `household_members.role`, so a policy
misconfiguration doesn't expose the ledger to a `child` role.

**iOS note:** `<input type="file" accept="image/*" capture="environment">` opens
the camera directly in iOS Safari — no PWA install needed to capture. Install is
only required for *push* (D11). Kids open a URL; friction stays near zero, which
is what adoption depends on.

**New capability — shopping-habit analysis (Phase 6).** Capture + receipt data
together yield signals no receipt alone can: captured-but-not-bought (considered
and declined), bought-without-capture (impulse), repeat captures of one item
(deliberation), store/time-of-day patterns, per-person basket composition,
recurring overspend shapes. Worth noting: per-person habit reporting on minors is
a deliberate choice, not a default — decide the granularity before switching it on.

---

### D16 — Income anchors to a trailing 3-month median, recomputed monthly

User-selected. The $6,283/mo target ($2,900 biweekly) sits $700–$3,000 above
what actually arrives (Jun $7,348 → Jul $3,857 → Aug $3,205), and the household
is on unemployment with SummitFlow pending. A median (not a mean) resists the
single-month payroll spikes and reversals that distort this data.

Ships with a **manual override field** so a known change (SummitFlow starting)
can be declared instead of waited for. The override is sticky and dated; the
auto value resumes when it is cleared.

### D17 — Savings target is explicitly paused, with a declared restart trigger

User-selected. The profile's `monthly_savings_target: 0.0` currently produces a
vacuous "on track" (zero trivially keeps up with zero). Instead the block states
*paused* as a deliberate state, and prompts to resume when the trailing income
median clears a user-set threshold. Consistent with D13: net worth grew ~$19,800/mo
Feb–Aug on its own, which is 66× any $300 contribution, so contribution
compliance is the wrong thing to measure right now.

### D18 — Sinking funds: four categories, amounts derived automatically

User-selected categories: **Travel**, **Home repair & appliances**,
**Insurance, taxes & registration**, **Gifts & holidays**.

User requirement, verbatim: *"it's fine if these sorts of categories have a
manual override but i'd want them to be automatically set in an intelligent
manner based on known good data (travel and other sinking fund category related
expenses averaged per month/year/etc., whatever you think is best)."*

Derivation rule: for each fund, take the trailing 12 months of that category's
spend **after** novelty/reversal cleanup, drop the top outlier if it is a
one-time event the user has marked as such, and divide by 12 to get the monthly
contribution. Show the derivation inline ("$5,012 of travel over 12 months →
$418/mo") so the number is auditable rather than magic. Manual override per
fund, dated, with the auto value still visible beside it.

Known obligations that predate all feeds must be seeded manually or the average
is wrong — see D23 on the property tax.

### D19 — Alerts: four triggers, and both adults are on Android

User-selected triggers: **projected to exceed the month's plan**, **novelty /
outlier purchases**, **category hit 100% of cap** (not 85%), and **better price
found elsewhere** (once Phase 5 lands unit pricing).

Devices: Elias **Pixel 7 Pro**, Mariana **Samsung Galaxy S22 Ultra** — both
Android. The girls are on iPhone but are capture-only (D15) and do not receive
budget alerts.

**This retires the D11 iOS concern entirely.** Web push works on Android Chrome
with no add-to-home-screen step, so no install ceremony is required for either
recipient. iOS only mattered for the girls, and camera capture works from Safari
via `capture="environment"` without installing anything.

### D20 — The 529s: four accounts, not six

User-confirmed: CollegeAmerica / VCSP is the **pre-transfer identity** of the two
Fidelity 529s. Resolution:

| Keep | Merge in | Balance |
|---|---|---|
| Fidelity *6273 | CollegeAmerica / VCSP 87595982 (Nadia) | $14,929.22 |
| Fidelity *6277 | CollegeAmerica / VCSP 87595967 (Sophia) | $14,929.22 |
| Merrill Edge 22Z-87861 (Nadia) | evidence row "529 - Nadia" $3,145.58 | $3,395.57 |
| Merrill Edge 25Z-87861 (Sophia) | evidence row "529 - Sophia" $3,147.46 | $3,397.60 |

Education total resolves to **$36,651.61**. Both Fidelity rows also need
`asset_group` corrected from `taxable` to `education` and `account_type` from
`brokerage` to `529`.

Data-quality flag: both CollegeAmerica balances are $14,363.57 **to the cent**,
which is more likely an extraction error applying one value to both daughters
than a genuine coincidence. Verify against the source PDF before merging.

### D21 — Check #1002 is travel and a family repayment, not a bill

User-supplied: the $3,606.00 check paid 2026-08-06 covered a **repayment to
Mariana's mother for a cruise (~$1,200)** plus **cash for Mariana's trip to
Germany and Ukraine** to see family.

It is currently categorized `Bills`, where it distorts August into the worst
month of the year. Correct handling: split into the cruise repayment (Travel,
and reconcilable against the Carnival charges already in the ledger) and the
travel cash (Travel). Neither belongs in Bills.

This is the archetype for a needed capability: **a single opaque transaction
that only a human can explain, which changes the verdict for its month.** The
review screen needs a first-class "explain this" affordance that attaches a
durable note and a split, rather than forcing a recategorization that loses the
reason.

### D22 — Account truth: Wells Fargo is closed, the CMA is the hub

User-supplied corrections:

- **Wells Fargo accounts are closed.** Everything moved to the Fidelity CMA for
  checking and cash. Do **not** attempt to reconnect them — their data is
  correctly historical, and P0-21's fix is to stop counting them as live, not to
  revive them.
- **`Chase Amazon card` and `Prime Visa` are the same card.** Two labels, one
  account.
- **The two Chase Sapphire cards need live Plaid feeds** — ~$16,924 of
  AC-replacement balance and ~220k points are invisible today (P0-20).
- Card rotation for travel points is an ongoing practice, so **new cards must be
  connectable as a routine operation**, not a one-time setup.

The resulting model is clean and worth stating plainly, because the current UI
obscures it:

| Account | Role | Feed |
|---|---|---|
| Fidelity CMA (Joint WROS) | income + bills + card payoff | SnapTrade, live |
| Prime Visa | day-to-day spend | Plaid, live |
| Sapphire ×2 | large purchases + points | **not connected** |

Verified from the CMA's own rows: Duke Energy, T-Mobile, Frontier, P C Utilities
and payroll all land here monthly, plus a $6,757.73 Chase card payoff in July.
**Every "metronomic bill" P0-3 claims to be missing is already in this account** —
the detector is looking in the wrong place, not working with missing data.

### D23 — The $2,144.48 property tax predates every feed

Searching the ledger for `2144.48` returns nothing, but this is not a parsing
failure. The CMA feed begins 2026-02-19 and Florida property taxes are due
November 1 (Pinellas County, discounted through November 30), so the payment
occurred before any live feed existed and before the Wells Fargo uploads begin.

Consequences: it must be **seeded manually** as a known annual obligation, or
the "Insurance, taxes & registration" sinking fund (D18) will be derived from
incomplete history and under-fund by ~$179/mo. The same applies to any annual
premium paid before February 2026.

This finding is only reachable because the user knew the amount — which is
exactly why P1-25 (search by amount) matters.

**Answered (2026-08-22):** the $2,144.48 *is* the discounted amount, and the
household always pays inside the November window. So the gross bill is
$2,233.83, the 4% discount is the norm rather than a one-off, and the sinking
fund should target the discounted figure. Seeded as an annual `Home` obligation
dated 2025-11-01; next due November 2026.

---

## 7. The plan

**Approved shape:** Money keeps its own section with **one primary tab and three
supports, plus Retirement**:

```
Money  ▸ Review        ← default; the routine sit-down screen
       ▸ Plan          ← caps, sinking funds, income, card commitments
       ▸ Prices        ← unit cost across stores, "Should I buy this?"
       ▸ Fix it        ← ledger, accounts, intake, data repair
       ▸ Retirement    ← stays; two-way link with Review
```

Ordering is **trust first** (D14). Nothing below is optional; phases are sequence,
not priority triage.

---

### Phase 0 — Connect and clean (prerequisite, no UI work)
Everything downstream is wrong until this lands.

Status keys: **[done]** landed and verified · **[part]** partly landed, remainder
named · **[blocked]** waiting on a decision or a source document · **[open]** not
started.

0.1 **[done]** Connect the two **Chase Sapphire Preferred** cards (P0-20).
    Both are live: `·3627` (Elias, first Chase item) and `·8054` (Mariana, second
    Chase item, connected 2026-08-22). The AC replacement is present and was
    **split across the two cards** — $5,831.50 + $5,801.50 = **$11,633.00** on
    2026-07-23, one purchase clearing both minimum spends at once. `household_
    credit_cards` now carries three rows (two Sapphires + the Prime Visa keeper),
    so the welcome-bonus and annual-fee alerting has real subjects. Both welcome
    bonuses compute as **earned** from the ledger.
0.2 **[done]** **Mark dead accounts dead** (P0-21, D22). `feed_status` /
    `coverage_through` on `household_accounts`; Wells Fargo stays closed.
0.3 **[done]** **Resolve account labels to accounts** (P1-24). The CMA, `9728`
    and `4635` variants are merged and the test rows archived; 26 registry rows
    are now 20 live. The two Sapphires arrived from Chase with the *identical*
    label `Ultimate Rewards®` and no owner — the registry cannot separate them
    because the provider genuinely reports one name for both. Named by operator
    override (`identity_override`, reapplied after every evidence refresh) as
    `Chase Sapphire Preferred ·3627` / `·8054` with owners, and the two Fidelity
    529s the same way (`Fidelity 529 ·6273` / `·6277` — Fidelity also reports one
    name for both; owners are still unknown and the inbox can ask).
    **The override now reaches the surfaces that render it** (P0-29): account
    summaries, the money inbox — which said *"Refresh transactions for Chase ·
    Ultimate Rewards®"* and now names the card — and every panel built from
    summaries.
    The ledger's account filter offered one card three times. Those five rows are
    Walmart receipts naming a card the registry has never heard of, and the
    merchant spells it three ways (`Visa Credit ****4635`, `Visa credit ending
    4635`, `Visa ending 4635`), so each option hid two thirds of its own rows.
    A raw label only survives when it resolved to no registry account, so
    unresolved labels sharing a trailing mask now collapse to one deterministic
    spelling — filter options 10 → 8, and filtering on it returns all five rows.
    That is a display repair, not an identification, so the account is **also**
    surfaced for identification (P0-30): the inbox now carries *"Confirm possible
    account: Visa Credit ****4635"*.
0.3a **[done]** Wells Fargo is three rows — masks `7312`, `4222`, and a no-mask
    export. **The household confirmed `7312` and `4222` are two genuinely
    different checking accounts, both now closed.** They are not merged. The
    shared Michael Wiley note payment across them is a real payment made from two
    accounts over time, not an identity collision.
0.4 **[done]** Education resolves to **$36,651.61**, exactly the D20 figure.
    Both Fidelity 529s carry `asset_group: education` / `account_type: 529` by
    classification override; CollegeAmerica/VCSP and the stale "529 College
    Savings" rows are archived. Merrill holds $3,395.57 + $3,397.60.
    **The "no balance" reading was wrong and no source PDF was needed.** SnapTrade
    has been carrying $14,929.22 for each Fidelity 529 all along — linked, active,
    synced. The dashboard was filing both under **taxable**, because the account
    summary took its classification from the *provider's* account type and the
    registry override was only ever read back inside the registry (see P0-29).
    The money was counted; the heading was wrong. Taxable drops $635,774.29 →
    $605,915.85, education rises $6,793.17 → $36,651.61, net worth is unchanged
    at $1,530,455.18 — which is the proof it was a reclassification and not a
    revaluation.
    The D20 data-quality flag is also retired: the identical $14,363.57 is real,
    not an extraction error. The source PDF shows both accounts holding the same
    177.153 shares of CWIAX at $81.08 — matched contributions into one fund. The
    Fidelity pair being identical at $14,929.22 is the same fact, later.
0.5 **[done]** **Fix the duplicated-with-opposite-sign ingest** (P0-22).
0.6 **[done]** **Stop the spend filters from eating income** (P0-23). Filters
    classify and say why instead of deleting.
0.7 **[done]** **Add `amount` to ledger search** (P1-25).
0.8 **[done]** Purge the **"Codex archive smoke"** test account; resolve the
    duplicate registry rows (P2-14).
0.9 **[done]** Investigate the **63% `removed` rate** — **it is genuine dedupe.**
    1,726 of 2,734 rows are removed. Matching every removed row against the live
    set on amount within ±5 days leaves **11 orphans**, not 1,072: the same
    charges arrive from the statement CSV, the activity export and Plaid with a
    few days of posting drift, and the drift is why an exact date+amount match
    looks like mass loss. Of the 11, nine are Plaid rows with `pending = true`
    *and* `removed = true` — pending holds superseded by a posted charge at a
    different amount (Avis $1,250, Compania Panamena $2,017.04, two cruise-line
    holds). One is a soft charge, one a zero-dollar SnapTrade row. **No
    identity-collision loss.** 0.3 and 0.5 were not causing it.
0.10 **[done]** **Seed known pre-feed obligations** (D23). The $2,144.48 is
    seeded as an annual `Home` obligation dated 2025-11-01. The household
    confirmed the amount paid **is** the discounted figure and that it always
    pays inside the November 4% window, so the gross bill was $2,233.83 and the
    next one is due November 2026.
0.11 **[done]** The six `HARBOR HILLS PROPERTY` rows are already deduped to one
    live row (2026-02-17, $104.13) — the P0-22 dedup fix caught them.
    Recategorised `Bills` → `Home` with a merchant rule, so future HOA charges
    land there without a second pass. **The household confirmed the HOA is
    annual**, which the data could never have shown: cadence is inferred from two
    or more sightings, and six months of card coverage will never contain two of
    an annual bill. Two gaps had to close for that answer to mean anything —
    `annual` was not in the cadence vocabulary at all (see P0-28), and there was
    nowhere to *state* a cadence. Merchants now carry a `cadence_override` that
    wins over inference, set through `scripts/household_declare_cadence.py`, and
    a merchant with a declared cadence is admitted to the recurring set on one
    sighting. The HOA now reports as a commitment: annual, $104.13, annualised
    $104.13, next expected 2027-02-17, confidence 1.0.
0.12 **[done]** Costco carries `membership_active` and a $5.42/mo membership
    accrual with a $0 pickup fee. **The household does not use delivery at Aldi,
    Amazon, Publix or Walmart**, so all four now carry a known $0 pickup fee with
    delivery fee and free-delivery threshold deliberately left unset — the
    optimizer prices in-store baskets with no fee, and an unset delivery fee now
    means *not used* rather than *not yet asked*.
0.13 **[open]** Ingest the **13 staged receipts** (8 Walmart, 5 Costco) — depends
    on the Costco parser work in Phase 4.2, and now also on P0-27 below: the
    receipts already ingested show the parser dating a purchase to the day it was
    processed and collapsing several orders into one row.
0.14 **[done]** **Stop receipts and card charges being counted as two purchases.**
    A receipt is now reconciled against the feed that actually moved the money
    (`household_receipt_reconciliation_service.py`). The receipt row is retired —
    `removed = TRUE` with a `metadata.reconciliation` audit blob naming the
    charges, never deleted — and stays as the line-item evidence the feed does
    not carry. Matching allows a **set** of charges, not just a twin, because one
    order routinely posts as several: the 2026-08-17 Walmart receipt for $54.06
    is the $50.48 and $3.58 charges of 2026-08-19, and was previously counted
    twice. Six receipts totalling **$677.20** were retired against seven charges;
    a second pass changes nothing. The same pass also catches a receipt uploaded
    twice as two different files — the ingest content hash only sees a
    byte-identical re-upload — but merges on **proof, not resemblance**: same
    merchant, date, total *and* an identical set of line items. Two trips that
    happened to cost the same both stand, and a receipt with no parsed line items
    is never merged.
    The evidence travels with the money: retiring the receipt would have hidden
    its line items along with it, so a one-charge match **moves the items onto
    the surviving charge and re-allocates them to its amount** — the split loader
    drops any transaction whose allocated cents miss the total, so a re-point
    alone would have left them linked but uncounted. Clicking the $99.00 Walmart
    charge now returns 17 items summing to $99.00. A split order keeps its items
    where they are rather than restating every price against one leg; both legs
    carry a `receipt_evidence` back-reference until an item can span charges
    (Phase 4).
0.15 **[done]** **Make a CSV import say what it will actually change.** An Amazon
    `Order History.csv` could not be applied at all: the file's byte-order mark
    made the first column unreadable, so every row was skipped, the proposal was
    empty, and approval was refused. Imports are now read as `utf-8-sig`, rows
    that carry no usable identity are counted as `skipped` rather than silently
    dropped, and the review proposal shows the real delta — rows in the file, how
    many are new, how many are already known, and the date range of the new ones.

**Exit test — run 2026-08-22 against the live backend. PASSES.**

| Check | Result |
|---|---|
| `liabilities_total` matches reality | **$17,287.71** = 5,896.50 (·8054) + 5,926.50 (·3627) + 5,464.71 (Amazon Chase). ✅ |
| Every account carries an honest freshness status and coverage range | 16 accounts, every one with a `freshness_status`; the three that are not current say so (`stale_balance` / `stale_transactions` gap flags with reasons), and none of the fresh ones is bluffing. ✅ |
| Searching `2144.48` finds the property tax | Exactly 1 hit: 2025-11-01, $2,144.48, Pinellas County Tax Collector, Home / essential, `manual_entry`. ✅ |
| The Progressive premium appears exactly once, as an expense | 2026-02-17 $276.99 expense live; its income twin is `removed = TRUE`. (A separate $763.00 premium on 2026-06-03 is a different charge, correctly its own row.) ✅ |
| Net worth reconciles | 1,547,742.89 assets − 17,287.71 liabilities = **1,530,455.18**. ✅ |

**Carried into Phase 1, not blocking:** the API's `balance` field is `null` on
every portfolio-origin account row while `current_value` carries the number —
the accounts UI renders `currentValue`, so nothing is visibly wrong, but two
fields mean two chances to read the wrong one. Pick one in Phase 1.

---

### Phase 1 — One trustworthy number pipeline — **COMPLETE, exit test passes**
Kills P0-1, P0-2, P0-3, P0-4, P0-5, P1-6, P1-7, P1-8, P1-13 — and P0-34/P0-35,
which only the exit test could have found.

1.1 ✅ **One canonical spend definition** shared by every surface. Report only
    **complete calendar months** and name which months were used. Remove the
    1M/3M/6M/12M sliding chips (D3) — replace with a month selector plus two fixed
    comparators (prior month, all-month average).
1.2 ✅ **Reversal pairing.** Detect same-amount / opposite-direction / same-merchant-
    token rows within N days and net them out. The Jul 09 ↔ Jul 10 Pinellas pair
    is the reference case: it inflates July income *and* July spend by $1,102 and
    makes Bills read $1,497 instead of ~$395.
1.3 ✅ **Rebuild recurring-bill detection** (P0-3). Require true periodicity + amount
    stability. Exclude travel/retail merchants from `commitment_type: "bill"`.
    Must detect Duke Energy, T-Mobile, Frontier, P C Utilities, Waste Pro — and
    must not detect Airbnb, Avis, Lufthansa, Costco.
1.4 ✅ **Rebuild `safe_to_spend`** as a cash-based affordability check (D8):
    `cash − bills actually due − rest-of-month essentials − committed fund
    balances − card balances outstanding`. Retire the `plan_residual` constraint
    and the green "Safe" badge over a disclaimed number.
1.5 ✅ **Delete vacuous verdicts.** No `status: "on_track"` derived from unset inputs
    — applies to `budget_snapshot`, `budget_readiness` ("all lanes Configured"
    with 17/19 caps unset) and `retirement_contribution_tracker` (D13).
1.6 ✅ **Fix the taxonomy** (P1-7). One essentiality per category; collapse the
    duplicate Transportation/Household/Travel series; map Plaid leakage
    ("General Services Storage/Insurance") into the curated set.
1.7 ✅ **Make exclusions visible and appealable** (P1-6). The hardcoded string list in
    `_household_spend_filters.py` ("zelle to", "atm withdrawal", …) gets a UI
    surface, a total, and per-row override.
1.8 ✅ **Merchant normalisation for statement rows** (P1-12) — "DIRECT DEBIT
    DUKEENERGY BILL PAY (Cash)" → "Duke Energy".
1.9 ✅ Replace `visibility_score: 99` with a coverage measure that tracks actual
    account coverage (P1-13).
1.10 ✅ Show the **mixed** bucket in needs/wants so the split sums to 100% (P1-8).

**Exit test:** every window/surface agrees; July 2026 reports $5,025 spend and
$2,755 income; recurring bills lists utilities, not a vacation.

**What the $5,025 figure means — recorded, because the arithmetic only works one
way.** July 2026's tracked outflow is **$16,658.01**. The exit-test number is
that total less the two things that were never July's ordinary spending:
`17,760.24 − 11,633.00 − 1,102.23 = $5,025.01`. The $11,633.00 is the air
conditioner, bought 2026-07-23 and **split across both Sapphire cards**
($5,831.50 + $5,801.50); the $1,102.23 is the Pinellas charge that was reversed
the next day. Income is `3,856.59 − 1,102.23 = $2,754.36` — the same reversal,
removed from the other side of the ledger.

The headline therefore **stays $16,658.01**, because $11,633 genuinely left the
account and showing $5,025 as "what July cost" would be exactly the class of lie
this revamp exists to kill. $5,025.01 is surfaced as `summary.everyday_spend`
with the air conditioner named in `one_time_purchases`, and $2,754.36 as the
income. Read that way, the exit test passes as written.

**Exit test — run 2026-08-24 against the live backend. PASSES.**

| Clause | Result |
| --- | --- |
| Every window/surface agrees on July 2026 spend | `spending.summary.total_spend`, `reports.monthly_spend_trend[2026-07]`, `reports.month_comparison.latest_total` and the Ledger's own included rows all report **$16,708.01**. One distinct value, not four. |
| Row counts agree too | Ledger counts **112** rows in July; the spending summary reports 112. No id counted on one side and not the other. |
| July everyday spend | **$5,075.01** (`summary.everyday_spend`), with the $11,633.00 air conditioner named in `one_time_purchases` as two Costco rows of $5,831.50 and $5,801.50. |
| July income | **$2,804.36**, net of the $1,102.23 Pinellas clawback. |
| Recurring bills list utilities, not a vacation | Frontier, Duke Energy, T-Mobile, Waste Pro, P C Utilities, plus the declared Harbor Hills HOA. Zero vacation-shaped entries. |

**Both money figures land exactly $50.00 above the numbers recorded above, and
one row explains both.** The Airbnb line of 2026-07-03 (**$50.00**) is the
household's rental income. When the baseline was written it was carried as a
refund — a *negative* $50 against spend and absent from income. It is now filed
as income: $50 out of the spend total and $50 into the income total, from the
same row, in the same direction as the correction. So `16,658.01 + 50.00 =
$16,708.01`, `5,025.01 + 50.00 = $5,075.01` and `2,754.36 + 50.00 = $2,804.36`.
The recorded arithmetic is unchanged; rental income simply stopped being booked
as a discount on shopping. It was verified by running the baseline commit's own
code against today's database: `58b5bab34` reports the same 112 rows and the
same $16,708.01, so nothing about the totals moved — only that one row's flow.

**Two defects surfaced by running the test, both fixed before it was recorded:**
**P0-34** (the Ledger disagreed with every total by $71.03) and **P0-35** (the
reversal netting had never once fired on live data, leaving $1,102.23 in July
income). Both are written up in §3.

---

### Phase 2 — Review screen — **COMPLETE**
The screen in the artifact. All seven tasks landed.

2.1 ✅ Month selector · verdict line · In / Out / Left with prior-month and
    all-month-average comparators.
2.2 ✅ Category rows: actual vs cap, over/under netting to a total, bars capped at
    100% with a cap tick.
2.3 ✅ **Outlier isolation** (D2.3) — contribution-to-variance, "excluding largest
    purchase" view.
2.4 ✅ **New this month** (D2.4) — novelty detection on merchants with no prior
    history, clustered where they belong. **The owner half of D2's fourth
    sentence is still blocked** on attribution (91% "Family"); see D15.
2.5 ✅ **Affordability panel** (1.4) — Free to spend sits beside the month's
    verdict, showing the whole subtraction. The grade moved to the server, so
    the review screen and the Decision Board read one figure and one word for it.
2.6 ✅ **Phase-aware retirement block** (D13) — the block asks the question its
    phase calls for, and the boundary is the primary adult's age against the
    household's own `target_retirement_age`. **It found that the target age has
    arrived**: Elias turned 49 in January and the plan's retirement age is 49.
    One deliberate departure from D13's table: the accumulating-and-short row
    says the gap in *assets* rather than a required $/mo, because a required
    contribution needs a return assumption and the Retirement tab's projection
    stays the only one.
2.7 ✅ **Retire the second copies** — the Decision Board is deleted (its Free to
    spend card duplicated 2.5's, and its watch list re-printed the pace sentence
    directly above it), the allocation donut moved to **Investing → Holdings**,
    and the budget stat row went **ten tiles → three**. The board's one unique
    contribution, a 2-item refresh blocker list, became the **Waiting on you**
    card and now shows every item — 5 on live data. `useDecisionBoard` is
    `useMoneyOverview`, returning only what the surviving cards read.

---

### Phase 3 — Plan, funds, and alerts
3.1 ✅ **Income anchor** (D16) — the median of the last three **complete**
    months of ledger income, with those months listed beside it. Live:
    **$6,067/mo** from May/June/July 2026, against a saved take-home target of
    $6,283. A declared override is stored with the day it was declared and wins
    until cleared, and the measured median stays on screen underneath it; the
    card says so when a declaration has aged past 120 days or drifted more than
    15% from what arrives — but not in its first 60 days, because a declaration
    about a change the ledger has not seen yet is *supposed* to disagree with it.
    The $506.31/mo note income (P0-23) is **not** arriving: last paid
    2026-03-02, and classified `transfer_in` rather than income, so it could not
    have reached the anchor regardless (**P1-37**).
3.2 **Income-anchored cap setup** (D6): anchor (3.1) − savings (3.3) − sinking-fund
    accruals (3.4), distributed by historical shape, adjusted in one pass.
    Re-propose on material drift.
3.3 ✅ **Savings target as a phase-aware state** (D17) — four states, no grade:
    **active** (states what the amount leaves of the anchor), **paused** (with
    the day it was declared, the reason, and the income level that ends it),
    **restart due** (the anchor has reached that level), and **undeclared**,
    which is what a $0 target now reports instead of "on track". The trigger is
    evaluated against the 3.1 anchor — including a declared one — so a pause
    and the screen above it read one number. A pause with no trigger is told it
    will never end; naming an amount clears the pause in the same write.
3.4 ✅ **Sinking funds** (D18) — the four chosen funds, each priced from its own
    trailing spend over the **12 complete months** before the running one, with
    the derivation printed beside it. Live: Travel **$815/mo** ($9,785 over 12
    months), Home repair & appliances **$291**, Insurance/taxes/registration
    **$243**, Gifts & holidays **undeclared**. The largest purchase in a window
    can be set aside as one-time — Travel falls to **$639/mo** without the
    $2,111 Carnival charge, and both figures stay on screen. A declared amount
    is dated and keeps the trailing figure visible under it. Two judgements are
    stated rather than guessed: the **property tax is a tax, not a repair**,
    so a merchant match moves it out of Home and into the taxes fund (D23);
    and **Costco appliance purchases sit in Household**, which also holds
    grocery runs, so home repair does not count them and says so. This replaces
    the merchant inference that proposed $7,104/mo — more than take-home.
3.5 **Card commitments in Plan** (P0-20): annual-fee dates, welcome-bonus
    deadlines, balances owed. Card rotation is routine (D22), so adding a card
    must be a supported operation, not a migration.
3.6 **Web push via the existing PWA** (D19). Add `push` + `notificationclick`
    handlers to `frontend/public/sw.js`, subscription storage, per-device
    registration for Elias and Mariana separately. Reuse
    `spend_alert_service.py`'s evaluate → two-sink → dedupe-marker shape; swap
    transport only. **Both recipients are on Android** (Pixel 7 Pro, Galaxy S22
    Ultra), so there is no add-to-home-screen requirement and no install
    ceremony — the D11 iOS caveat is void.
3.7 **Alert kinds** (D19), in priority order: month projected over plan; novelty /
    outlier purchase; category at 100% of cap (not 85%); better-price-found
    (deferred until Phase 5 unit pricing lands). Existing card kinds continue
    alongside.

---

### Phase 4 — Item ↔ money linkage
Prerequisite for D2.4 owner attribution and for all per-item price work.

4.1 **Link purchase items to transactions** (U-4) — currently 81 of 3,067 (2.6%).
4.2 **Costco receipt parser** (§6b): item-number + abbreviated-name + qty-line-above
    + markdown-line-below format. **Gate ingestion on arithmetic**, not confidence:
    `Σ items − instant savings == SUBTOTAL` and `Σ line quantities == TOTAL NUMBER
    OF ITEMS SOLD`. All 5 sample receipts reconcile exactly — use them as fixtures
    ($884.23 / 68 items).
4.3 **Walmart parser hardening**: the fulfillment token sits between name and qty
    (`Fresh Hass Avocados, Each 16 shopped Qty 10 $8.20` → qty is 10, not 16);
    handle `weight adjusted` rows.
4.4 **Owner attribution** (D2.4) — today 91% "Family". **Depends on Phase 5.0**
    (identity propagation), which makes attribution a byproduct of who captured or
    uploaded rather than a dropdown nobody fills in. Manual override stays for
    corrections and for gift/shared purchases.

---

### Phase 5 — Prices subsystem (D10, D15)

5.0 **Identity propagation — do this first; it unblocks 4.4.**
    Migration: add a unique email column to `household_members`, seeded with the
    four Gmail addresses. Configure Cloudflare Access with Google as IdP.
    `middleware.ts` currently verifies `payload.email` and then discards it —
    forward it as a trusted header; resolve it to a `household_members` row
    server-side; stamp `owner_name` on every capture, upload and edit.
    **Scoping:** Access policy admits all four to the capture route, Elias +
    Mariana only to the rest of Money; enforce the same rule app-side off
    `household_members.role` so `child` cannot reach net worth, accounts, ledger
    or retirement.

5.1 **Fix package extraction** (U-2) with a confidence gate and manual override.
    Known failures: `Triple Omega 3-6-9 … 150 Ct` → parsed 54 count (2.8× off);
    `MoKo Case for Fire HD 10 Tablet` → 10 "tablets"; olive-oil *dispenser bottle*
    → 16 weight_oz.
5.2 **Unit normalisation** — one comparable base per shelf (mass / volume / count);
    honey currently `weight_oz` while olive oil is `volume_fl_oz`.
5.3 **Product-family / size-variant grouping** (U-3) — `_best_candidate()` only
    searches the same `product_id`, so cross-size and cross-brand comparison is
    architecturally impossible today.
5.4 **Materiality thresholds in $/month**, not a flat 10% (U-1) — the user's own
    worked example (32oz@$32 vs 64oz@$60 = 6.25%) is currently discarded.
5.5 **Costco item-number → product map** — the shelf tag carries item number, full
    description, package size *and* per-unit price. It is the join key between
    Costco receipts and the price matrix.
5.6 **Camera capture** for shelf tags — **four people, all phones** (D15).
    No camera input exists today (only `accept="image/*,.pdf"` on `AddCardDialog`,
    no `capture` attribute). Use
    `<input type="file" accept="image/*" capture="environment">`, which opens the
    camera directly in iOS Safari — **no PWA install needed to capture** (install
    is only required for push, D11). Kids open a URL. Every capture carries its
    owner via 5.0. Target OCR fields: Costco item number, full description,
    package size, shelf per-unit price, store.
5.7 **"Should I buy this?"** in-store screen: your usual unit cost, the other four
    stores after fees and membership, bigger-pack verdict, and how long it lasts at
    observed pace.
5.8 **Scraping as a routine** — adapters already exist for amazon/walmart/aldi/
    costco/publix with a unit-price-tuned focus query; currently 8 vendor quotes
    total. Turn into a scheduled backfill for routinely-purchased items.
5.9 Retire most of **Levers** (P1-10): $262/mo of modeled trim across 4,617px.
    Keep cut-candidates and deviations, folded into Review's "what changed".

---

### Phase 6 — Shopping habits (D15)
Only possible once 5.0 + 5.6 are collecting attributed captures alongside receipts.

6.1 **Considered-and-declined** — captured but never purchased. The only record of
    a good decision the household currently has no way to see.
6.2 **Impulse** — purchased with no prior capture, in categories where capture is
    the norm.
6.3 **Deliberation** — the same item captured repeatedly before buying.
6.4 **Pattern surfaces** — store and time-of-day habits, per-person basket
    composition, recurring overspend shapes, "we always overspend at Costco on
    Saturdays" class of finding.
6.5 Feeds Review's "what changed" and the alert stream, not a separate tab.
**Decide granularity for the girls before switching per-person reporting on** —
household-level habits and per-person habits are different products.

---

### Cross-cutting
- **Verification:** `st check --quick --changed-only`; `st service rebuild
  portfolio-ai`; live route/UI evidence via `st browser check`. Build/tests alone
  are not runtime evidence.
- **No sliding-window chips anywhere.** Complete months only, named.
- **No verdict from an unset input.** If the target is null, say so; never green.
- **Every headline number must be reachable to its rows** in one click.

---

## 8. Work log

| Date | Phase | What happened |
|---|---|---|
| 2026-08-22 | Audit | Read all 5 target panels + backend spend filters; queried live DB and all 4 spending windows; captured live screenshots of Dashboard/Budget/Levers/Ledger/Purchases. 18 findings recorded (5 P0). No project files changed. |
| 2026-08-22 | Grill Q1–Q4 | D1–D12 decided. Sub-audits: unit-price engine, receipt sources (Walmart/Costco), cash + sinking funds, prices subsystem, PWA push readiness, missing credit cards. New findings U-1…U-4, P0-20, P2-19. |
| 2026-08-22 | Receipts | User uploaded 13 PDFs (8 Walmart, 5 Costco). All `status: staged` — **deliberately not ingested**, per "don't change anything until approved". Verified both formats parse and self-reconcile. Costco: $884.23 / 68 items across 5 receipts. |
| 2026-08-22 | Proposal | Published visual proposal artifact (IA + Review screen mockup on real July 2026 data + Prices subsystem + disposition table). Awaiting approval. |
| 2026-08-22 | Grill Q5 + identity | D13 (phase-aware retirement block), D14 (sequencing: trust pipeline first, nothing dropped), D15 (family-wide capture; identity propagation). Four Gmail identities recorded. §7 restructured: new Phase 5.0 identity propagation ahead of 4.4 owner attribution; 5.6 rewritten for four-person capture; new Phase 6 shopping habits. Artifact republished with the family-capture section. Still nothing in the project changed. |
| 2026-08-22 | Security | Emails were committed to this **public** repo, then redacted from the plan doc and the artifact. History rewritten: `0a4add8b9` + `94e7cdfc3` squashed into `4073f9168`, force-pushed, branch protection restored. GitHub still serves the orphaned SHA until Support GCs it — request drafted. Real addresses now live in `.env.local` → `HOUSEHOLD_MEMBER_EMAILS`, gitignored. |
| 2026-08-22 | Phase 0 | Both Sapphire cards connected (P0-20 closed): `·3627` Elias, `·8054` Mariana on a second Chase item. The AC replacement is **split across both cards** — $5,831.50 + $5,801.50 on 2026-07-23 — clearing both $5,000 minimum spends with one purchase. `household_credit_cards` seeded with three rows; both welcome bonuses compute as `earned` from the ledger; the $95 annual fee posted 2026-08-02 on both, so the next one is 2027-08-02. Chase reports both cards as `Ultimate Rewards®`, so the registry gained an `identity_override` (label + owner) that survives evidence refresh, mirroring the classification override. The Cards tab had the same problem one level up — it rendered both Sapphires as the same row twice — so a card row now carries its account's owner and last four. MSR progress now excludes the issuer's own fees — the annual fee was counting as qualifying spend. The 63% `removed` rate was investigated and cleared: 11 true orphans, nine of them Plaid pending holds. |
| 2026-08-22 | Phase 0 cont. 2 | Three household answers landed and each exposed a defect underneath it. **HOA is annual** (0.11) — but `annual` was not a cadence the system had (**P0-28**): it was absent from `_RECURRING_CADENCES`, the multiplier and next-date tables, and the recurring query required two sightings, which six months of coverage can never show for a yearly bill. Added `annual`, added a merchant `cadence_override` that outranks inference (`scripts/household_declare_cadence.py`), and admitted declared merchants on one sighting. HOA now reports annual, $104.13, next 2027-02-17, confidence 1.0, recategorised `Bills` → `Home` with a merchant rule. **No delivery at Aldi/Amazon/Publix/Walmart** (0.12) — all four now carry a known $0 pickup fee with delivery deliberately unset, so "unset" means *not used* rather than *not yet asked*. **Fidelity 529s** (0.4) — the "no balance" diagnosis was wrong: SnapTrade had $14,929.22 for each all along, and the dashboard was filing them under taxable because the account summary read the *provider's* account type while the registry's `classification_override` was only ever read back inside the registry (**P0-29**). Education $6,793.17 → **$36,651.61**, taxable $635,774.29 → $605,915.85, net worth unchanged — proof it was a reclassification, not a revaluation. Also read the source PDF and retired D20's data-quality flag: the identical $14,363.57 is real (both accounts hold the same 177.153 CWIAX shares), not an extraction error. |
| 2026-08-22 | Phase 0 cont. | Receipts stopped double-counting the card feed (0.14): a new reconciliation pass retires a receipt whose spend the feed already carries, matching a **set** of charges rather than a twin — the $54.06 Walmart receipt is the $50.48 + $3.58 pair. Six receipts / $677.20 retired against seven charges, idempotent on a second pass, audit blob on every retired row. The same pass detects a receipt uploaded twice as two different files, on identical line items rather than a matching total. CSV imports fixed and made legible (0.15): a byte-order mark was silently voiding an entire Amazon export, and the review proposal now states rows-in-file / new / already-known / date range before approval. 0.3a and 0.10 closed by household answers (two separate closed Wells Fargo accounts; property tax paid at the 4% November discount). New finding **P0-27** — the receipt parser dates purchases to the day they were processed and merges several orders into one row; $313.20 is provably two May orders, and its $138.22 leg is already counted elsewhere. Fix lands in Phase 4.2. |
| 2026-08-22 | Phase 0 cont. 3 | **P0-27 re-diagnosed by reproduction, and it was not what the finding said.** Replaying the $313.20 document's structured data through the current `extract_transactions` yields **zero** transactions, not a mis-dated one: the review returns two orders whose `date`, `amount` and `merchant` are all null, structured extraction skips them, and the summary fallback finds no date either. The mis-dated rows are residue from an older path — every one of the four had `transaction_date` exactly equal to its document's upload date. So the live defect was **silence**: a receipt naming a merchant, a total and two orders produced no spend, no warning, and a document reported as applied. A receipt with no readable purchase date is now **held** — reason written to `date_quality_summary` beside the future-dated holds, `household_receipt_held_without_a_date` logged — because guessing the date is what made the four wrong in the first place. The four stale rows are retired (`removed`, never deleted) with `metadata.date_quality.reason = dated_to_the_day_the_file_was_read`; live receipt rows 15 → 5. Teaching the parser to read `"May 20, 2026 order"` off a Walmart order page stays with the Costco parser in Phase 4.2. |
| 2026-08-22 | Phase 0 closed | The review inbox went **17 → 12**, and every one of the 12 that remains is waiting on a person rather than on a bug. Three defects came out of clearing it. **P0-31**: four Wells Fargo statements had sat at `needs_review` since March saying *"Re-upload or add more context"* while their 41 transactions were in the ledger the whole time — only the PDFs had moved out from under the recorded path. The recovery pass already knew this and wrote the summaries, but never touched `status`, so the false alarm was permanent and the action it recommended was the one that could double-count applied spend. **P0-32**: the Amazon export reads 3,056 rows, finds 0 new, proposes nothing — and was pinned open waiting for an approval the system itself refuses (*"no explicit money-data changes to approve"*), because a general preference question about Amazon set `ambiguity_remaining`. **P0-33**: SnapTrade names both Fidelity rollover IRAs `Rollover IRA`; the list showed that name twice, one row at $9,596.29 and one at $0.00, with nothing to tell them apart — the same hand-correction the two Sapphires and the two 529s each needed, now closed as a class by falling back to the mask the registry already recorded and appending it only where labels actually collide. Net worth $1,530,455.18 before and after. **Phase 0's exit test was then run against the live backend and passes on all five checks** (liabilities $17,287.71; every account honest about freshness; `2144.48` finds the property tax; the Progressive premium appears once, as an expense; assets − liabilities reconciles). Phase 1 — the UI/UX work — is next. |
| 2026-08-22 | Questions closed | All 7 open questions in §5 resolved — 3 from the data, 4 by the user. New findings P0-21 (only two live feeds), P0-22 (same premium booked income *and* expense), P0-23 (spend filters delete real note income), P1-24 (19 labels / ~7 accounts), P1-25 (ledger can't search by amount), P2-26 (HOA ×6, miscategorized). Decisions D16–D23 added. Phase 0 expanded 6→13 tasks; Phase 3 rewritten. **Plan is ready to build.** |
| 2026-08-23 | Phase 1.1–1.3, 1.8 | **One month, one number, and bills that are actually bills.** 1.1/1.2: every surface now reads one canonical spend definition over **complete calendar months** — a month selector plus two fixed comparators (prior month, all-month average) replaced the 1M/3M/6M/12M chips (D3), and reversal pairing nets out the Jul 09 ↔ Jul 10 Pinellas charge that was inflating July income *and* July spend by $1,102.23 (`8e70c8136`). 1.8: statement merchants normalise, so `DIRECT DEBIT DUKEENERGY BILL PAY (Cash)` is Duke Energy and three spellings of Frontier are one merchant (`efc4ca2fb`) — which turned out to be **half of P0-3**, because a bill split across three spellings never accumulates enough sightings to prove a cadence. 1.3: the recurring detector was rebuilt on evidence rather than size. The old bar was two sightings ranked by `average_amount DESC`; the new one requires 3 sightings, a 55+ day span across 3+ calendar months, and 70% of both the gaps and the amounts inside 35% of the merchant's own median. Live result: **Frontier $34.99, Duke Energy $184.05, T-Mobile $151.58, Waste Pro $194.59 quarterly, P C Utilities $202.96 bimonthly, the declared HOA $104.13 annual**, then Netflix/Spotify/Get Fitness/YouTube Premium as subscriptions. Airbnb, Avis, Lufthansa and Costco are gone — and each fails for a different reason, which is why all three tests were needed: the Airbnb stay kept a *perfect* weekly cadence, just for a fortnight. `due_soon_bills_total` went from **$1,922 of phantom overdue vacation** to **$88.38** of four real obligations, and it stopped being computed from a truncated top-six list. P C Utilities is bimonthly rather than rounded to quarterly, which would have under-funded its sinking fund by a third. Gate green at each commit; 2442 backend tests, 232 frontend money tests. |
| 2026-08-23 | Phase 1.4 | **Safe to Spend became Free to spend, and it is now arithmetic on money.** The old figure was $1,283 and its binding constraint was `plan_residual` — monthly income *target* minus monthly plan *total* — so neither the $30,494.75 in the CMA nor the $17,287.71 owed across three Sapphires ever reached it, and a green **Safe** badge sat over a number the card disclaimed in the same breath. The check is now `cash − bills due − essentials still to come − sinking-fund balances − card balances`, shown as the full subtraction so the reader can check it: **30,494.75 − 88.38 − 1,290.32 − 0 − 17,287.71 = $11,828.34**. Four judgment calls are recorded in P0-2: the horizon is the rest of the month *or* the next fortnight, whichever reaches further (ask on the 30th and a pure month frame hides next week's bills); essentials still to come is the larger of what is left of the baseline and the remaining days at the baseline's own daily rate (August's $5,000 was already spent by the 23rd, and 'nothing left to buy' with eight days of groceries ahead is false); the result is **not floored at zero**, because a household that cannot cover what it owes needs the size of the hole; and inputs the system does not have are **named** rather than treated as zero — sinking-fund balances have no home until D7 lands in Phase 3, so the card says so. `plan_residual` and `discretionary_cap` are retired, `cash_after_commitments` is the only constraint left, and the status can be estimate, tight, hold or review — never *safe*. |
| 2026-08-23 | Phase 1.5 | **Three green verdicts deleted, one cause between them.** `on_track` and `Configured` were both *fall-through* values — reached by not failing a check rather than by passing one. `budget_snapshot.status` said `on_track` in the same payload as `pace_status: partial_plan` and `actual_monthly_spend 10,085` against a `monthly_plan_total 5,000`; it now returns **`plan_incomplete`** and says why (*"the monthly plan has no discretionary target, so total spending of $10,085/mo cannot be judged against it"*), or **`above_plan`** when a complete plan is overrun on the total even though every lane is individually inside its cap. `budget_readiness` reported all three lanes **Configured** with 17/19 category caps unset, because "Configured" meant *any* resolved value — and Lifestyle's was an inferred $4,073.26, which is just the discretionary spending the household already does, handed back as a cap. Lanes now distinguish set from inferred (**"Inferred from spending"**, status `partially_configured`, summary naming the lane, label tinted by state). `retirement_contribution_tracker` stops reporting `on_track` from a $0 target against $0 contributions (D13's defect) — a zero target is unset or paused, and D17 makes `paused` first-class in Phase 3. All three verified live on the running backend. |
| 2026-08-23 | Phase 1.6 | **The legend stopped showing the same category twice, because essentiality stopped being a field.** Transportation, Household, Travel and Home each appeared as two series, and the reason was structural rather than a bad row here and there: essentiality was stored as a *second free field* beside the category, so nothing obliged two "Transportation" rows to agree and each classifier decided independently. `_household_taxonomy.py` makes it a **function of the category** — one reading for each of the 23 curated categories, reachable only through `essentiality_for()`, and every classifier path now routes through it including Plaid's. Two of the four doublings turned out to be a single row each: **Home** held a $2,144.48 property tax and an HOA payment, its only "essential" rows, and those are what dragged the category between needs and wants depending which was read — `BILL_CONCEPTS` files property tax and HOA dues as **Bills**, after which Home is honestly discretionary. Raw Plaid labels are mapped instead of displayed ("General Services Insurance" → Insurance, "General Services Storage" → Household, "Bank Fees Other Bank Fees" → Bills). A category the household invented ("Girls") is **kept as written** and given a stable `mixed`, because flattening a real label into a fallback would be a worse lie than the doubling being fixed. Stored rows are repaired by `_canonicalize_stored_essentiality` inside `repair_transaction_system`, which rewrites essentiality only and never moves a transaction between categories. Live: **23 categories in 23 rows**, a second repair pass reports `essentiality_aligned = 0`, and `category_breakdown` returns six rows with no duplicate category and no Plaid leakage. It also sharpened 1.10 rather than easing it — Household is now one honest `mixed` series and the **largest** category at 24.6% of spend, so the bucket the needs/wants split hides is a quarter of the money. Gate green: 2457 backend tests. |
| 2026-08-23 | Phase 1.7 | **Every spend total now publishes what it left out, and the household can argue with it.** Three things were missing and only one was the string list: there was no **total** (nothing said what exclusion cost), no **reason a person could read** (the ledger said `cash_movement`, which names a category of decision rather than the decision), and no **way to disagree** — which is what made the first two matter, because a number you can neither check nor appeal has to be trusted rather than believed. `spend_exclusions` now publishes the counterpart to every total: **139 of 1,000 rows ($448,762)**, grouped by the rule that held them, with the merchants under each rule named. That number required widening past the ticket: rolling up only the literal string list gave **11 rows**, because most exclusions never reach the string list — they are dropped earlier for flow type. Eleven answers "why is this Zelle payment missing?" and leaves "why is my spend total smaller than my transactions?" unanswered, and the second is the question people actually arrive with. The appeal is a nullable `spend_override` column (migration `b2c3d4e5f6a7`), three-valued on purpose — `include` restores, `exclude` drops, clearing hands the row back to the rules, because an appeal that cannot be withdrawn is a worse trap than the filter it corrects. It is a **column, not a metadata key**: the spend predicate is built in SQL across several queries, and an override invisible to SQL would apply on the Ledger and not the Dashboard — the exact defect class this phase exists to remove — so `non_spend_sql_predicate` applies it centrally rather than leaving each query to remember. Only rules that match on **wording** invite an appeal; a row excluded for being income is not a guess about a string, and offering to overrule it would be offering the wrong argument. Verified live end to end: appealing the $400 ATM withdrawal of 2026-03-16 moved the roll-up to **138 / $448,362** — exactly $400 — reported it as "1 restored, $400.00" under Cash withdrawals, and flipped that row's own SQL verdict from dropped to counted; withdrawing it restored 139 / $448,762, and the live data is as it was found. One defect surfaced during verification and was fixed in the same task: "income" is reachable both as a flow type and as a category, so the card listed **"Money coming in" twice** — P1-7's doubled legend, reproduced one surface over — so rules are now grouped by meaning rather than by which rule matched. Gate green: 2,468 backend tests, 269 frontend money tests, 0 console errors on the live page. |
| 2026-08-24 | Phase 1.10 | **The split adds up to all of the money, not 90% of it.** Needs plus wants read $3,217 / $4,074 against $8,103 of average monthly spend, and the card called itself "Want vs need" while displaying needs first. The `mixed` bucket was computed nowhere and shown nowhere — the executive report summed the two named essentialities and never asked what the remainder was. `average_monthly_mixed` is now published as **the remainder** rather than as a third sum over a third label, so a category carrying some unforeseen essentiality surfaces as unclassified instead of vanishing, which is the failure mode itself. 1.6 made the slice bigger rather than smaller: with Household given one honest `mixed` reading it is the largest single category, so live the split is **needs $3,154 (30.8%) / wants $4,253 (41.6%) / mixed $2,823 (27.6%)**, summing to exactly $10,230.57 and **100.0%**. The hidden slice was a quarter of the money, not the $811 tail P1-8 describes. Card renamed **"Needs, wants and mixed"**, all three amounts and shares shown, and mixed explained rather than merely listed — a Household or Cash row can be a repair or a treat. Gate green: 2,470 backend tests, 273 frontend money tests, 0 console errors live. |
| 2026-08-24 | Phase 1.9 | **The confidence signal stopped moving opposite to the coverage.** `visibility_score` read **99 / "Strong household visibility"** beside a stale net worth, three accounts needing refresh and a spending feed gone quiet — because it was never a coverage measure. It was a **setup checklist**: 10 points for having told the system an income target, 5 for a retirement age, 10 for owning taxable assets. 80 of its 100 points were reachable without a single account being current, so answering questions raised "visibility" while the accounts behind the numbers went stale. `_household_coverage.py` measures observable facts in four published components — balances current (30), spending feeds reporting (30), known accounts connected (20), spend classified (20). Two weightings are deliberate opposites: balances go **by money**, because a $572,782 brokerage going stale and a $0 rollover going stale are not the same event; spending feeds go **by account**, because weighting those by balance would rank a card by what is owed on it rather than by how much spending flows through it. A component only reads 100 when nothing about it is wrong — money-weighting alone rounded $6,793 of stale balances against $1.56M to 100%, printing a perfect score directly above a line naming two stale accounts, the same anti-correlation one level down. Live: **91, "Strong coverage"**, with balances 99, feeds 75 (*Chase Sapphire Preferred ·8054 has gone quiet*), connected 94 (*Visa Credit ****4635 is not connected*), classified 100. The summary names the **weakest component rather than the score**, because "91%" tells nobody what to do. The old scorer, its label function and the freshness cap that existed to stop it claiming strength over stale accounts are deleted rather than left beside the new one, and the card publishes the working — a figure that cannot be broken down is how "99%" survived this long. Gate green: 2,479 backend tests, 277 frontend money tests, 0 console errors live. |
| 2026-08-24 | Phase 1 exit | **Running the exit test found the two defects it existed to find, and both were on the reversal/agreement axis the phase is named for.** Three surfaces agreed on July 2026 at **$16,708.01**; the Ledger — the one screen built to explain why a row counts — said $16,636.98 across 109 rows and marked three Amazon charges *excluded as a duplicate* (**P0-34**). The totals decide spend over transaction rows alone; the Ledger deduped transactions against imported receipt lines together, so an import row that never reaches a total itself could suppress a charge that does — P0-1 reproduced one screen down, on the screen a person opens to check P0-1. Two passes now: inclusion over transactions only, and the combined pass demoted to a **`duplicate_note`**, which is provenance rather than grounds to drop money. Ledger and totals now both report **112 rows / $16,708.01**, difference $0.00, no id counted on one side and not the other. Then the income half: `_household_reversal_pairs.py` opens by naming the July Pinellas deposit and its next-day clawback as its reference case, its unit tests pair exactly that, and on live data it returned **7 pairs, none in July** (**P0-35**). Candidates came from the spend rows plus the income rows — and an outflow filed under `Income` is dropped from spend by the `category:income` rule long before pairing runs, so the deposit was being offered a partner that had already been discarded. The charge was kept out of spend by that rule: the right answer for the wrong reason, while the deposit stayed in income permanently. Pairing now also reads outflows filed under income, on the same terms `_income_rows` reads the inflows, deduped by id — that one category deliberately, not the whole non-spend list, because the household's own transfers *are* same-amount opposite-direction twins by construction and must not annihilate each other, whereas an expense filed as income is a deposit being taken back. Pairs 7 → **8**; July income **$3,906.59 → $2,804.36**; July spend unchanged, because the charge was already out — it is now out for the reason that is true. **Exit test passes on all three clauses**: one distinct spend value across four surfaces, everyday spend **$5,075.01** with the $11,633.00 air conditioner named as two Costco rows, income **$2,804.36**, and recurring bills reading Frontier / Duke Energy / T-Mobile / Waste Pro / P C Utilities / HOA with zero vacation-shaped entries. Both money figures sit exactly **$50.00** above the recorded baseline and one row explains both: the 2026-07-03 Airbnb $50.00 was carried as a refund — a negative $50 against spend and absent from income — and is now filed as income, moving $50 in each direction. Confirmed by running the baseline commit's own code (`58b5bab34`) against today's database: same 112 rows, same $16,708.01, so nothing about the totals moved, only that row's flow. Gate green: 2,487 backend tests, 433 frontend tests, all surfaces verified live after rebuild. **Phase 1 closed.** |
| 2026-08-24 | Phase 2.1–2.2 | **The Budget screen stopped being a setup console and started answering the question.** D2's first two sentences -- "we're under budget overall" and "overspent on groceries but underspent on gas and overall we're under" -- were both unanswerable, and for the same reason: every row was judged against `average_monthly_spend`, the run-rate across all covered months. A six-month average that no single month resembles cannot be over or under anything, and the badge saying **Confirmed cap** sat directly above a breach figure computed from a different period. Rows now read the reported month, the badge and the variance agree, and the column that said *Observed / mo* says **This month** with the run-rate demoted to a subtitle. The bar under each row **stops at the cap**: a category at 300% draws the same full bar as one at 101% and the overflow is stated in money, because a bar that runs off the end makes the biggest breach the least legible row on the screen. `HouseholdBudgetVerdict` publishes the netting once on the server -- `over_total`, `under_total`, and the variance they net to -- and both the footer and the headline restate it rather than re-summing rows, so the sentence at the top of the screen cannot drift from the table under it. The verdict is measured against **confirmed caps only**: a suggested cap is drawn from the household's own spending, and grading a month against that would put every month roughly on plan by construction. Past 25% of spend running uncapped it **refuses a verdict** and says how much is unjudged, which is what August live now reads -- *"Only $1,019 of August 2026's $7,433 has a cap, so there is no overall verdict yet. $6,414 ran through 9 uncapped categories. Of what is capped: 2 under by $881 (most of it Groceries)."* June, which has more of its spend capped, reads *"1 over by $1,128 (most of it Groceries) · 1 under by $27 (most of it Gas)"*. Building it surfaced **P1-36**: `suggest_essentiality` still held its own three-name list and could never return `mixed`, and `load_item_splits` grouped on the essentiality stored per item -- so Household arrived as two rows, `mixed` $12,985.32 from transactions and `discretionary` $71.03 from three Amazon charges' items, and a cap on Household would have been compared against whichever half the reader was looking at. Splits now take their essentiality from their category, and the repair pass reaches `household_purchase_items`: 3,042 rows aligned, 0 on a second pass, July unchanged at $16,708.01 with Household one row at $13,056.35. Gate green: 2,494 backend tests, 444 frontend tests, verdict line verified on the live page with 0 console errors. |
| 2026-08-24 | Phase 2.3 | **Two true sentences about July that point opposite ways, and the screen now says both.** July spent **$3,004 more** than June; July's everyday spending was **$8,629 less**. Showing only the first turns a household that bought an air conditioner into a household that overspent, which is the same class of lie as the sliding windows. `spend_variance` publishes both, plus contribution-to-variance per category. Three judgment calls are recorded in the module. The comparator month gets **its own** outliers removed too -- otherwise a June carrying its own $9,000 roof would flatter July for free. Drivers are measured on the **everyday** rows only: a category whose entire movement is the purchase just set aside did not change its habits, and naming it as a driver would contradict the line directly above it (July's Household would otherwise lead the list at +$12,827, which is the air conditioner again). And the share is divided by the **magnitude** of the change rather than the signed total, because dividing by a negative made Travel's $5,157 *drop* read as "+60%" in a month that fell. Live July reads: Travel −$5,157 (−60%), Groceries −$1,915 (−22%), Household +$1,194 (+14%), Insurance −$756 (−9%). Minimum $25 to be named and at most six named movers -- everything stays in the totals, but a "what changed" list of twenty rows is the category table the reader already has. Gate green: 2,500 backend tests, 449 frontend tests, 0 console errors on the live page. |
| 2026-08-24 | Phase 2.4 | **34 unfamiliar names became two trips.** July 2026 has 44 charges at 34 merchants the ledger has never seen. As a list that is 34 mystery lines and reads like a fraud report; grouped by date it is **23 new places between the 2nd and the 13th ($1,233)**, **8 more between the 19th and the 28th ($260, mostly Personal Care)**, and two loners. The gap threshold is **2 days** and that is load-bearing: at 3 days the whole of July collapses into a single cluster, which is the same failure as not clustering at all. Clusters are built from **dates alone** — the Plaid metadata on these rows carries an item id and a transaction id and nothing else, so the card says "23 new places, 2-13 July" rather than naming a country it cannot source. One bug caught in review before it shipped: groups below the 3-merchant threshold were emitting a single entry labelled after the first merchant, which filed Meyer Feinkost's $23.44 under "Hsr K" — worse than not grouping at all. Sub-threshold groups now emit one entry per merchant. This closes **half** of D2's fourth sentence; the owner half ("these 4 items Mariana bought") is still blocked on attribution being 91% "Family", which is D15's problem and is recorded as such rather than faked. Gate green: 2,507 backend tests, 454 frontend tests, 0 console errors live. |
| 2026-08-24 | Phase 2.5 | **The affordability figure moved to the screen where the month is judged, and stopped being graded twice.** Free to spend was on the Decision Board, one tab from the review screen, so the screen that says "August came in over your caps" could not say whether there was money to act on it. It now sits beside the verdict as the whole subtraction rather than a single confident number: **30,495 − 88 − 1,129 − 17,336 = $11,941**, each line a thing the household can go look at. Two things moved to the server while doing it. The word over the figure (`estimate` / `tight` / `hold`, never *safe*) was a `weekendSpendAllowance < 150` ladder inside a React hook; putting the same dollar amount on a second screen would have meant a second copy of that threshold, so `build_affordability` now returns `status`, `headline` and `detail` and both surfaces read them. And the stale-data treatment was replacing the explaining sentence with "Stale account data; refresh before relying on this." while still printing the number — the worst of both. The card now always shows the figure and what it means, and names the input that is behind: **"Cash and card balances need a refresh."** / **"This month's essentials are still an estimate."** Live on both surfaces at $11,941 with identical inputs. |
| 2026-08-24 | Phase 2.6 | **Asking the retirement question properly answered it: the plan's retirement age has already arrived.** The old block graded contribution compliance and reported `on_track` from a $0 target against $0 contributions — a pass earned by having no inputs — while net worth grew at roughly 66× the $300/mo it was measuring. It now picks its question from the primary adult's age against `target_retirement_age`, both read live: **Elias turned 49 in January and the plan's retirement age is 49**, so the block is in drawdown and asks whether the withdrawal holds. It does not: **$10,231/mo of actual spending against the $6,428/mo that $1,542,811 of investable assets supports at the household's own recorded 5% rule**, with the plan assuming $7,500/mo — D13's two-way link, found on a budget screen exactly as predicted. Three things it refuses to do. It will not call that a *withdrawal* verdict: no account in the ledger is labelled as an IRA, 401(k), Roth or HSA, so whether a drawdown has actually started is invisible and the block says so rather than reading a $0 as a measurement. It will not state a required $/mo contribution in the accumulating-and-short phase, because that needs a return assumption and the Retirement tab's projection stays the only one — the gap is stated in **assets** ($257,189) instead. And with no birth year or no target age it returns `phase_unknown` rather than picking a phase. Ages come from `_split_members`, borrowed from the retirement planner rather than re-derived, so the boundary cannot move on one screen and not the other. The block renders on the review screen and in the planning drawer from the same object. |
| 2026-08-24 | Phase 2.7 | **Deleted the screen that answered the same questions a second time, and Phase 2 closed with it.** The Decision Board's four cards were each a duplicate by the time 2.5 landed: Free to spend was already on the review screen as the full subtraction, and the board's own watch list re-printed `paceDetail` — the exact sentence rendered three inches above it in the same card — which is why the panel test had been asserting *two* copies of "Month-to-date spend is ahead of plan by $500." Both copies are gone; the sentence is printed once. The allocation donut moved to **Investing → Holdings**, because where the assets sit is an Investing question and Money's job is what came in and what went out; it took its state with it (`AccountAllocationSection` self-fetches and owns `selectedAssetGroup`), so nothing had to drag the old hook across. Moving it surfaced one thing worth fixing: inside a tab panel the donut mounts for a frame at zero width, and recharts answered that with `width(-1) and height(-1)` on the console — the chart now waits for a measured box, and `/portfolio?tab=holdings` reports 0 errors, 0 warnings, donut 509×288. The budget stat row went **ten tiles → three** (Unknown purchases · Caps waiting on you · Connected MTD spend), which on live data reads *0 purchases to categorize*, *17 suggested rows not accepted yet · $6,650*, and *$7,488 Plaid/SnapTrade through Aug 24, 3 pending transactions included ($145)*. **One thing the board carried that nothing else did**: `dashboard.inbox` reached the UI only through its 2-item "Refresh blockers" list, so deleting the board would have silently removed the only place those items appear. They are now the **Waiting on you** card on the Budget screen, uncapped — **5 items** on live data, each naming what it blocks ("Blocks net worth"), where 2 showed before. `useDecisionBoard` became `useMoneyOverview` and returns only what the surviving cards read. Gate green: 2,523 backend tests, 470 frontend tests, ARCH/ruff/ty/biome/tsc clean; `/money?tab=dashboard`, `/money?tab=spending`, `/portfolio?tab=holdings` all verified after rebuild with 0 console errors and 0 warnings. **Phase 2 closed.** |
| 2026-08-24 | Phase 3.1 | **The plan stopped being priced off a number nobody receives.** The household's saved take-home target is **$6,283/mo**; the last three complete months brought in **$6,067, $7,985 and $2,804**. Everything Phase 3 caps — savings, sinking funds, category budgets — divides up that first number, which is $216/mo above what a normal month actually delivers and $3,479 above July. The anchor is now the **median of the last three complete calendar months** of ledger income: **$6,067/mo**, with the three months listed on the card so the arithmetic can be checked against a bank statement in a minute. A median rather than a mean, deliberately, and the ledger shows why: January and February hold $15,244 and $13,417 against a still-running August at $3,205, and a mean over the record is $7,750 — a cap the household could not have paid in four of the last eight months. The running month is never counted; nothing is reported until at least one complete month exists, and with none the card says so rather than showing $0. It reads the ledger's own `income_totals_by_month` — the same collapse the Budget screen reports, reversals netted and brokerage activity out — so the anchor and the month on screen cannot disagree about what income even is: July arrives as $2,804.36, already net of the Pinellas clawback. **A declared anchor** ("SummitFlow starts next month") is stored with the **day it was declared** and outranks the median, but never erases it: both sit on the card together. It is called out as stale after 120 days, or when it has drifted more than 15% from what arrives — but not in its first 60 days, because a declaration about a change the ledger has not seen is supposed to disagree with the months before it, and flagging that immediately would make the feature useless for the one case it exists for. An **undated** declaration is always flagged: it cannot be told apart from one that stopped being true. Verified live end to end: declaring $9,000 dated today flips the card to *Declared* with the measured $6,067 still under it, and clearing it returns to *Measured* — the profile row is back to null. **P1-37**, from confirming the plan's open question: the **$506.31/mo note income** (P0-23) is not arriving — last payment **2026-03-02**, the receiving account closed in March — and every one of those rows is classified `transfer_in`, not income, so it could not have reached the anchor even if it had continued. Reclassifying it needs to know Michael Wiley is not the household, which is the D15 ownership question; the dated declaration covers the gap in the meantime. Gate green: 2,536 backend tests (13 new), 478 frontend tests (8 new), ARCH/ruff/ty/biome/tsc clean; `/money?tab=spending` verified after rebuild with 0 console errors and 0 warnings. |
| 2026-08-24 | Phase 3.3 | **A $0 savings target stopped counting as keeping up.** The live profile carries `monthly_savings_target: 0.0`, and zero trivially keeps up with zero — a pass awarded for having no plan, the same shape of answer the retirement block gave before 2.6, and it sat on screen while net worth grew roughly $19,800/mo on its own. Saving is now one of four declared states. **Active** states what the amount leaves rather than grading it: $1,500/mo *"leaves $4,567 of the $6,067 anchor for everything else"*, and a target above the anchor is told that one of the two is wrong instead of being quietly accepted. **Paused** carries the day it was declared, the reason, and the income level that ends it — *"Paused since Feb 01, 2026. On unemployment while SummitFlow is pending. Restarts at $8,000/mo of income. A normal month currently brings in $6,067 — $1,933 short."* **Restart due** fires when the anchor reaches that level and asks for an amount. **Undeclared** is what the live household reads today: *"The savings target is $0, which is not a plan."* Two deliberate refusals. A pause with no restart trigger is told outright that nothing will ever prompt it to resume, because a pause that cannot end is just a plan to stop saving with extra steps. And nothing here grades contributions: the retirement block already refuses to read $0 of visible retirement activity as $0 contributed (2.6), and repeating that mistake one card over would undo it. The trigger is evaluated against the **3.1 anchor**, declared value included, so the pause and the card above it cannot disagree about what income is; naming an amount clears the pause in the same write, so the two states can never both be on. Verified live end to end through the API: paused at an $8,000 trigger reads *paused, $1,933 short*; lowering the trigger to $5,000 flips it to *Time to resume* on screen; clearing returns the profile to its original state (target $0, no pause). Gate green: 2,545 backend tests (9 new), 485 frontend tests (7 new), ARCH/ruff/ty/biome/tsc clean; `/money?tab=spending` verified after rebuild with 0 console errors and 0 warnings. |
| 2026-08-24 | Phase 3.4 | **The sinking funds stopped being an inference over merchants and became four numbers with their working shown.** What they replace proposed **$7,104/mo** of buffers — more than the household takes home — by treating any merchant it saw on a rhythm as an obligation, and none of it ever reached the UI. The four funds are now the household's own choice (D18), each priced from its own trailing spend over the **12 complete months before the running one** — never the current month, which would quote a fund at a third of its rate in early August. Live: **Travel $815/mo** ($9,785 over 12 months), **Home repair & appliances $291**, **Insurance, taxes & registration $243**, and **Gifts & holidays undeclared** — nothing in this ledger is filed as gifts, they sit inside Retail, so that fund asks for an amount instead of reporting $0/mo as though nothing were owed. Every figure prints the subtraction that produced it, so a number that looks wrong can be checked rather than argued with. The **largest purchase in each window is droppable**: Travel falls to **$639/mo** without the $2,111 Carnival charge, and the card keeps both figures — one cruise should not set a monthly contribution for a year, but hiding that it happened is worse. Two judgements are made out loud instead of guessed. The **$2,144.48 Pinellas County Tax Collector** row is filed under Home; it is a *tax*, not a repair, so a merchant match claims it for the taxes fund and it can only fund one buffer (D23's obligation, finally landing somewhere). And the **$11,633 air conditioner is filed under Household**, the mixed bucket that also holds Costco grocery runs, so home repair does not count it — the card says so and offers a declared amount, rather than quietly funding groceries as appliances. Overrides live in a new `household_sinking_funds` table holding only what the ledger cannot derive: a dated declaration and the one-time flag. The monthly figure is never cached — it is recomputed from `spend_rows_for_window`, the same collapse every total uses, so a fund cannot drift from the purchases it claims to be based on. Verified live end to end: setting aside the cruise moved Travel to $639 on screen and back to $815 when counted again; a $150 gifts declaration read *Declared, 2026-08-24* and cleared back to *Needs an amount*. Both verification writes were reverted. Gate green: 2,554 backend tests (9 new), 492 frontend tests (7 new), ARCH/ruff/ty/biome/tsc clean; `/money?tab=spending` verified after rebuild with 0 console errors and 0 warnings. |
