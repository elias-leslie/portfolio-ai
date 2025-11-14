# Task List: Paper Trading Engine

**Source**: User request via context exploration
**Complexity**: Complex
**Effort**: MEDIUM-HIGH (2-3 weeks total: 3-5 days MVP + 2-3 weeks full engine)
**Environment**: Local Dev
**Created**: 2025-11-14
**Dependencies**: 
- Task 0060 (CLI agents) - agents will execute paper trades autonomously
- Task 0062 (gap detection) - paper trading validates strategies
- Task 0063 (backtesting) - shares portfolio state tracking logic

---

## Summary

**Goal**: Build a paper trading engine that allows AI agents and users to execute simulated trades, track performance, and validate investment strategies autonomously before committing real capital.

**Approach**: Two-phase delivery:
- **Phase A (Quick MVP)**: Functional but minimal system running during vacation (3-5 days)
  - Cash management, instant order execution, basic transaction log
  - Agent tools for autonomous watchlist management and trade creation
  - Reuse existing infrastructure (60-70% complete)
- **Phase B (Full Engine)**: Production-ready system after vacation (2-3 weeks)
  - Realistic fill simulation, advanced order types, position sizing rules
  - Risk management, performance attribution, visualization

**Scope Discovery**: Not required (exploration complete - 60-70% infrastructure exists)

**Autonomous Behavior & Limits**:
- **Complete Autonomy**: Agents have full autonomy to create/manage paper trades within limits
- **Watchlist Management**:
  - Agents CAN add tickers autonomously (unlimited within rate limits)
  - Agents CAN remove ONLY tickers they added (validated via `added_by` field)
  - Agents CANNOT remove user-added tickers (validation enforced in API)
  - Removal criteria: Time-based (min 30 days holding) + performance-based (strategy invalidated)
- **Cash Management**:
  - Default initial cash: $100,000 per paper trading account
  - Max position size: 5% of cash per trade ($5,000 max per position)
  - No margin/leverage (cash only)
  - Insufficient cash → trade rejected, agent notified
- **Trade Execution**:
  - Phase A: Instant fills at closing price (no slippage, no spread)
  - Phase B: Realistic fills with slippage/spread modeling
  - All trades logged to `paper_trade_transactions` table (audit trail)
- **Risk Guardrails**:
  - Max open positions: 20 (prevent over-diversification)
  - Stop loss: 2x ATR (automatic exit protection)
  - Max holding period: 60 days (force exit if no signal)
  - Max daily trades: 10 (prevent churning)
- **Performance Monitoring**:
  - Agents track P&L per strategy (link to backtest_run_id)
  - Poor performing strategies (Sharpe < 0, win rate < 40%) flagged for review
  - Agents can autonomously close positions if strategy invalidated
- **Git Workflow**:
  - Daily commits: `reports/autonomous/{YYYY-MM-DD}-paper-trades.json`
  - Includes: Open trades, closed trades, P&L summary, strategy performance
  - Commit format: `[AUTONOMOUS] {date} - Paper Trading - {num_trades} trades, {P&L}% return, {num_open} open`

---

## Infrastructure Analysis

**Existing (60-70% complete)**:
- ✅ `idea_outcomes` table - Complete paper trade lifecycle tracking
- ✅ Paper trading portfolio calculations - `paper_trading_portfolio.py` (354 lines)
- ✅ Trade calculations - `trade_calculations.py` (197 lines) - Stop loss, target price extraction, exit conditions
- ✅ Order creation - `paper_trading_orders.py` (201 lines) - Create trades from agent ideas
- ✅ P&L calculation - Long/short position support, return % calculation
- ✅ Exit logic - Target hit, stop loss hit, time limit expiration
- ✅ Daily update task - Scheduled Celery task at 21:30 UTC (4:30 PM ET)
- ✅ Agent tools - `store_idea` tool automatically creates paper trades
- ✅ Portfolio accounts table - Ready for cash balance extension
- ✅ Watchlist API - Add/remove ticker endpoints exist

