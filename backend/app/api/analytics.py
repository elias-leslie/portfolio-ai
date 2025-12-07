"""Analytics API router for trading intelligence endpoints."""

from __future__ import annotations

import datetime as dt
import math
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

from app.analytics import (
    calculate_rvol,
    get_peer_comparison,
    get_peer_group_detail,
    get_sector_rotation,
)
from app.storage import get_storage
from app.storage.connection import get_connection_manager

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

# Initialize storage
storage = get_storage()


# Response models
class RVOLResponse(BaseModel):
    """Response model for RVOL (Relative Volume) data."""

    symbol: str = Field(..., description="Stock symbol")
    date: str = Field(..., description="Date for RVOL calculation (YYYY-MM-DD)")
    rvol: float = Field(..., description="Relative volume ratio (1.0 = normal volume)")
    interpretation: str = Field(..., description="Human-readable interpretation of RVOL value")


class SectorMomentumItem(BaseModel):
    """Individual sector momentum data."""

    sector: str = Field(..., description="Sector name")
    momentum_5d: float | None = Field(..., description="5-day momentum (%)")
    momentum_20d: float | None = Field(..., description="20-day momentum (%)")
    num_stocks: int = Field(..., description="Number of stocks in sector")
    avg_volume: float | None = Field(..., description="Average volume across sector stocks")


class SectorRotationResponse(BaseModel):
    """Response model for sector rotation analysis."""

    date: str = Field(..., description="Date for sector rotation (YYYY-MM-DD)")
    sectors: list[SectorMomentumItem] = Field(..., description="Sectors ranked by momentum")
    count: int = Field(..., description="Number of sectors returned")


class PeerComparisonResponse(BaseModel):
    """Response model for peer comparison analysis."""

    symbol: str = Field(..., description="Stock symbol")
    sector: str = Field(..., description="Sector name")
    date: str = Field(..., description="Date for peer comparison (YYYY-MM-DD)")
    return_5d: float | None = Field(..., description="5-day return (%)")
    return_20d: float | None = Field(..., description="20-day return (%)")
    sector_avg_5d: float | None = Field(..., description="Sector average 5-day return (%)")
    sector_avg_20d: float | None = Field(..., description="Sector average 20-day return (%)")
    relative_perf_5d: float | None = Field(
        ..., description="Relative performance vs sector over 5 days (%)"
    )
    relative_perf_20d: float | None = Field(
        ..., description="Relative performance vs sector over 20 days (%)"
    )
    peer_rank: int | None = Field(..., description="Rank within peer group (1 = best)")
    peer_count: int = Field(..., description="Total number of peers")
    percentile: float | None = Field(..., description="Percentile rank (0-100, higher is better)")


class PeerDetailItem(BaseModel):
    """Individual peer performance data."""

    symbol: str = Field(..., description="Stock symbol")
    sector: str = Field(..., description="Sector name")
    return_5d: float | None = Field(..., description="5-day return (%)")
    return_20d: float | None = Field(..., description="20-day return (%)")
    rank: int = Field(..., description="Rank within peer group")
    is_target: bool = Field(..., description="Whether this is the target symbol")


class PeerGroupDetailResponse(BaseModel):
    """Response model for peer group detail."""

    symbol: str = Field(..., description="Target stock symbol")
    sector: str = Field(..., description="Sector name")
    date: str = Field(..., description="Date for peer comparison (YYYY-MM-DD)")
    peers: list[PeerDetailItem] = Field(..., description="All peers ranked by performance")
    count: int = Field(..., description="Number of peers")


class ShortInterestResponse(BaseModel):
    """Response model for short interest data."""

    model_config = {"populate_by_name": True}

    symbol: str = Field(..., description="Stock symbol")
    as_of_date: str = Field(..., description="Date of short interest data (YYYY-MM-DD)")
    short_shares: float | None = Field(None, description="Number of shares sold short")
    short_ratio: float | None = Field(None, description="Days to cover (short ratio)")
    pct_float: float | None = Field(
        None, description="Short percent of float", alias="short_percent_of_float"
    )
    pct_outstanding: float | None = Field(
        None, description="Short percent of shares outstanding", alias="short_percent_of_outstanding"
    )
    short_prior_month: float | None = Field(None, description="Short shares prior month")
    pct_change: float | None = Field(None, description="Percent change from prior month")
    source: str = Field("yfinance", description="Data source")


