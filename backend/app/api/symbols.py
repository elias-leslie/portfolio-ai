"""Symbol Intelligence API - Comprehensive symbol data aggregation.

Provides a unified endpoint that returns ALL relevant data about a symbol
in one call, enabling agents to give fact-based recommendations.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from app.logging_config import get_logger
from app.storage import get_storage
from app.storage.helpers import row_to_dict, rows_to_dicts
from app.watchlist.watchlist_service import WatchlistService

logger = get_logger(__name__)

# Scoring pillar weights - must sum to 1.0
PILLAR_WEIGHTS = {
    "price": 0.22,
    "technical": 0.22,
    "fundamental": 0.26,
    "catalyst": 0.17,
    "options_flow": 0.08,
    "performance": 0.05,
}

# Fear & Greed thresholds for recommendations
FEAR_GREED_FEAR_THRESHOLD = 30
FEAR_GREED_GREED_THRESHOLD = 70
FEAR_GREED_DEFAULT = 50
GAIN_PCT_TRIM_THRESHOLD = 20.0

router = APIRouter(prefix="/api/symbols", tags=["symbols"])
storage = get_storage()
watchlist_service = WatchlistService(storage)


# Response Models
class PillarScore(BaseModel):
    """Individual pillar score with metadata."""

    score: float | None
    weight: float
    sub_scores: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    stale: bool = False


class ScoresSection(BaseModel):
    """All scoring data for a symbol."""

    overall: float | None
    signal_type: str | None
    signal_strength: int | None
    pillars: dict[str, PillarScore]
    data_quality: dict[str, Any] | None = None


class SignalSection(BaseModel):
    """Signal classification with reasoning."""

    type: str | None
    strength: int | None
    confirmations: int | None = None
    reasons: dict[str, list[str]] | None = None
    avoid_flags: int = 0


class TradingSection(BaseModel):
    """Trading style and position guidance."""

    style: str | None
    confidence: int | None
    holding_period: str | None
    risk_level: str | None
    entry_price: float | None
    stop_loss: float | None
    profit_target: float | None
    position_size_shares: int | None
    position_size_dollars: float | None


class CompanySection(BaseModel):
    """Company fundamentals and timing."""

    health: str | None = None  # WEAK, FAIR, STRONG
    earnings_date: str | None = None
    earnings_days_away: int | None = None


class TrendSection(BaseModel):
    """Trend alignment and volume data."""

    short_term_aligned: bool | None = None
    long_term_aligned: bool | None = None
    volume_relative: float | None = None  # 1.0 = average, 2.0 = 2x average


class NewsArticle(BaseModel):
    """Recent news article."""

    headline: str
    source: str | None = None
    published_at: str | None = None


class AlertIndicator(BaseModel):
    """Priority alert indicator."""

    icon: str
    label: str
    tooltip: str | None = None
    priority: int = 0
    category: str | None = None


class PositionInfo(BaseModel):
    """Portfolio position details."""

    shares: float
    cost_basis: float
    current_value: float
    gain: float
    gain_pct: float
    weight_pct: float


class PortfolioContext(BaseModel):
    """Portfolio-level context."""

    total_value: float
    num_holdings: int
    diversification_score: float | None = None
    sector_weight: float | None = None
    concentration_top3: float | None = None


class PortfolioSection(BaseModel):
    """Portfolio position and context."""

    held: bool
    position: PositionInfo | None = None
    context: PortfolioContext | None = None


class PaperTradeInfo(BaseModel):
    """Paper trade summary."""

    entry_price: float
    exit_price: float | None = None
    return_pct: float | None = None
    holding_days: int | None = None
    status: str


class PaperTradesSection(BaseModel):
    """Paper trading history for symbol."""

    open_position: PaperTradeInfo | None = None
    closed_trades: list[PaperTradeInfo] = []
    win_rate: float | None = None
    avg_return: float | None = None


class StrategyInfo(BaseModel):
    """Strategy summary."""

    id: str
    name: str
    strategy_type: str
    expected_sharpe: float | None = None
    live_sharpe: float | None = None
    win_rate: float | None = None
    current_signal: str | None = None


class StrategiesSection(BaseModel):
    """Active strategies for symbol."""

    active_count: int
    strategies: list[StrategyInfo] = []
    best_strategy: StrategyInfo | None = None


class KeyEvent(BaseModel):
    """Material news event."""

    icon: str
    text: str
    time_ago: str


class NewsSection(BaseModel):
    """News and sentiment data."""

    sentiment_score: float | None = None
    sentiment_label: str | None = None
    article_count_24h: int = 0
    key_events: list[KeyEvent] = []
    headline: str | None = None
    recent_articles: list[NewsArticle] = []


class SectorInfo(BaseModel):
    """Sector performance context."""

    name: str | None = None
    signal: str | None = None
    daily_change: float | None = None
    relative_to_spy: float | None = None


class MarketSection(BaseModel):
    """Broader market context."""

    fear_greed_score: int | None = None
    fear_greed_label: str | None = None
    health_score: int | None = None
    vix: float | None = None
    sp500_change: float | None = None
    sector: SectorInfo | None = None


class RecommendationSection(BaseModel):
    """Personalized recommendation."""

    action: str
    reasoning: list[str]
    if_not_held: dict[str, Any] | None = None


class SymbolIntelligenceResponse(BaseModel):
    """Complete symbol intelligence response."""

    symbol: str
    generated_at: datetime

    scores: ScoresSection | None = None
    signal: SignalSection | None = None
    trading: TradingSection | None = None
    company: CompanySection | None = None
    trends: TrendSection | None = None
    portfolio: PortfolioSection | None = None
    paper_trades: PaperTradesSection | None = None
    strategies: StrategiesSection | None = None
    news: NewsSection | None = None
    market: MarketSection | None = None
    alerts: list[AlertIndicator] = []
    recommendation: RecommendationSection | None = None

    error: str | None = None


def _get_watchlist_data(symbol: str) -> dict[str, Any] | None:
    """Fetch watchlist data for symbol using the watchlist service."""
    try:
        items = watchlist_service.get_items_with_scores()
        # Find the item for this symbol (items are dicts)
        for item in items:
            if item.get("symbol", "").upper() == symbol.upper():
                score = item.get("score") or {}

                result = {
                    "id": str(item.get("id")),
                    "symbol": item.get("symbol"),
                    "note": item.get("note"),
                    "overall_score": score.get("overall"),
                    "signal_type": item.get("signal_type"),
                    "signal_strength": item.get("signal_strength"),
                    "recommended_style": item.get("recommended_style"),
                    "style_confidence": item.get("style_confidence"),
                    "optimal_holding_period": item.get("optimal_holding_period"),
                    "risk_level": item.get("risk_level"),
                    "entry_price": item.get("entry_price"),
                    "stop_loss": item.get("stop_loss"),
                    "profit_target": item.get("profit_target"),
                    "position_size_shares": item.get("position_size_shares"),
                    # Company facts
                    "company_health": item.get("company_health"),
                    "earnings_date": item.get("earnings_date"),
                    "earnings_days_away": item.get("earnings_days_away"),
                    # Trend alignment facts
                    "timeframe_short_aligned": item.get("timeframe_short_aligned"),
                    "timeframe_long_aligned": item.get("timeframe_long_aligned"),
                    "volume_relative": item.get("volume_relative"),
                    # News intelligence (full object)
                    "news_intelligence": item.get("news_intelligence"),
                    # Priority alerts
                    "priority_indicators": item.get("priority_indicators"),
                }

                # Extract pillar scores (each pillar is a dict with score, stale, metadata, etc.)
                for pillar in ["price", "technical", "fundamental", "catalyst", "options_flow"]:
                    pillar_data = score.get(pillar) or {}
                    result[f"{pillar}_score"] = pillar_data.get("score")
                    result[f"{pillar}_sub_scores"] = pillar_data.get("sub_scores")
                    result[f"{pillar}_metadata"] = pillar_data.get("metadata")
                    result[f"{pillar}_stale"] = pillar_data.get("stale", False)

                # Performance pillar (may not exist)
                perf = score.get("performance_factor") or {}
                result["performance_score"] = perf.get("score")
                result["performance_sub_scores"] = perf.get("sub_scores")
                result["performance_metadata"] = perf.get("metadata")
                result["performance_stale"] = perf.get("stale", False)

                # Data quality
                dq = item.get("data_quality") or {}
                result["data_quality_overall_pct"] = dq.get("overall_pct")
                result["data_quality_pillars"] = dq.get("pillars")

                return result
        return None
    except Exception as e:
        logger.warning(f"Failed to get watchlist data for {symbol}: {e}")
        return None


def _get_portfolio_data(symbol: str) -> dict[str, Any]:
    """Fetch portfolio position and context."""
    position = None
    summary = None

    try:
        with storage.connection() as conn:
            # Get position for this symbol
            pos_result = conn.execute(
                """
                SELECT p.id, p.symbol, p.shares, p.cost_basis, p.position_type,
                       pc.price as current_price
                FROM portfolio_positions p
                LEFT JOIN price_cache pc ON UPPER(p.symbol) = UPPER(pc.symbol)
                WHERE UPPER(p.symbol) = UPPER(%s)
                """,
                [symbol],
            )
            pos_row = pos_result.fetchone()
            if pos_row and pos_result.description:
                position = row_to_dict(pos_row, pos_result.description)

            # Get portfolio summary
            summary_result = conn.execute(
                """
                SELECT
                    COUNT(*) as num_holdings,
                    SUM(p.shares * COALESCE(pc.price, p.cost_basis)) as total_value
                FROM portfolio_positions p
                LEFT JOIN price_cache pc ON UPPER(p.symbol) = UPPER(pc.symbol)
                """
            )
            sum_row = summary_result.fetchone()
            if sum_row and summary_result.description:
                summary = row_to_dict(sum_row, summary_result.description)
    except Exception as e:
        logger.warning(f"Failed to get portfolio data for {symbol}: {e}")

    return {"position": position, "summary": summary}


def _get_paper_trades_data(symbol: str) -> dict[str, Any]:
    """Fetch paper trading history for symbol."""
    trades = []
    try:
        with storage.connection() as conn:
            result = conn.execute(
                """
                SELECT
                    idea_id, symbol, shares, entry_price, entry_date,
                    exit_price, exit_date, exit_reason,
                    current_price, current_return_pct, realized_return_pct,
                    CASE WHEN exit_date IS NULL THEN 'open' ELSE 'closed' END as status,
                    EXTRACT(DAY FROM COALESCE(exit_date, NOW()) - entry_date)::int as holding_days
                FROM idea_outcomes
                WHERE UPPER(symbol) = UPPER(%s)
                ORDER BY entry_date DESC
                """,
                [symbol],
            )
            rows = result.fetchall()
            if rows and result.description:
                trades = rows_to_dicts(rows, result.description)
    except Exception as e:
        logger.warning(f"Failed to get paper trades data for {symbol}: {e}")

    # Calculate stats
    closed = [t for t in trades if t.get("status") == "closed"]
    open_trade = next((t for t in trades if t.get("status") == "open"), None)

    wins = [t for t in closed if float(t.get("realized_return_pct") or 0) > 0]
    win_rate = (len(wins) / len(closed) * 100) if closed else None
    avg_return = (
        sum(float(t.get("realized_return_pct") or 0) for t in closed) / len(closed)
        if closed
        else None
    )

    return {
        "trades": trades,
        "open_trade": open_trade,
        "closed_trades": closed,
        "win_rate": win_rate,
        "avg_return": avg_return,
    }


def _get_strategies_data(symbol: str) -> dict[str, Any]:
    """Fetch active strategies for symbol."""
    strategies = []
    try:
        with storage.connection() as conn:
            result = conn.execute(
                """
                SELECT
                    id, name, symbol, strategy_type, status,
                    expected_sharpe, live_sharpe_ratio, live_win_rate,
                    live_trades_count
                FROM strategy_definitions
                WHERE UPPER(symbol) = UPPER(%s)
                AND status IN ('active', 'testing')
                ORDER BY live_sharpe_ratio DESC NULLS LAST
                """,
                [symbol],
            )
            rows = result.fetchall()
            if rows and result.description:
                strategies = rows_to_dicts(rows, result.description)
    except Exception as e:
        logger.warning(f"Failed to get strategies data for {symbol}: {e}")

    return {
        "strategies": strategies,
        "active_count": len(strategies),
        "best": strategies[0] if strategies else None,
    }


def _get_news_data(symbol: str) -> dict[str, Any]:
    """Fetch news sentiment for symbol."""
    try:
        with storage.connection() as conn:
            # Try simpler query first
            result = conn.execute(
                """
                SELECT symbol, sentiment_score, article_count, created_at
                FROM news_summary_log
                WHERE UPPER(symbol) = UPPER(%s)
                ORDER BY created_at DESC
                LIMIT 1
                """,
                [symbol],
            )
            row = result.fetchone()
            if row and result.description:
                return row_to_dict(row, result.description)
    except Exception as e:
        logger.warning(f"Failed to get news data for {symbol}: {e}")
    return {}


def _get_market_data() -> dict[str, Any]:
    """Fetch current market context."""
    fear_greed = None
    indicators = {}

    try:
        with storage.connection() as conn:
            # Fear & Greed
            fg_result = conn.execute(
                """
                SELECT score, label, score_change
                FROM fear_greed_daily
                ORDER BY as_of_date DESC
                LIMIT 1
                """
            )
            fg_row = fg_result.fetchone()
            if fg_row and fg_result.description:
                fear_greed = row_to_dict(fg_row, fg_result.description)
    except Exception as e:
        logger.warning(f"Failed to get fear/greed data: {e}")

    try:
        with storage.connection() as conn:
            # Market indicators (VIX, SPY)
            ind_result = conn.execute(
                """
                SELECT symbol, close as price,
                       (close - LAG(close) OVER (PARTITION BY symbol ORDER BY date)) /
                       NULLIF(LAG(close) OVER (PARTITION BY symbol ORDER BY date), 0) * 100 as daily_change
                FROM day_bars
                WHERE symbol IN ('^VIX', '^GSPC')
                AND date >= (SELECT MAX(date) - INTERVAL '2 days' FROM day_bars WHERE symbol = '^VIX')
                ORDER BY date DESC
                """
            )
            rows = ind_result.fetchall()
            if rows and ind_result.description:
                for r in rows_to_dicts(rows, ind_result.description):
                    if r["symbol"] not in indicators:
                        indicators[r["symbol"]] = r
    except Exception as e:
        logger.warning(f"Failed to get market indicators: {e}")

    return {
        "fear_greed": fear_greed,
        "vix": indicators.get("^VIX", {}).get("price"),
        "sp500_change": indicators.get("^GSPC", {}).get("daily_change"),
    }


def _build_scores_section(watchlist: dict[str, Any]) -> ScoresSection:
    """Build the scores section from watchlist data."""
    pillars = {}
    for pillar, weight in PILLAR_WEIGHTS.items():
        score_key = f"{pillar}_score"
        pillars[pillar] = PillarScore(
            score=watchlist.get(score_key),
            weight=weight,
            sub_scores=watchlist.get(f"{pillar}_sub_scores"),
            metadata=watchlist.get(f"{pillar}_metadata"),
            stale=watchlist.get(f"{pillar}_stale", False) or False,
        )

    return ScoresSection(
        overall=watchlist.get("overall_score"),
        signal_type=watchlist.get("signal_type"),
        signal_strength=watchlist.get("signal_strength"),
        pillars=pillars,
        data_quality={
            "overall_pct": watchlist.get("data_quality_overall_pct"),
            "pillars": watchlist.get("data_quality_pillars"),
        },
    )


def _build_portfolio_section(
    position: dict[str, Any] | None, summary: dict[str, Any] | None
) -> PortfolioSection:
    """Build the portfolio section from position and summary data."""
    if position:
        current_price = position.get("current_price") or position.get("cost_basis") or 0
        current_value = position.get("shares", 0) * current_price
        cost_total = position.get("shares", 0) * position.get("cost_basis", 0)
        gain = current_value - cost_total
        gain_pct = (gain / cost_total * 100) if cost_total else 0
        total_value = (summary.get("total_value") if summary else None) or current_value

        return PortfolioSection(
            held=True,
            position=PositionInfo(
                shares=position.get("shares", 0),
                cost_basis=position.get("cost_basis", 0),
                current_value=current_value,
                gain=gain,
                gain_pct=gain_pct,
                weight_pct=(current_value / total_value * 100) if total_value else 0,
            ),
            context=PortfolioContext(
                total_value=total_value,
                num_holdings=summary.get("num_holdings", 0) if summary else 0,
            ),
        )

    return PortfolioSection(
        held=False,
        context=PortfolioContext(
            total_value=(summary.get("total_value") or 0) if summary else 0,
            num_holdings=(summary.get("num_holdings") or 0) if summary else 0,
        )
        if summary
        else None,
    )


def _build_paper_trades_section(paper_trades: dict[str, Any]) -> PaperTradesSection:
    """Build the paper trades section from paper trades data."""
    open_pos = paper_trades.get("open_trade")
    closed = paper_trades.get("closed_trades") or []

    return PaperTradesSection(
        open_position=PaperTradeInfo(
            entry_price=open_pos.get("entry_price", 0),
            return_pct=open_pos.get("current_return_pct"),
            holding_days=open_pos.get("holding_days"),
            status="open",
        )
        if open_pos
        else None,
        closed_trades=[
            PaperTradeInfo(
                entry_price=t.get("entry_price", 0),
                exit_price=t.get("exit_price"),
                return_pct=t.get("realized_return_pct"),
                holding_days=t.get("holding_days"),
                status="closed",
            )
            for t in closed[:5]
        ],
        win_rate=paper_trades.get("win_rate"),
        avg_return=paper_trades.get("avg_return"),
    )


def _generate_recommendation(
    watchlist: dict[str, Any] | None,
    portfolio: dict[str, Any] | None,
    market: dict[str, Any] | None,
) -> dict[str, Any]:
    """Generate personalized recommendation based on all data."""
    portfolio = portfolio or {}
    market = market or {}

    held = portfolio.get("position") is not None
    signal = watchlist.get("signal_type") if watchlist else None
    strength = (watchlist.get("signal_strength") if watchlist else None) or 0
    fear_greed_data = market.get("fear_greed") or {}
    fear_greed = fear_greed_data.get("score", FEAR_GREED_DEFAULT) if fear_greed_data else FEAR_GREED_DEFAULT

    reasoning = []
    action = "HOLD"

    if held:
        position = portfolio["position"]
        gain_pct = 0
        if position.get("current_price") and position.get("cost_basis"):
            gain_pct = (
                (position["current_price"] - position["cost_basis"]) / position["cost_basis"]
            ) * 100

        if signal == "BUY" and strength >= 7:
            action = "BUY_MORE"
            reasoning.append(f"Strong BUY signal ({strength}/10)")
        elif signal == "AVOID":
            action = "CONSIDER_SELLING"
            reasoning.append("Signal turned to AVOID")
        elif gain_pct > GAIN_PCT_TRIM_THRESHOLD:
            action = "CONSIDER_TRIMMING"
            reasoning.append(f"Position up {gain_pct:.1f}% - consider taking profits")
        else:
            action = "HOLD_POSITION"
            reasoning.append(f"Current gain: {gain_pct:.1f}%")

        if strength < 6:
            reasoning.append(f"Signal strength only {strength}/10 - wait for stronger confirmation")
    elif signal == "BUY":
        if strength >= 7:
            action = "INITIATE_POSITION"
            reasoning.append(f"Strong BUY signal ({strength}/10)")
        else:
            action = "SMALL_POSITION"
            reasoning.append(f"BUY signal but moderate strength ({strength}/10)")
    elif signal == "HOLD":
        action = "WATCH"
        reasoning.append("HOLD signal - wait for better entry")
    else:
        action = "AVOID"
        reasoning.append("AVOID signal - do not initiate")

    # Market context
    if fear_greed and fear_greed < FEAR_GREED_FEAR_THRESHOLD:
        reasoning.append(f"Market in Fear ({fear_greed}) - consider smaller positions")
    elif fear_greed and fear_greed > FEAR_GREED_GREED_THRESHOLD:
        reasoning.append(f"Market in Greed ({fear_greed}) - be cautious")

    return {
        "action": action,
        "reasoning": reasoning,
        "if_not_held": {
            "action": "SMALL_POSITION" if signal == "BUY" else "AVOID",
            "size_pct": 2.0 if strength >= 7 else 1.0,
            "reasoning": f"Signal: {signal}, Strength: {strength}/10",
        }
        if held
        else None,
    }


def _fetch_all_data(
    symbol: str, include_market: bool, include_paper_trades: bool, include_strategies: bool
) -> dict[str, Any]:
    """Fetch all data sources for symbol intelligence.

    Returns dict with keys: watchlist, portfolio, paper_trades, strategies, news, market
    """
    return {
        "watchlist": _get_watchlist_data(symbol),
        "portfolio": _get_portfolio_data(symbol),
        "paper_trades": _get_paper_trades_data(symbol) if include_paper_trades else None,
        "strategies": _get_strategies_data(symbol) if include_strategies else None,
        "news": _get_news_data(symbol),
        "market": _get_market_data() if include_market else {},
    }


def _build_response(
    symbol: str, include_market: bool, include_paper_trades: bool, include_strategies: bool
) -> SymbolIntelligenceResponse:
    """Build the full intelligence response synchronously."""
    symbol = symbol.upper()

    # Fetch all data
    data = _fetch_all_data(symbol, include_market, include_paper_trades, include_strategies)
    watchlist = data["watchlist"]
    portfolio = data["portfolio"]
    paper_trades = data["paper_trades"]
    strategies = data["strategies"]
    news = data["news"]
    market = data["market"]

    # Build response
    response = SymbolIntelligenceResponse(symbol=symbol, generated_at=datetime.now(UTC))

    # Scores section
    if watchlist:
        response.scores = _build_scores_section(watchlist)

        response.signal = SignalSection(
            type=watchlist.get("signal_type"),
            strength=watchlist.get("signal_strength"),
            reasons={
                "bullish": watchlist.get("signal_reasons_bullish") or [],
                "bearish": watchlist.get("signal_reasons_bearish") or [],
            },
            avoid_flags=watchlist.get("avoid_flag_count") or 0,
        )

        response.trading = TradingSection(
            style=watchlist.get("recommended_style"),
            confidence=watchlist.get("style_confidence"),
            holding_period=watchlist.get("optimal_holding_period"),
            risk_level=watchlist.get("risk_level"),
            entry_price=watchlist.get("entry_price"),
            stop_loss=watchlist.get("stop_loss"),
            profit_target=watchlist.get("profit_target"),
            position_size_shares=watchlist.get("position_size_shares"),
            position_size_dollars=(
                watchlist.get("position_size_shares", 0) * watchlist.get("entry_price", 0)
                if watchlist.get("position_size_shares") and watchlist.get("entry_price")
                else None
            ),
        )

        # Company section (facts about the company)
        earnings_date = watchlist.get("earnings_date")
        response.company = CompanySection(
            health=watchlist.get("company_health"),
            earnings_date=str(earnings_date) if earnings_date else None,
            earnings_days_away=watchlist.get("earnings_days_away"),
        )

        # Trends section (alignment and volume)
        response.trends = TrendSection(
            short_term_aligned=watchlist.get("timeframe_short_aligned"),
            long_term_aligned=watchlist.get("timeframe_long_aligned"),
            volume_relative=watchlist.get("volume_relative"),
        )

        # Alerts section (priority indicators)
        priority_indicators = watchlist.get("priority_indicators") or []
        response.alerts = [
            AlertIndicator(
                icon=ind.get("icon", ""),
                label=ind.get("label", ""),
                tooltip=ind.get("tooltip"),
                priority=ind.get("priority", 0),
                category=ind.get("category"),
            )
            for ind in priority_indicators
            if isinstance(ind, dict)
        ]

        # News section from watchlist (richer data)
        news_intel = watchlist.get("news_intelligence") or {}
        if news_intel:
            recent_articles_raw = news_intel.get("recent_articles") or []
            response.news = NewsSection(
                sentiment_score=news_intel.get("sentiment_score"),
                sentiment_label=news_intel.get("sentiment_label"),
                article_count_24h=news_intel.get("article_count_24h") or 0,
                headline=news_intel.get("headline"),
                key_events=[
                    KeyEvent(
                        icon=e.get("icon", "") if isinstance(e, dict) else "",
                        text=e.get("text", "") if isinstance(e, dict) else str(e),
                        time_ago=e.get("time_ago", "") if isinstance(e, dict) else "",
                    )
                    for e in (news_intel.get("key_events") or [])[:3]
                ],
                recent_articles=[
                    NewsArticle(
                        headline=a.get("headline", ""),
                        source=a.get("source"),
                        published_at=a.get("published_at"),
                    )
                    for a in recent_articles_raw[:5]
                    if isinstance(a, dict)
                ],
            )

    # Portfolio section
    pos = portfolio.get("position") if portfolio else None
    summary = portfolio.get("summary") if portfolio else None
    response.portfolio = _build_portfolio_section(pos, summary)

    # Paper trades section
    if paper_trades:
        response.paper_trades = _build_paper_trades_section(paper_trades)

    # Strategies section
    if strategies and strategies.get("strategies"):
        strats = strategies["strategies"]
        best = strategies.get("best")

        response.strategies = StrategiesSection(
            active_count=strategies["active_count"],
            strategies=[
                StrategyInfo(
                    id=str(s["id"]),
                    name=s["name"],
                    strategy_type=s["strategy_type"],
                    expected_sharpe=s.get("expected_sharpe"),
                    live_sharpe=s.get("live_sharpe_ratio"),
                    win_rate=s.get("live_win_rate"),
                )
                for s in strats[:3]
            ],
            best_strategy=StrategyInfo(
                id=str(best["id"]),
                name=best["name"],
                strategy_type=best["strategy_type"],
                expected_sharpe=best.get("expected_sharpe"),
                live_sharpe=best.get("live_sharpe_ratio"),
                win_rate=best.get("live_win_rate"),
            )
            if best
            else None,
        )

    # News section fallback (only if not already populated from watchlist)
    if news and not response.news:
        response.news = NewsSection(
            sentiment_score=news.get("sentiment_score"),
            article_count_24h=news.get("article_count") or 0,
        )

    # Market section
    if market:
        fg = market.get("fear_greed") or {}
        response.market = MarketSection(
            fear_greed_score=fg.get("score"),
            fear_greed_label=fg.get("label"),
            vix=market.get("vix"),
            sp500_change=market.get("sp500_change"),
        )

    # Generate recommendation
    response.recommendation = RecommendationSection(
        **_generate_recommendation(watchlist, portfolio, market)
    )

    return response


@router.get("/{symbol}/intelligence", response_model=SymbolIntelligenceResponse)
async def get_symbol_intelligence(
    symbol: str,
    include_market: bool = True,
    include_paper_trades: bool = True,
    include_strategies: bool = True,
) -> SymbolIntelligenceResponse:
    """Get comprehensive intelligence for a symbol.

    Returns all relevant data in one call:
    - Watchlist scores and signals
    - Portfolio position (if held)
    - Paper trading history
    - Active strategies
    - News sentiment
    - Market context
    - Personalized recommendation
    """
    try:
        return await run_in_threadpool(
            _build_response, symbol, include_market, include_paper_trades, include_strategies
        )
    except Exception as e:
        logger.exception(f"Error getting symbol intelligence for {symbol}")
        return SymbolIntelligenceResponse(
            symbol=symbol.upper(), generated_at=datetime.now(UTC), error=str(e)
        )
