# Money Workspace Revamp — Plan & Working Doc

**Status:** PHASE 0 COMPLETE — exit test passes (§7). 15 of 16 tasks landed;
0.13 (the staged receipts) waits on the household's approval and on the
Costco/Walmart order-page parser in Phase 4.2. **Phase 1 is next, and it is the
UI/UX work.**
**Owner:** Elias Leslie
**Started:** 2026-08-22
**Last updated:** 2026-08-22 (Phase 0 closed: the review queue no longer asks
for decisions nobody can make, and two accounts sharing one name are told apart)

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
> update its Phase 0 status key and the §8 work log, then re-order the queue.

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

**Phase 0 is complete and its exit test passes** (the table is at the end of
§7's Phase 0 block). The next session is the UI/UX work.

1. **Start Phase 1 — one trustworthy number pipeline.** This is the reason five
   panels give four different answers to "what did we spend." Everything before
   it was data repair; this is the first thing the household will *see* change.
   Read §7 Phase 1 for the tasks, and D3 for the decision to drop the sliding
   1M/3M/6M/12M chips in favour of complete calendar months.

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
- **P0-3** the recurring detector's *inferred* labels remain wrong — Costco reads
  "likely weekly, $61,113/yr annualized". Declaring a cadence (0.11) routes
  around it for known bills; repairing it is Phase 1.
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

### P0-4 — Headline verdicts contradict the arithmetic under them

`budget_snapshot`: `status: "on_track"`, summary *"The current monthly spending
profile is inside the available budget guardrails."*
Same object: `actual_monthly_spend 8,103` vs `monthly_plan_total 5,000` vs
`monthly_income_target 6,283`. Also `pace_status: "partial_plan"` — two
different verdicts in one payload.

`budget_readiness`: `status: "ready_for_budgeting"`, all three lanes
("Essentials", "Lifestyle", "Savings") reported **"Configured"** — while 17 of
19 categories have no cap at all.

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

### P1-8 — Needs/wants split doesn't add up

Decision Board: **$3,217 / $4,074**, badge *"Wants leading 50%"*, body *"(50% vs
40%)"*. 3,217 + 4,074 = 7,292, but average monthly spend is 8,103 — the $811
`mixed` bucket is invisible, so the two shares sum to 90% and the card labels
itself "Want vs need" while displaying needs first.

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

### Phase 1 — One trustworthy number pipeline
Kills P0-1, P0-2, P0-3, P0-4, P0-5, P1-6, P1-7, P1-8, P1-13.

1.1 **One canonical spend definition** shared by every surface. Report only
    **complete calendar months** and name which months were used. Remove the
    1M/3M/6M/12M sliding chips (D3) — replace with a month selector plus two fixed
    comparators (prior month, all-month average).
1.2 **Reversal pairing.** Detect same-amount / opposite-direction / same-merchant-
    token rows within N days and net them out. The Jul 09 ↔ Jul 10 Pinellas pair
    is the reference case: it inflates July income *and* July spend by $1,102 and
    makes Bills read $1,497 instead of ~$395.
1.3 **Rebuild recurring-bill detection** (P0-3). Require true periodicity + amount
    stability. Exclude travel/retail merchants from `commitment_type: "bill"`.
    Must detect Duke Energy, T-Mobile, Frontier, P C Utilities, Waste Pro — and
    must not detect Airbnb, Avis, Lufthansa, Costco.
1.4 **Rebuild `safe_to_spend`** as a cash-based affordability check (D8):
    `cash − bills actually due − rest-of-month essentials − committed fund
    balances − card balances outstanding`. Retire the `plan_residual` constraint
    and the green "Safe" badge over a disclaimed number.
1.5 **Delete vacuous verdicts.** No `status: "on_track"` derived from unset inputs
    — applies to `budget_snapshot`, `budget_readiness` ("all lanes Configured"
    with 17/19 caps unset) and `retirement_contribution_tracker` (D13).
1.6 **Fix the taxonomy** (P1-7). One essentiality per category; collapse the
    duplicate Transportation/Household/Travel series; map Plaid leakage
    ("General Services Storage/Insurance") into the curated set.
1.7 **Make exclusions visible and appealable** (P1-6). The hardcoded string list in
    `_household_spend_filters.py` ("zelle to", "atm withdrawal", …) gets a UI
    surface, a total, and per-row override.
1.8 **Merchant normalisation for statement rows** (P1-12) — "DIRECT DEBIT
    DUKEENERGY BILL PAY (Cash)" → "Duke Energy".
1.9 Replace `visibility_score: 99` with a coverage measure that tracks actual
    account coverage (P1-13).
1.10 Show the **mixed** bucket in needs/wants so the split sums to 100% (P1-8).

**Exit test:** every window/surface agrees; July 2026 reports $5,025 spend and
$2,755 income; recurring bills lists utilities, not a vacation.

---

### Phase 2 — Review screen
The screen in the artifact. Build only after Phase 1 exits.

2.1 Month selector · verdict line · In / Out / Left with prior-month and
    all-month-average comparators.
2.2 Category rows: actual vs cap, over/under netting to a total, bars capped at
    100% with a cap tick.
2.3 **Outlier isolation** (D2.3) — contribution-to-variance, "excluding largest
    purchase" view.
2.4 **New this month** (D2.4) — novelty detection on merchants with no prior
    history, clustered where they belong (the July El Salvador trip = 8 merchants,
    $385, one cluster — not 8 mystery lines).
2.5 Affordability panel (1.4).
2.6 Phase-aware retirement block (D13).
2.7 Retire: Decision Board's four cards, the allocation donut (→ Investing), the
    ten-tile budget stat row (→ three).

---

### Phase 3 — Plan, funds, and alerts
3.1 **Income anchor** (D16): trailing 3-month **median** of deposits, recomputed
    monthly, with a dated manual override that wins until cleared. Show both
    values side by side so the override is never silently stale. Confirm whether
    the $506.31/mo note income (P0-23) is still arriving and include it if so.
3.2 **Income-anchored cap setup** (D6): anchor (3.1) − savings (3.3) − sinking-fund
    accruals (3.4), distributed by historical shape, adjusted in one pass.
    Re-propose on material drift.
3.3 **Savings target as a phase-aware state** (D17): `paused` is a first-class
    state with a user-set restart trigger on the trailing income median — not a
    $0 target silently reporting "on track".
3.4 **Sinking funds** (D18): the four user-selected funds — Travel, Home repair &
    appliances, Insurance/taxes/registration, Gifts & holidays.
    **Amounts auto-derived**: trailing 12 months of that category after
    novelty/reversal cleanup, top one-time outlier droppable, ÷12. Show the
    derivation inline ("$5,012 of travel over 12 months → $418/mo") so it is
    auditable. Dated manual override per fund with the auto value still visible.
    Seed the pre-feed obligations from 0.10 or the averages will under-fund.
    This replaces the old merchant-inference, which proposed $7,104/mo — more
    than take-home.
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