class CashFlowMetricsResponse(BaseModel):
    """Response model for cash flow metrics data."""

    symbol: str = Field(..., description="Stock symbol")
    as_of_date: str = Field(..., description="Date of cash flow data (YYYY-MM-DD)")
    operating_cash_flow: float | None = Field(None, description="Operating cash flow")
    free_cash_flow: float | None = Field(None, description="Free cash flow")
    capital_expenditure: float | None = Field(None, description="Capital expenditure")
    fcf_yield: float | None = Field(None, description="FCF yield (FCF / Market Cap)")
    cash_flow_margin: float | None = Field(None, description="Cash flow margin (OCF / Revenue)")
    fcf_per_share: float | None = Field(None, description="Free cash flow per share")
    cash_conversion_ratio: float | None = Field(None, description="Cash conversion ratio (OCF / Net Income)")
    source: str = Field("yfinance", description="Data source")


class InsiderTransactionResponse(BaseModel):
    """Response model for insider transaction data."""

    symbol: str = Field(..., description="Stock symbol")
    insider_name: str | None = Field(None, description="Name of insider")
    insider_title: str | None = Field(None, description="Title of insider")
    transaction_type: str | None = Field(None, description="Transaction type (Buy, Sell, etc.)")
    transaction_date: str | None = Field(None, description="Transaction date")
    shares: float | None = Field(None, description="Number of shares")
    value: float | None = Field(None, description="Transaction value")
    shares_owned_after: float | None = Field(None, description="Shares owned after transaction")


class InsiderTransactionsListResponse(BaseModel):
    """Response model for list of insider transactions."""

    symbol: str = Field(..., description="Stock symbol")
    transactions: list[InsiderTransactionResponse] = Field(default_factory=list)
    count: int = Field(0, description="Number of transactions")


class InstitutionalHoldingResponse(BaseModel):
    """Response model for institutional holding data."""

    symbol: str = Field(..., description="Stock symbol")
    holder_name: str | None = Field(None, description="Name of institutional holder")
    shares: float | None = Field(None, description="Number of shares held")
    value: float | None = Field(None, description="Value of holdings")
    pct_held: float | None = Field(None, description="Percent of company held")
    pct_change: float | None = Field(None, description="Change from prior period")
    report_date: str | None = Field(None, description="Report date")


class InstitutionalSummaryResponse(BaseModel):
    """Response model for institutional ownership summary."""

    symbol: str = Field(..., description="Stock symbol")
    as_of_date: str | None = Field(None, description="As of date")
    total_institutions: int | None = Field(None, description="Total number of institutions")
    total_shares_held: float | None = Field(None, description="Total shares held by institutions")
    pct_held_institutions: float | None = Field(None, description="Percent held by institutions")
    pct_held_insiders: float | None = Field(None, description="Percent held by insiders")
    institutions_increased: int | None = Field(None, description="Institutions that increased")
    institutions_decreased: int | None = Field(None, description="Institutions that decreased")
    top_holders: list[InstitutionalHoldingResponse] = Field(default_factory=list)


# Endpoints


