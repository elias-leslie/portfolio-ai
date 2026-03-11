"""Financial health scoring: Piotroski F-Score and Altman Z-Score.

GAP-008: Piotroski F-Score (9-point fundamental quality score)
GAP-009: Altman Z-Score (bankruptcy prediction model)

Both scores use balance sheet and income statement data from yfinance.
"""

from __future__ import annotations

from dataclasses import dataclass

try:
    import yfinance as yf

    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False


@dataclass
class FinancialHealthScores:
    """Container for financial health scores."""

    symbol: str
    f_score: int | None = None  # 0-9 (higher = better quality)
    f_score_components: dict[str, int] | None = None  # Individual F-Score components
    z_score: float | None = None  # >2.99 safe, 1.81-2.99 grey, <1.81 distress
    z_score_zone: str | None = None  # "safe", "grey", "distress"
    error: str | None = None


def calculate_piotroski_f_score(
    symbol: str,
) -> tuple[int | None, dict[str, int] | None, str | None]:
    """Calculate Piotroski F-Score (9-point fundamental quality score).

    The F-Score assesses financial strength using 9 binary criteria:

    Profitability (4 points):
    1. ROA > 0 (positive net income)
    2. Operating Cash Flow > 0
    3. ROA increasing year-over-year
    4. Cash Flow from Operations > Net Income (accruals quality)

    Leverage/Liquidity (3 points):
    5. Long-term debt ratio decreasing
    6. Current ratio increasing
    7. No new share issuance

    Operating Efficiency (2 points):
    8. Gross margin increasing
    9. Asset turnover increasing

    Args:
        symbol: Stock symbol

    Returns:
        Tuple of (f_score, components_dict, error_message)
        f_score: 0-9 integer (None if calculation failed)
        components: Dict with individual component scores
        error: Error message if failed
    """
    if not YFINANCE_AVAILABLE:
        return None, None, "yfinance not available"

    try:
        ticker = yf.Ticker(symbol)
        bs = ticker.balance_sheet
        cf = ticker.cashflow
        income = ticker.income_stmt

        if bs.empty or cf.empty or income.empty:
            return None, None, "Insufficient financial statement data"

        # Need at least 2 periods for YoY comparisons
        if bs.shape[1] < 2 or income.shape[1] < 2:
            return None, None, "Need at least 2 periods for comparison"

        components = {}
        score = 0

        # Get current and prior period data
        curr_bs = bs.iloc[:, 0]
        prev_bs = bs.iloc[:, 1]
        curr_inc = income.iloc[:, 0]
        prev_inc = income.iloc[:, 1]
        curr_cf = cf.iloc[:, 0]

        # Helper to safely get values
        def get_val(series: object, key: str, default: float = 0) -> float:
            return series.get(key, default) or default

        # Calculate metrics
        total_assets_curr = get_val(curr_bs, "Total Assets", 1)
        total_assets_prev = get_val(prev_bs, "Total Assets", 1)
        net_income_curr = get_val(curr_inc, "Net Income")
        net_income_prev = get_val(prev_inc, "Net Income")
        operating_cf = get_val(curr_cf, "Operating Cash Flow")
        gross_profit_curr = get_val(curr_inc, "Gross Profit")
        gross_profit_prev = get_val(prev_inc, "Gross Profit")
        revenue_curr = get_val(curr_inc, "Total Revenue", 1)
        revenue_prev = get_val(prev_inc, "Total Revenue", 1)
        long_term_debt_curr = get_val(curr_bs, "Long Term Debt")
        long_term_debt_prev = get_val(prev_bs, "Long Term Debt")
        current_assets_curr = get_val(curr_bs, "Current Assets")
        current_assets_prev = get_val(prev_bs, "Current Assets")
        current_liab_curr = get_val(curr_bs, "Current Liabilities", 1)
        current_liab_prev = get_val(prev_bs, "Current Liabilities", 1)
        shares_curr = get_val(curr_bs, "Share Issued")
        shares_prev = get_val(prev_bs, "Share Issued")

        # 1. ROA > 0 (positive net income)
        roa_curr = net_income_curr / total_assets_curr if total_assets_curr else 0
        components["roa_positive"] = 1 if roa_curr > 0 else 0
        score += components["roa_positive"]

        # 2. Operating Cash Flow > 0
        components["ocf_positive"] = 1 if operating_cf > 0 else 0
        score += components["ocf_positive"]

        # 3. ROA increasing YoY
        roa_prev = net_income_prev / total_assets_prev if total_assets_prev else 0
        components["roa_increasing"] = 1 if roa_curr > roa_prev else 0
        score += components["roa_increasing"]

        # 4. Cash Flow > Net Income (accruals quality)
        components["accruals_quality"] = 1 if operating_cf > net_income_curr else 0
        score += components["accruals_quality"]

        # 5. Long-term debt ratio decreasing
        debt_ratio_curr = long_term_debt_curr / total_assets_curr if total_assets_curr else 0
        debt_ratio_prev = long_term_debt_prev / total_assets_prev if total_assets_prev else 0
        components["debt_decreasing"] = 1 if debt_ratio_curr < debt_ratio_prev else 0
        score += components["debt_decreasing"]

        # 6. Current ratio increasing
        curr_ratio_curr = current_assets_curr / current_liab_curr if current_liab_curr else 0
        curr_ratio_prev = current_assets_prev / current_liab_prev if current_liab_prev else 0
        components["liquidity_improving"] = 1 if curr_ratio_curr > curr_ratio_prev else 0
        score += components["liquidity_improving"]

        # 7. No new share issuance
        components["no_dilution"] = 1 if shares_curr <= shares_prev else 0
        score += components["no_dilution"]

        # 8. Gross margin increasing
        gm_curr = gross_profit_curr / revenue_curr if revenue_curr else 0
        gm_prev = gross_profit_prev / revenue_prev if revenue_prev else 0
        components["margin_improving"] = 1 if gm_curr > gm_prev else 0
        score += components["margin_improving"]

        # 9. Asset turnover increasing
        turnover_curr = revenue_curr / total_assets_curr if total_assets_curr else 0
        turnover_prev = revenue_prev / total_assets_prev if total_assets_prev else 0
        components["turnover_improving"] = 1 if turnover_curr > turnover_prev else 0
        score += components["turnover_improving"]

        return score, components, None

    except Exception as e:
        return None, None, f"F-Score calculation error: {e!s}"


