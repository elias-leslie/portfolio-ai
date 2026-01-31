"""Analytics API router for trading intelligence endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from app.analytics import (
    calculate_rvol,
    get_peer_comparison,
    get_peer_group_detail,
    get_sector_rotation,
)
from app.analytics.financial_data import (
    get_cash_flow_metrics,
    get_insider_transactions,
    get_institutional_holdings,
    get_short_interest,
)
from app.analytics.financial_health_scores import get_financial_health_scores
from app.api.analytics_models import (
    CashFlowMetricsResponse,
    FinancialHealthResponse,
    InsiderTransactionResponse,
    InsiderTransactionsListResponse,
    InstitutionalHoldingResponse,
    InstitutionalSummaryResponse,
    PeerComparisonResponse,
    PeerDetailItem,
    PeerGroupDetailResponse,
    RVOLResponse,
    SectorMomentumItem,
    SectorRotationResponse,
    ShortInterestResponse,
)
from app.api.analytics_utils import interpret_rvol, parse_date_param, safe_round, validate_group_by
from app.storage import get_storage

router = APIRouter(prefix="/api/analytics", tags=["analytics"])
storage = get_storage()


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
    """Get Relative Volume (RVOL) for a symbol."""
    target_date = parse_date_param(date)
    rvol = calculate_rvol(storage, symbol.upper(), target_date, lookback_days)

    if rvol is None:
        raise HTTPException(
            status_code=404,
            detail=f"Could not calculate RVOL for {symbol} on {target_date}. "
            "Insufficient data available.",
        )

    return RVOLResponse(
        symbol=symbol.upper(),
        date=target_date.isoformat(),
        rvol=round(rvol, 2),
        interpretation=interpret_rvol(rvol),
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
    """Get sector rotation analysis showing relative sector momentum."""
    target_date = parse_date_param(date)
    rotation = get_sector_rotation(storage, target_date, lookback_days)

    if rotation is None or len(rotation) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Could not calculate sector rotation for {target_date}. "
            "Insufficient data available.",
        )

    sectors = [
        SectorMomentumItem(
            sector=row["sector"],
            momentum_5d=safe_round(row["momentum_5d"]),
            momentum_20d=safe_round(row["momentum_20d"]),
            num_stocks=row["num_stocks"],
            avg_volume=row["avg_volume"],
        )
        for row in rotation.iter_rows(named=True)
    ]

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
    """Get peer comparison analysis for a symbol."""
    target_date = parse_date_param(date)
    validate_group_by(group_by)

    comparison = get_peer_comparison(storage, symbol.upper(), target_date, lookback_days, group_by)

    if comparison is None or len(comparison) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Could not calculate peer comparison for {symbol} on {target_date}. "
            "Symbol not found or insufficient data available.",
        )

    return PeerComparisonResponse(
        symbol=symbol.upper(),
        sector=comparison[group_by][0],
        date=target_date.isoformat(),
        return_5d=safe_round(comparison["return_5d"][0]),
        return_20d=safe_round(comparison["return_20d"][0]),
        sector_avg_5d=safe_round(comparison["sector_avg_5d"][0]),
        sector_avg_20d=safe_round(comparison["sector_avg_20d"][0]),
        relative_perf_5d=safe_round(comparison["relative_perf_5d"][0]),
        relative_perf_20d=safe_round(comparison["relative_perf_20d"][0]),
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
    """Get detailed peer group rankings for a symbol."""
    target_date = parse_date_param(date)
    validate_group_by(group_by)

    peers = get_peer_group_detail(storage, symbol.upper(), target_date, lookback_days, group_by)

    if peers is None or len(peers) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Could not get peer group detail for {symbol} on {target_date}. "
            "Symbol not found or insufficient data available.",
        )

    sector_name = peers[group_by][0]
    peer_items = [
        PeerDetailItem(
            symbol=row["symbol"],
            sector=row[group_by],
            return_5d=safe_round(row["return_5d"]),
            return_20d=safe_round(row["return_20d"]),
            rank=row["rank"],
            is_target=row["is_target"],
        )
        for row in peers.iter_rows(named=True)
    ]

    return PeerGroupDetailResponse(
        symbol=symbol.upper(),
        sector=sector_name,
        date=target_date.isoformat(),
        peers=peer_items,
        count=len(peer_items),
    )


@router.get("/short-interest/{symbol}", response_model=ShortInterestResponse)
async def get_short_interest_endpoint(
    symbol: Annotated[str, Path(description="Stock symbol (e.g., AAPL)")],
) -> ShortInterestResponse:
    """Get short interest data for a symbol."""
    data = get_short_interest(symbol.upper())
    if data is None:
        raise HTTPException(404, f"No short interest data found for {symbol.upper()}")
    return ShortInterestResponse(**data.__dict__)


@router.get("/cash-flow/{symbol}", response_model=CashFlowMetricsResponse)
async def get_cash_flow_metrics_endpoint(
    symbol: Annotated[str, Path(description="Stock symbol (e.g., AAPL)")],
) -> CashFlowMetricsResponse:
    """Get cash flow metrics for a symbol."""
    data = get_cash_flow_metrics(symbol.upper())
    if data is None:
        raise HTTPException(404, f"No cash flow metrics found for {symbol.upper()}")
    return CashFlowMetricsResponse(**data.__dict__)


@router.get("/insider-transactions/{symbol}", response_model=InsiderTransactionsListResponse)
async def get_insider_transactions_endpoint(
    symbol: Annotated[str, Path(description="Stock symbol (e.g., AAPL)")],
    limit: Annotated[int, Query(description="Max transactions to return", ge=1, le=100)] = 20,
) -> InsiderTransactionsListResponse:
    """Get SEC Form 4 insider transactions for a symbol."""
    data = get_insider_transactions(symbol.upper(), limit)
    transactions = [InsiderTransactionResponse(**t.__dict__) for t in data]
    return InsiderTransactionsListResponse(
        symbol=symbol.upper(), transactions=transactions, count=len(transactions)
    )


@router.get("/institutional-holdings/{symbol}", response_model=InstitutionalSummaryResponse)
async def get_institutional_holdings_endpoint(
    symbol: Annotated[str, Path(description="Stock symbol (e.g., AAPL)")],
    top_n: Annotated[int, Query(description="Number of top holders to include", ge=1, le=50)] = 10,
) -> InstitutionalSummaryResponse:
    """Get 13F institutional holdings for a symbol."""
    data = get_institutional_holdings(symbol.upper(), top_n)
    if data is None:
        raise HTTPException(404, f"No institutional holdings found for {symbol.upper()}")
    top_holders = [InstitutionalHoldingResponse(**h.__dict__) for h in data.top_holders]
    return InstitutionalSummaryResponse(**{**data.__dict__, "top_holders": top_holders})


@router.get("/health-scores/{symbol}", response_model=FinancialHealthResponse)
async def get_health_scores(
    symbol: Annotated[str, Path(description="Stock symbol (e.g., AAPL)")],
) -> FinancialHealthResponse:
    """Get Piotroski F-Score (0-9) and Altman Z-Score for bankruptcy risk."""
    scores = get_financial_health_scores(symbol.upper())
    return FinancialHealthResponse(
        symbol=scores.symbol,
        piotroski_fscore=scores.f_score,
        fscore_components=scores.f_score_components,
        altman_zscore=scores.z_score,
        zscore_zone=scores.z_score_zone,
        error=scores.error,
    )