@router.get("/rvol/{symbol}", response_model=RVOLResponse)
async def get_rvol(
    symbol: Annotated[str, Path(description="Stock symbol (e.g., AAPL)")],
    date: Annotated[
        str | None,
        Query(description="Date for RVOL calculation (YYYY-MM-DD). Defaults to today."),
    ] = None,
    lookback_days: Annotated[
        int, Query(description="Lookback period for RVOL calculation", ge=5, le=60)
    ] = 20,
) -> RVOLResponse:
    """Get Relative Volume (RVOL) for a symbol.

    RVOL measures current trading volume relative to the average volume
    over a lookback period. Values > 1.0 indicate above-average volume.

    Args:
        symbol: Stock symbol (e.g., "AAPL")
        date: Date for RVOL calculation (YYYY-MM-DD). Defaults to today.
        lookback_days: Number of trading days to average (default: 20)

    Returns:
        RVOLResponse with RVOL value and interpretation

    Raises:
        HTTPException: If symbol not found or insufficient data
    """
    # Default to today's date if not provided
    if date is None:
        target_date = dt.date.today()
    else:
        try:
            target_date = dt.datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date format: {date}. Use YYYY-MM-DD format.",
            ) from None

    # Calculate RVOL
    rvol = calculate_rvol(storage, symbol.upper(), target_date, lookback_days)

    if rvol is None:
        raise HTTPException(
            status_code=404,
            detail=f"Could not calculate RVOL for {symbol} on {target_date}. "
            "Insufficient data available.",
        )

    # Interpret RVOL value
    if rvol >= 2.0:
        interpretation = "Very high volume (2x+ normal)"
    elif rvol >= 1.5:
        interpretation = "High volume (1.5-2x normal)"
    elif rvol >= 1.0:
        interpretation = "Above average volume"
    elif rvol >= 0.5:
        interpretation = "Below average volume"
    else:
        interpretation = "Very low volume (<0.5x normal)"

    return RVOLResponse(
        symbol=symbol.upper(),
        date=target_date.isoformat(),
        rvol=round(rvol, 2),
        interpretation=interpretation,
    )


@router.get("/sectors/rotation", response_model=SectorRotationResponse)
async def get_sectors_rotation(
    date: Annotated[
        str | None,
        Query(description="Date for sector rotation (YYYY-MM-DD). Defaults to today."),
    ] = None,
    lookback_days: Annotated[
        int, Query(description="Lookback period for momentum calculation", ge=10, le=60)
    ] = 20,
) -> SectorRotationResponse:
    """Get sector rotation analysis showing relative sector momentum.

    Analyzes performance across all sectors to identify sector rotation
    patterns and relative strength.

    Args:
        date: Date for sector rotation (YYYY-MM-DD). Defaults to today.
        lookback_days: Lookback period for momentum calculation (default: 20)

    Returns:
        SectorRotationResponse with sectors ranked by momentum

    Raises:
        HTTPException: If insufficient data available
    """
    # Default to today's date if not provided
    if date is None:
        target_date = dt.date.today()
    else:
        try:
            target_date = dt.datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date format: {date}. Use YYYY-MM-DD format.",
            ) from None

    # Get sector rotation data
    rotation = get_sector_rotation(storage, target_date, lookback_days)

    if rotation is None or len(rotation) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Could not calculate sector rotation for {target_date}. "
            "Insufficient data available.",
        )

    # Convert to response model
    sectors = []
    for row in rotation.iter_rows(named=True):
        sectors.append(
            SectorMomentumItem(
                sector=row["sector"],
                momentum_5d=round(row["momentum_5d"], 2) if row["momentum_5d"] else None,
                momentum_20d=(round(row["momentum_20d"], 2) if row["momentum_20d"] else None),
                num_stocks=row["num_stocks"],
                avg_volume=row["avg_volume"],
            )
        )

    return SectorRotationResponse(
        date=target_date.isoformat(),
        sectors=sectors,
        count=len(sectors),
    )