**Missing (30-40%)**:
- ❌ Cash balance tracking (no cash column in portfolio_accounts)
- ❌ Order system (instant fills only, no order states)
- ❌ Agent watchlist tools (add_ticker, remove_ticker, create_paper_trade)
- ❌ Transaction log (no audit trail for trades)
- ❌ Ownership tracking (can't distinguish agent-added vs user-added tickers)
- ❌ Manual paper trade creation API
- ❌ Realistic fill simulation (slippage, spread, liquidity)
- ❌ Advanced order types (market, limit, stop)
- ❌ Position sizing rules (equal weight, volatility-adjusted, Kelly)
- ❌ Risk management (max position size, max leverage, correlation limits)
- ❌ Performance attribution (what worked, what didn't)
- ❌ Visualization (P&L chart, trade log, performance metrics)

---

## Tasks

### Phase A: Quick MVP (3-5 days) - Functional During Vacation

#### 0.0 Database Schema Changes

**Effort**: LOW (10%)

- [ ] 0.1 Add cash balance to portfolio_accounts
  - Migration: `042_paper_trading_cash.sql`
  - Add `cash_balance DOUBLE PRECISION DEFAULT 100000.0` to portfolio_accounts
  - Add `initial_cash DOUBLE PRECISION DEFAULT 100000.0` for reset tracking
  - Add index on account_type for paper trading account queries
- [ ] 0.2 Create transaction log table
  - Table: `paper_trade_transactions`
  - Columns: id (PK), trade_id (FK idea_outcomes), transaction_type (ENTRY/EXIT), ticker, shares, price, amount, cash_before, cash_after, timestamp, notes
  - Index on trade_id, ticker, timestamp
- [ ] 0.3 Add ownership tracking to watchlist_items
  - Add `added_by TEXT DEFAULT 'user'` to watchlist_items (user/agent_run_id)
  - Add `added_at TIMESTAMP WITH TIME ZONE` (when added)
  - Index on added_by for filtering agent-added tickers
- [ ] 0.4 Extend idea_outcomes for position sizing
  - Add `shares INTEGER` (number of shares traded)
  - Add `entry_amount DOUBLE PRECISION` (total entry cost)
  - Add `exit_amount DOUBLE PRECISION` (total exit proceeds)
  - Add `realized_pnl DOUBLE PRECISION` (absolute P&L in dollars, not just %)

#### 1.0 Cash Management System

**Effort**: LOW-MEDIUM (15%)

- [ ] 1.1 Create CashManager class (`backend/app/analytics/cash_manager.py`)
  - `get_cash_balance(account_id: str) -> float` - Fetch current cash
  - `deduct_cash(account_id: str, amount: float, reason: str) -> bool` - Deduct for trade entry
  - `add_cash(account_id: str, amount: float, reason: str) -> bool` - Add from trade exit
  - `check_sufficient_cash(account_id: str, amount: float) -> bool` - Pre-trade validation
  - All operations log to transaction table
- [ ] 1.2 Initialize paper trading account with default cash
  - Create migration helper to add paper trading account if not exists
  - Default: $100,000 starting cash
  - Account type: "paper"
  - Name: "Paper Trading Portfolio"
- [ ] 1.3 Integrate cash checks into order creation
  - Modify `create_paper_trade_from_idea` to check cash before creating trade
  - Calculate max shares affordable: `cash_balance / entry_price`
  - Use simple equal-weight position sizing: `cash_balance * 0.05` per position (5% max)
  - Reject trade if insufficient cash (log warning)

#### 2.0 Agent Watchlist Tools

**Effort**: MEDIUM (25%)

- [ ] 2.1 Create `add_ticker` tool definition
  - Tool name: `add_ticker`
  - Schema: ticker (string), reason (string), expected_return_pct (float), time_horizon_days (int)
  - Description: "Add a ticker to the watchlist for monitoring. Use when you discover an interesting opportunity."
  - Tool tracks added_by = agent_run_id automatically
- [ ] 2.2 Create `remove_ticker` tool definition
  - Tool name: `remove_ticker`
  - Schema: ticker (string), reason (string)
  - Description: "Remove a ticker you previously added after idea invalidated. You can only remove tickers YOU added."
  - Validation: Only allow removal if added_by = current agent_run_id
  - Error if trying to remove user-added ticker
- [ ] 2.3 Create `create_paper_trade` tool definition
  - Tool name: `create_paper_trade`
  - Schema: ticker (string), action (buy/sell), thesis (string), target_price (float, optional), stop_loss_pct (float, optional)
  - Description: "Create a paper trade to test your investment thesis. Trade will be tracked with automatic exits."
  - Automatically creates agent_idea + paper trade entry
  - Uses cash management to calculate affordable shares
- [ ] 2.4 Implement tool executors in AgentTools class
  - `execute_add_ticker(ticker, reason, expected_return_pct, time_horizon_days) -> dict`
  - `execute_remove_ticker(ticker, reason) -> dict`
  - `execute_create_paper_trade(ticker, action, thesis, target_price, stop_loss_pct) -> dict`
  - All tools log to transaction table
  - All tools check ownership before removal
- [ ] 2.5 Wire tools into agent runtime
  - Add tool definitions to Discovery Agent
  - Add tool definitions to Portfolio Analyzer
  - Register executors in AgentTools initialization
  - Update agent prompts to mention new capabilities

#### 3.0 Order Execution Engine (Simple)

**Effort**: LOW-MEDIUM (15%)

- [ ] 3.1 Create OrderExecutor class (`backend/app/analytics/order_executor.py`)
  - `execute_market_order(ticker, action, shares, account_id) -> dict` - Instant fill at current price
  - Uses PriceDataFetcher to get current price
  - Updates cash balance via CashManager
  - Logs transaction to paper_trade_transactions
  - Returns: {filled: true, price: X, shares: Y, amount: Z}
- [ ] 3.2 Integrate order execution into paper trade creation
  - Modify `create_paper_trade_from_idea` to use OrderExecutor
  - Calculate shares from cash allocation (5% of account per position)
  - Execute market order immediately (no order states in MVP)
  - Update idea_outcomes with shares, entry_amount
- [ ] 3.3 Integrate order execution into trade closing
  - Modify `close_trade` in `paper_trading_portfolio.py` to use OrderExecutor
  - Execute market order to exit position
  - Update cash balance with proceeds
  - Calculate realized P&L in dollars: `(exit_price - entry_price) * shares`
  - Log transaction with EXIT type

#### 4.0 Transaction Audit Trail

**Effort**: LOW (10%)

- [ ] 4.1 Create TransactionLogger class (`backend/app/analytics/transaction_logger.py`)
  - `log_entry(trade_id, ticker, shares, price, cash_before, cash_after, notes) -> None`
  - `log_exit(trade_id, ticker, shares, price, cash_before, cash_after, pnl, notes) -> None`
  - `get_transactions(account_id, limit=100) -> list[dict]` - Recent transactions
  - All transactions include timestamp, trade_id reference
- [ ] 4.2 Add transaction logging to all cash operations
  - CashManager calls TransactionLogger on every deduct/add
  - OrderExecutor calls TransactionLogger on every fill
  - Include contextual notes: "Entry: AAPL long 10 shares", "Exit: TSLA short stop loss hit"
- [ ] 4.3 Create API endpoint for transaction history
  - `GET /api/paper-trading/transactions` - List all transactions
  - `GET /api/paper-trading/transactions/{trade_id}` - Get transactions for specific trade
  - Returns: transaction_type, ticker, shares, price, amount, cash_balance, timestamp, notes

#### 5.0 Manual Paper Trade Creation

**Effort**: LOW-MEDIUM (15%)

- [ ] 5.1 Create API endpoint for manual trade creation
  - `POST /api/paper-trading/trades` - Create paper trade manually
  - Request body: ticker, action (buy/sell), thesis, target_price (optional), stop_loss_pct (optional)
  - Validates cash availability
  - Creates agent_idea record (agent_run_id = "manual")
  - Creates paper trade via existing flow
  - Returns: trade details including shares, entry_price, entry_amount
- [ ] 5.2 Add validation and error handling
  - Check ticker exists (validate_symbol from watchlist)
  - Check sufficient cash
  - Check position limits (max 5% per position)
  - Return clear error messages for failures
- [ ] 5.3 Create simple UI component for manual trade creation
  - Add "Create Paper Trade" button to Watchlist page
  - Dialog with form: ticker dropdown, buy/sell toggle, thesis textarea, target price input, stop loss % input
  - Show available cash and max shares
  - Display success/error toast after submission

#### 6.0 Testing & Validation (Phase A)

**Effort**: LOW (10%)

- [ ] 6.1 Unit tests for cash management
  - Test cash deduction, addition, balance checks
  - Test insufficient cash handling
  - Test transaction logging
- [ ] 6.2 Unit tests for order execution
  - Test market order fills at current price
  - Test cash updates after fills
  - Test entry/exit transaction logging
- [ ] 6.3 Integration tests for paper trade lifecycle
  - Create trade → check cash deducted
  - Update trade daily → check P&L calculations
  - Close trade → check cash credited, realized P&L
  - Verify transaction log completeness
- [ ] 6.4 Integration tests for agent tools
  - Test add_ticker with ownership tracking
  - Test remove_ticker with ownership validation
  - Test create_paper_trade with cash checks
  - Test removal rejection for user-added tickers
- [ ] 6.5 Manual verification checklist
  - Create paper trade manually via API
  - Verify cash balance updates
  - Wait for daily update task (or trigger manually)
  - Verify P&L calculations match expected
  - Close trade manually (via status update)
  - Verify cash credited correctly
  - Check transaction log completeness

---

### Phase B: Full Engine (2-3 weeks) - Production-Ready After Vacation

#### 7.0 Realistic Fill Simulation

**Effort**: MEDIUM (20%)

- [ ] 7.1 Create FillSimulator class (`backend/app/analytics/fill_simulator.py`)
  - `simulate_market_fill(ticker, shares, side) -> dict` - Add slippage based on order size
    - Small order (<100 shares): 0.05% slippage
    - Medium order (100-1000): 0.10% slippage
    - Large order (>1000): 0.20% slippage
  - `simulate_limit_fill(ticker, limit_price, shares, side, current_price) -> dict | None`
    - Returns fill if current_price crosses limit_price
    - Add random execution probability (85% if within 0.5% of limit)
  - `simulate_spread_impact(ticker, current_price) -> dict` - Bid/ask spread estimation
    - Liquid stocks (>$100M daily volume): 0.01% spread
    - Medium liquidity: 0.05% spread
    - Low liquidity: 0.10% spread
- [ ] 7.2 Integrate fill simulation into OrderExecutor
  - Replace instant fills with FillSimulator calls
  - Apply slippage to entry/exit prices
  - Log actual fill price vs expected price in transaction notes
- [ ] 7.3 Add volume/liquidity checks
  - Query daily volume from market_data table
  - Reject orders >10% of daily volume (illiquidity protection)
  - Log warning for orders >1% of daily volume

#### 8.0 Advanced Order Types

**Effort**: MEDIUM-HIGH (25%)

- [ ] 8.1 Create order states table
  - Table: `paper_trade_orders`
  - Columns: id (PK), trade_id (FK idea_outcomes), order_type (MARKET/LIMIT/STOP), status (PENDING/FILLED/CANCELLED), ticker, side (BUY/SELL), shares, limit_price, stop_price, submitted_at, filled_at, cancelled_at
  - Index on status, trade_id, ticker
- [ ] 8.2 Implement limit orders
  - `submit_limit_order(ticker, side, shares, limit_price) -> order_id`
  - Daily update task checks if limit price reached
  - Fill order if current_price crosses limit_price
  - Update order status: PENDING → FILLED
  - Log fill transaction
- [ ] 8.3 Implement stop orders
  - `submit_stop_order(ticker, side, shares, stop_price) -> order_id`
  - Daily update task checks if stop price hit
  - Convert to market order when stop_price reached
  - Fill at current price (with slippage)
  - Update order status: PENDING → FILLED
- [ ] 8.4 Implement order cancellation
  - `cancel_order(order_id) -> bool`
  - Update order status: PENDING → CANCELLED
  - Refund reserved cash if entry order
  - Log cancellation with reason
- [ ] 8.5 Add order management API endpoints
  - `GET /api/paper-trading/orders` - List all orders
  - `GET /api/paper-trading/orders/{order_id}` - Get order details
  - `POST /api/paper-trading/orders` - Submit new order
  - `DELETE /api/paper-trading/orders/{order_id}` - Cancel order

#### 9.0 Position Sizing Rules

**Effort**: MEDIUM (20%)

- [ ] 9.1 Create PositionSizer class (`backend/app/analytics/position_sizer.py`)
  - `equal_weight(cash_balance, num_positions) -> float` - Simple equal allocation
  - `volatility_adjusted(ticker, cash_balance, target_vol) -> float` - Size inversely to volatility
    - Fetch volatility from technical_indicators
    - Formula: `shares = (cash * target_vol) / (price * ticker_vol)`
  - `kelly_criterion(ticker, win_rate, avg_win, avg_loss, cash_balance) -> float`
    - Kelly % = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
    - Use 25% of Kelly for safety (Kelly / 4)
  - `calculate_shares(ticker, method, cash_balance, constraints) -> int`
    - Apply position sizing method
    - Enforce min/max share constraints
    - Round to integer shares
- [ ] 9.2 Add position sizing preferences
  - Add to user_preferences table:
    - `paper_trading_position_method TEXT DEFAULT 'equal_weight'`
    - `paper_trading_max_position_pct DOUBLE PRECISION DEFAULT 5.0` (% of account)
    - `paper_trading_target_volatility DOUBLE PRECISION DEFAULT 15.0` (annualized %)
  - Validate values on update
- [ ] 9.3 Integrate position sizing into order creation
  - Modify OrderExecutor to use PositionSizer
  - Calculate shares based on user preference method
  - Enforce max_position_pct constraint
  - Log sizing calculation in transaction notes

#### 10.0 Risk Management

**Effort**: MEDIUM-HIGH (25%)

- [ ] 10.1 Create RiskManager class (`backend/app/analytics/risk_manager.py`)
  - `check_position_limits(ticker, shares, price, account_id) -> bool`
    - Max position size: default 5% of account
    - Max total exposure: default 95% of account (keep 5% cash buffer)
  - `check_leverage_limits(account_id) -> bool`
    - Short positions create leverage
    - Max leverage: 1.0 (no borrowing in MVP)
  - `check_correlation_limits(ticker, account_id) -> bool`
    - Calculate correlation with existing positions
    - Reject if correlation >0.8 with position >20% of account (concentration risk)
  - `calculate_portfolio_risk(account_id) -> dict`
    - Portfolio volatility (weighted average)
    - Portfolio beta (weighted average)
    - Correlation matrix
    - Concentration metrics (top 3 holdings %, Herfindahl index)
- [ ] 10.2 Add risk preferences
  - Add to user_preferences table:
    - `paper_trading_max_leverage DOUBLE PRECISION DEFAULT 1.0`
    - `paper_trading_max_correlation DOUBLE PRECISION DEFAULT 0.8`
    - `paper_trading_cash_buffer_pct DOUBLE PRECISION DEFAULT 5.0`
  - Validate values on update
- [ ] 10.3 Integrate risk checks into order flow
  - RiskManager.check_position_limits() before order submission
  - RiskManager.check_leverage_limits() before short orders
  - RiskManager.check_correlation_limits() before large positions
  - Reject orders that violate risk constraints
  - Log rejection reason in transaction notes
- [ ] 10.4 Add portfolio risk API endpoint
  - `GET /api/paper-trading/risk` - Current portfolio risk metrics
  - Returns: total_exposure, leverage, top_positions, correlation_matrix, concentration_metrics

#### 11.0 Performance Attribution

**Effort**: MEDIUM (20%)

- [ ] 11.1 Create PerformanceAnalyzer class (`backend/app/analytics/performance_analyzer.py`)
  - `calculate_trade_metrics(trade_id) -> dict`
    - Win/loss (realized_pnl > 0)
    - Win rate (% winning trades)
    - Average win/loss (mean P&L for wins/losses)
    - Profit factor (total wins / total losses)
    - Max favorable/adverse excursion (already tracked)
  - `calculate_portfolio_metrics(account_id) -> dict`
    - Total return % (current equity / initial cash - 1)
    - Sharpe ratio (return / volatility)
    - Max drawdown (peak to trough)
    - Win rate (% winning trades)
    - Average holding period (mean days held)
  - `attribute_returns(account_id) -> dict`
    - P&L by ticker
    - P&L by sector
    - P&L by long/short
    - P&L by entry reason (momentum, value, event, etc.)
- [ ] 11.2 Add performance tracking to trade updates
  - Calculate and store metrics daily during update task
  - Track cumulative equity curve (cash + open position value)
  - Store in new table: `paper_trade_performance_history`
- [ ] 11.3 Create performance API endpoints
  - `GET /api/paper-trading/performance` - Overall portfolio performance
  - `GET /api/paper-trading/performance/trades` - Trade-level performance metrics
  - `GET /api/paper-trading/performance/attribution` - Return attribution breakdown

#### 12.0 Visualization & UI

**Effort**: MEDIUM-HIGH (25%)

- [ ] 12.1 Create Paper Trading page (`frontend/src/app/paper-trading/page.tsx`)
  - Layout: Tabs for Overview, Trades, Orders, Transactions, Performance
  - Overview tab: Current cash, total equity, unrealized P&L, realized P&L
  - Header with account summary card
- [ ] 12.2 Build Trades tab
  - Table: Open trades (ticker, side, shares, entry price, current price, P&L, P&L %, days held, actions)
  - Table: Closed trades (ticker, side, shares, entry price, exit price, realized P&L, realized P&L %, holding days, exit reason)
  - Filters: Open/Closed, Long/Short, Date range
  - Sort by: P&L, P&L %, Holding days
  - Actions: Close trade manually (market order), View details
- [ ] 12.3 Build Orders tab
  - Table: Active orders (type, ticker, side, shares, limit/stop price, status, submitted time)
  - Table: Filled orders (type, ticker, side, shares, fill price, filled time)
  - Filters: Pending/Filled/Cancelled, Order type
  - Actions: Cancel pending order, Resubmit cancelled order
- [ ] 12.4 Build Transactions tab
  - Table: All transactions (type, ticker, shares, price, amount, cash balance, timestamp, notes)
  - Filters: Entry/Exit, Date range, Ticker
  - Export to CSV functionality
- [ ] 12.5 Build Performance tab
  - Equity curve chart (time series of total account value)
  - P&L distribution chart (histogram of trade returns)
  - Win rate gauge (% of winning trades)
  - Metrics cards: Total return %, Sharpe ratio, Max drawdown, Avg win/loss, Profit factor
  - Attribution breakdown: By ticker, by sector, by long/short
- [ ] 12.6 Add Create Trade dialog (enhanced from MVP)
  - Ticker input with autocomplete
  - Buy/Sell toggle
  - Order type selector (Market, Limit, Stop)
  - Shares input with position sizing calculator
  - Target price / Stop loss inputs
  - Thesis textarea
  - Preview: Entry amount, max shares, position size %, estimated slippage
  - Submit button with validation

#### 13.0 Testing & Documentation (Phase B)

**Effort**: MEDIUM (15%)

- [ ] 13.1 Unit tests for new components
  - FillSimulator: Test slippage, spread, liquidity checks
  - PositionSizer: Test equal weight, volatility-adjusted, Kelly
  - RiskManager: Test position limits, leverage, correlation
  - PerformanceAnalyzer: Test metrics calculations
- [ ] 13.2 Integration tests for advanced features
  - Test limit order fills when price reached
  - Test stop order triggers and fills
  - Test position sizing with different methods
  - Test risk limit enforcement
  - Test performance attribution accuracy
- [ ] 13.3 Frontend component tests
  - Test Paper Trading page renders
  - Test trade creation dialog submission
  - Test order cancellation flow
  - Test data fetching and display
- [ ] 13.4 E2E tests with Playwright
  - Create paper trade via UI
  - Wait for order fill
  - Verify trade appears in open trades
  - Close trade manually
  - Verify transaction log updated
- [ ] 13.5 Update documentation
  - Add Paper Trading section to ARCHITECTURE.md
  - Document API endpoints in API_REFERENCE.md
  - Create user guide: `docs/guides/paper-trading.md`
  - Document agent tools in agent documentation

---

## Autonomous Agent Behavior Rules

**Watchlist Management**:
- Agents can add tickers autonomously when discovering opportunities
- Agents can remove ONLY tickers they added (ownership validation enforced)
- Agents CANNOT remove user-added tickers (error returned)
- Removal criteria: Idea invalidated after time + performance thresholds
  - Time: Minimum 30 days since idea added
  - Performance: Target not reached AND stop loss not hit (idea was wrong, not just unlucky)

**Paper Trade Creation**:
- Agents can create paper trades autonomously via `create_paper_trade` tool
- Each trade subject to:
  - Cash availability check (5% of account per position max)
  - Risk management constraints (position limits, leverage, correlation)
  - Position sizing rules (equal weight default, user-configurable)
- Agents notified of rejection with clear reason
- Agents encouraged to learn from rejected trades

**Trade Management**:
- Agents CANNOT manually close trades (automatic exits only)
- Exit conditions:
  - Target price hit (profit taking)
  - Stop loss hit (risk management)
  - Time limit exceeded (60 days default, configurable)
- Agents receive notifications when their trades close
- Agents encouraged to analyze exit reasons and adjust strategy

**Risk Tolerance**:
- User has HIGH risk tolerance (per requirements)
- Agents allowed to create paper trades freely within constraints
- Constraints protect against:
  - Over-concentration (max 5% per position)
  - Over-leverage (max 1.0 leverage)
  - Over-correlation (max 0.8 correlation for large positions)
- Constraints enforced automatically, no manual oversight needed

---

## Verification

**Phase A (Quick MVP)**:
- [ ] Functional: Cash management, order execution, transaction logging working
- [ ] Functional: Agent tools (add_ticker, remove_ticker, create_paper_trade) operational
- [ ] Functional: Manual paper trade creation via API working
- [ ] Functional: Daily update task correctly updates trades and closes on exit conditions
- [ ] Tests: Backend `pytest tests/ -v` passes (unit + integration tests for Phase A)
- [ ] Quality: `~/portfolio-ai/scripts/lint.sh` passes (ruff + mypy)
- [ ] Services: `bash ~/portfolio-ai/scripts/restart.sh` succeeds
- [ ] Manual: Create paper trade, verify cash deduction, wait for update, verify P&L, close trade, verify cash credit
- [ ] Git: Regular commits throughout Phase A (~5-7 commits expected)

**Phase B (Full Engine)**:
- [ ] Functional: All requirements met (fill simulation, order types, position sizing, risk management, performance attribution, visualization)
- [ ] Functional: Zero regressions in Phase A functionality
- [ ] Tests: Backend `pytest tests/ -v` passes (unit + integration tests for Phase B)
- [ ] Tests: Frontend `npm test` passes (component tests)
- [ ] Tests: Frontend `npm run test:e2e` passes (E2E tests)
- [ ] Quality: `~/portfolio-ai/scripts/lint.sh` passes (ruff + mypy)
- [ ] Services: `bash ~/portfolio-ai/scripts/restart.sh` succeeds
- [ ] Docs: ARCHITECTURE.md, API_REFERENCE.md, paper-trading.md updated
- [ ] Manual: Complete user journey (create trade, wait for fill, check P&L, analyze performance, close trade)
- [ ] Git: Regular commits throughout Phase B (~10-15 commits expected)

---

## Notes

**Reusable Infrastructure**:
- `paper_trading_portfolio.py` - Trade update logic (354 lines)
- `paper_trading_orders.py` - Order creation logic (201 lines)
- `trade_calculations.py` - Stop loss, target extraction, exit checks (197 lines)
- `idea_outcomes` table - Complete trade lifecycle schema
- `portfolio_accounts` table - Ready for cash balance extension
- `watchlist` API - Add/remove endpoints exist
- `AgentTools` class - Ready for new tool definitions
- `PriceDataFetcher` - Current price fetching
- Daily update task - Scheduled infrastructure exists

**Design Decisions**:
- Simple equal-weight position sizing in MVP (5% per position)
- Instant market fills in MVP (no order states, no slippage)
- Paper-only account (no real brokerage integration)
- Agent ownership tracking via `added_by` field in watchlist
- Transaction log for complete audit trail
- Autonomous agent behavior within risk constraints
- Two-phase delivery for quick validation + full feature set

**Risk Management**:
- MVP: Simple cash checks and position size limits
- Full: Position limits, leverage limits, correlation limits, portfolio risk metrics
- All constraints configurable via user preferences
- Violations logged clearly for agent learning

**Integration Points**:
- Task 0060: Agents use new tools to manage watchlist and create trades
- Task 0062: Gap detection analyzes paper trade performance for strategy validation
- Task 0063: Backtesting shares position tracking and P&L calculation logic
- Existing infrastructure: Leverages 60-70% of code already written

**Vacation Safety**:
- Phase A delivers functional system in 3-5 days
- Agents can create trades autonomously during vacation
- Daily update task runs automatically (scheduled)
- Risk constraints prevent over-trading
- Transaction log provides complete audit trail
- Phase B adds polish after vacation (2-3 weeks)