def calculate_altman_z_score(symbol: str) -> tuple[float | None, str | None, str | None]:
    """Calculate Altman Z-Score (bankruptcy prediction model).

    The Z-Score predicts probability of bankruptcy using 5 financial ratios:

    Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5

    Where:
    X1 = Working Capital / Total Assets (liquidity)
    X2 = Retained Earnings / Total Assets (profitability)
    X3 = EBIT / Total Assets (productivity)
    X4 = Market Cap / Total Liabilities (solvency)
    X5 = Revenue / Total Assets (activity)

    Interpretation:
    - Z > 2.99: "Safe Zone" - low bankruptcy risk
    - 1.81 < Z < 2.99: "Grey Zone" - some risk
    - Z < 1.81: "Distress Zone" - high bankruptcy risk

    Args:
        symbol: Stock symbol

    Returns:
        Tuple of (z_score, zone, error_message)
        z_score: Float value (None if calculation failed)
        zone: "safe", "grey", or "distress"
        error: Error message if failed
    """
    if not YFINANCE_AVAILABLE:
        return None, None, "yfinance not available"

    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        bs = ticker.balance_sheet
        income = ticker.income_stmt

        if bs.empty or income.empty:
            return None, None, "Insufficient financial statement data"

        # Get most recent data
        curr_bs = bs.iloc[:, 0]
        curr_inc = income.iloc[:, 0]

        # Helper to safely get values
        def get_val(series: object, key: str, default: float = 0) -> float:
            return series.get(key, default) or default

        # Extract required values
        total_assets = get_val(curr_bs, "Total Assets")
        if not total_assets or total_assets <= 0:
            return None, None, "Invalid total assets"

        working_capital = get_val(curr_bs, "Working Capital")
        retained_earnings = get_val(curr_bs, "Retained Earnings")
        ebit = get_val(curr_inc, "EBIT") or get_val(curr_inc, "Operating Income")
        total_revenue = get_val(curr_inc, "Total Revenue")
        total_liabilities = get_val(curr_bs, "Total Liabilities Net Minority Interest")

        # Get market cap from info
        market_cap = info.get("marketCap", 0) or 0

        if not total_liabilities or total_liabilities <= 0:
            total_liabilities = 1  # Avoid division by zero

        # Calculate Z-Score components
        x1 = working_capital / total_assets  # Working Capital / Total Assets
        x2 = retained_earnings / total_assets  # Retained Earnings / Total Assets
        x3 = ebit / total_assets  # EBIT / Total Assets
        x4 = market_cap / total_liabilities  # Market Cap / Total Liabilities
        x5 = total_revenue / total_assets  # Revenue / Total Assets

        # Altman Z-Score formula
        z_score = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5

        # Determine zone
        if z_score > 2.99:
            zone = "safe"
        elif z_score > 1.81:
            zone = "grey"
        else:
            zone = "distress"

        return round(z_score, 2), zone, None

    except Exception as e:
        return None, None, f"Z-Score calculation error: {e!s}"


def get_financial_health_scores(symbol: str) -> FinancialHealthScores:
    """Get both F-Score and Z-Score for a symbol.

    Args:
        symbol: Stock symbol

    Returns:
        FinancialHealthScores with both scores
    """
    f_score, f_components, f_error = calculate_piotroski_f_score(symbol)
    z_score, z_zone, z_error = calculate_altman_z_score(symbol)

    error = None
    if f_error and z_error:
        error = f"F-Score: {f_error}; Z-Score: {z_error}"

    return FinancialHealthScores(
        symbol=symbol,
        f_score=f_score,
        f_score_components=f_components,
        z_score=z_score,
        z_score_zone=z_zone,
        error=error,
    )