@router.get("/peers/{symbol}", response_model=PeerComparisonResponse)
async def get_peer_comp(
    symbol: Annotated[str, Path(description="Stock symbol (e.g., AAPL)")],
    date: Annotated[
        str | None,
        Query(description="Date for peer comparison (YYYY-MM-DD). Defaults to today."),
    ] = None,
    group_by: Annotated[
        str, Query(description='Grouping method: "sector" or "industry"')
    ] = "sector",
    lookback_days: Annotated[
        int, Query(description="Lookback period for momentum calculation", ge=10, le=60)
    ] = 20,
) -> PeerComparisonResponse:
    """Get peer comparison analysis for a symbol.

    Compares a symbol's performance against its sector or industry peers
    to identify relative strength and positioning.

    Args:
        symbol: Stock symbol (e.g., "AAPL")
        date: Date for peer comparison (YYYY-MM-DD). Defaults to today.
        group_by: Grouping method - "sector" or "industry" (default: "sector")
        lookback_days: Lookback period for momentum calculation (default: 20)

    Returns:
        PeerComparisonResponse with peer rank and relative performance

    Raises:
        HTTPException: If symbol not found or insufficient data
    """
    # Default to today's date if not provided
    if date is None:
        target_date = dt.date.today()
    else:
        try:
            target_date = dt.datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date format: {date}. Use YYYY-MM-DD format.",
            ) from None

    # Validate group_by parameter
    if group_by not in ["sector", "industry"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid group_by parameter: {group_by}. Use 'sector' or 'industry'.",
        )

    # Get peer comparison data
    comparison = get_peer_comparison(storage, symbol.upper(), target_date, lookback_days, group_by)

    if comparison is None or len(comparison) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Could not calculate peer comparison for {symbol} on {target_date}. "
            "Symbol not found or insufficient data available.",
        )

    # Extract data from DataFrame - access scalars directly
    return PeerComparisonResponse(
        symbol=symbol.upper(),
        sector=comparison[group_by][0],
        date=target_date.isoformat(),
        return_5d=(
            round(comparison["return_5d"][0], 2) if comparison["return_5d"][0] is not None else None
        ),
        return_20d=(
            round(comparison["return_20d"][0], 2)
            if comparison["return_20d"][0] is not None
            else None
        ),
        sector_avg_5d=(
            round(comparison["sector_avg_5d"][0], 2)
            if comparison["sector_avg_5d"][0] is not None
            else None
        ),
        sector_avg_20d=(
            round(comparison["sector_avg_20d"][0], 2)
            if comparison["sector_avg_20d"][0] is not None
            else None
        ),
        relative_perf_5d=(
            round(comparison["relative_perf_5d"][0], 2)
            if comparison["relative_perf_5d"][0] is not None
            else None
        ),
        relative_perf_20d=(
            round(comparison["relative_perf_20d"][0], 2)
            if comparison["relative_perf_20d"][0] is not None
            else None
        ),
        peer_rank=comparison["peer_rank"][0],
        peer_count=comparison["peer_count"][0],
        percentile=comparison["percentile"][0],
    )


@router.get("/peers/{symbol}/detail", response_model=PeerGroupDetailResponse)
async def get_peer_group_det(
    symbol: Annotated[str, Path(description="Stock symbol (e.g., AAPL)")],
    date: Annotated[
        str | None,
        Query(description="Date for peer comparison (YYYY-MM-DD). Defaults to today."),
    ] = None,
    group_by: Annotated[
        str, Query(description='Grouping method: "sector" or "industry"')
    ] = "sector",
    lookback_days: Annotated[
        int, Query(description="Lookback period for momentum calculation", ge=10, le=60)
    ] = 20,
) -> PeerGroupDetailResponse:
    """Get detailed peer group rankings for a symbol.

    Returns ranked list of all stocks in the same sector or industry as the
    target symbol, showing their relative performance.

    Args:
        symbol: Stock symbol (e.g., "AAPL")
        date: Date for peer comparison (YYYY-MM-DD). Defaults to today.
        group_by: Grouping method - "sector" or "industry" (default: "sector")
        lookback_days: Lookback period for momentum calculation (default: 20)

    Returns:
        PeerGroupDetailResponse with all peers ranked by performance

    Raises:
        HTTPException: If symbol not found or insufficient data
    """
    # Default to today's date if not provided
    if date is None:
        target_date = dt.date.today()
    else:
        try:
            target_date = dt.datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date format: {date}. Use YYYY-MM-DD format.",
            ) from None

    # Validate group_by parameter
    if group_by not in ["sector", "industry"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid group_by parameter: {group_by}. Use 'sector' or 'industry'.",
        )

    # Get peer group detail
    peers = get_peer_group_detail(storage, symbol.upper(), target_date, lookback_days, group_by)

    if peers is None or len(peers) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Could not get peer group detail for {symbol} on {target_date}. "
            "Symbol not found or insufficient data available.",
        )

    # Get sector/industry name from first row
    sector_name = peers[group_by][0]

    # Convert to response model
    peer_items = []
    for row in peers.iter_rows(named=True):
        peer_items.append(
            PeerDetailItem(
                symbol=row["symbol"],
                sector=row[group_by],
                return_5d=round(row["return_5d"], 2) if row["return_5d"] else None,
                return_20d=round(row["return_20d"], 2) if row["return_20d"] else None,
                rank=row["rank"],
                is_target=row["is_target"],
            )
        )

    return PeerGroupDetailResponse(
        symbol=symbol.upper(),
        sector=sector_name,
        date=target_date.isoformat(),
        peers=peer_items,
        count=len(peer_items),
    )


@router.get("/short-interest/{symbol}", response_model=ShortInterestResponse)
async def get_short_interest(
    symbol: Annotated[str, Path(description="Stock symbol (e.g., AAPL)")],
) -> ShortInterestResponse:
    """Get short interest data for a symbol.

    Returns the most recent short interest data including short ratio,
    percent of float, and changes from prior period.

    Args:
        symbol: Stock symbol (e.g., "AAPL")

    Returns:
        ShortInterestResponse with short interest metrics

    Raises:
        HTTPException: If symbol not found or no data available
    """
    mgr = get_connection_manager()
    with mgr.connection() as conn:
        result = conn.execute(
            """
            SELECT symbol, as_of_date, short_shares, short_ratio,
                   short_percent_of_float, short_percent_of_outstanding,
                   short_prior_month, short_pct_change, source
            FROM short_interest
            WHERE symbol = %s
            ORDER BY as_of_date DESC
            LIMIT 1
            """,
            (symbol.upper(),),
        )
        row = result.fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No short interest data found for {symbol.upper()}",
        )

    return ShortInterestResponse(
        symbol=row[0],
        as_of_date=row[1].isoformat() if row[1] else None,
        short_shares=row[2],
        short_ratio=row[3],
        pct_float=row[4],
        pct_outstanding=row[5],
        short_prior_month=row[6],
        pct_change=row[7],
        source=row[8] or "yfinance",
    )


@router.get("/cash-flow/{symbol}", response_model=CashFlowMetricsResponse)
async def get_cash_flow_metrics(
    symbol: Annotated[str, Path(description="Stock symbol (e.g., AAPL)")],
) -> CashFlowMetricsResponse:
    """Get cash flow metrics for a symbol.

    Returns FCF yield, operating cash flow, conversion ratio and other metrics.
    """
    mgr = get_connection_manager()
    with mgr.connection() as conn:
        result = conn.execute(
            """
            SELECT symbol, as_of_date, operating_cash_flow, free_cash_flow,
                   capital_expenditure, fcf_yield, cash_flow_margin,
                   fcf_per_share, cash_conversion_ratio, source
            FROM cash_flow_metrics
            WHERE symbol = %s
            ORDER BY as_of_date DESC
            LIMIT 1
            """,
            (symbol.upper(),),
        )
        row = result.fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No cash flow metrics found for {symbol.upper()}",
        )

    return CashFlowMetricsResponse(
        symbol=row[0],
        as_of_date=row[1].isoformat() if row[1] else None,
        operating_cash_flow=row[2],
        free_cash_flow=row[3],
        capital_expenditure=row[4],
        fcf_yield=row[5],
        cash_flow_margin=row[6],
        fcf_per_share=row[7],
        cash_conversion_ratio=row[8],
        source=row[9] or "yfinance",
    )


@router.get("/insider-transactions/{symbol}", response_model=InsiderTransactionsListResponse)
async def get_insider_transactions(
    symbol: Annotated[str, Path(description="Stock symbol (e.g., AAPL)")],
    limit: Annotated[int, Query(description="Max transactions to return", ge=1, le=100)] = 20,
) -> InsiderTransactionsListResponse:
    """Get SEC Form 4 insider transactions for a symbol.

    Returns buy/sell tracking data from insider filings.
    """
    mgr = get_connection_manager()
    with mgr.connection() as conn:
        result = conn.execute(
            """
            SELECT symbol, insider_name, insider_title, transaction_type,
                   transaction_date, shares, value, shares_owned_after
            FROM insider_transactions
            WHERE symbol = %s
            ORDER BY transaction_date DESC
            LIMIT %s
            """,
            (symbol.upper(), limit),
        )
        rows = result.fetchall()

    def safe_float(val: float | None) -> float | None:
        """Convert NaN to None for JSON serialization."""
        if val is None:
            return None
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return None
        return val

    transactions = [
        InsiderTransactionResponse(
            symbol=row[0],
            insider_name=row[1],
            insider_title=row[2],
            transaction_type=row[3],
            transaction_date=row[4].isoformat() if row[4] else None,
            shares=safe_float(row[5]),
            value=safe_float(row[6]),
            shares_owned_after=safe_float(row[7]),
        )
        for row in rows
    ]

    return InsiderTransactionsListResponse(
        symbol=symbol.upper(),
        transactions=transactions,
        count=len(transactions),
    )


@router.get("/institutional-holdings/{symbol}", response_model=InstitutionalSummaryResponse)
async def get_institutional_holdings(
    symbol: Annotated[str, Path(description="Stock symbol (e.g., AAPL)")],
    top_n: Annotated[int, Query(description="Number of top holders to include", ge=1, le=50)] = 10,
) -> InstitutionalSummaryResponse:
    """Get 13F institutional holdings for a symbol.

    Returns ownership percent and change tracking from institutional filings.
    """
    mgr = get_connection_manager()

    # Get summary data
    with mgr.connection() as conn:
        summary_result = conn.execute(
            """
            SELECT symbol, as_of_date, total_institutions, total_shares_held,
                   pct_held_institutions, pct_held_insiders,
                   institutions_increased, institutions_decreased
            FROM institutional_ownership_summary
            WHERE symbol = %s
            ORDER BY as_of_date DESC
            LIMIT 1
            """,
            (symbol.upper(),),
        )
        summary_row = summary_result.fetchone()

        # Get top holders
        holders_result = conn.execute(
            """
            SELECT symbol, holder_name, shares, value, pct_held, pct_change, report_date
            FROM institutional_holdings
            WHERE symbol = %s
            ORDER BY value DESC NULLS LAST
            LIMIT %s
            """,
            (symbol.upper(), top_n),
        )
        holder_rows = holders_result.fetchall()

    top_holders = [
        InstitutionalHoldingResponse(
            symbol=row[0],
            holder_name=row[1],
            shares=row[2],
            value=row[3],
            pct_held=row[4],
            pct_change=row[5],
            report_date=row[6].isoformat() if row[6] else None,
        )
        for row in holder_rows
    ]

    if summary_row is None and not top_holders:
        raise HTTPException(
            status_code=404,
            detail=f"No institutional holdings found for {symbol.upper()}",
        )

    return InstitutionalSummaryResponse(
        symbol=symbol.upper(),
        as_of_date=summary_row[1].isoformat() if summary_row and summary_row[1] else None,
        total_institutions=summary_row[2] if summary_row else None,
        total_shares_held=summary_row[3] if summary_row else None,
        pct_held_institutions=summary_row[4] if summary_row else None,
        pct_held_insiders=summary_row[5] if summary_row else None,
        institutions_increased=summary_row[6] if summary_row else None,
        institutions_decreased=summary_row[7] if summary_row else None,
        top_holders=top_holders,
    )
