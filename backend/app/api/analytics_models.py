"""Response models for analytics API endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
        None,
        description="Short percent of shares outstanding",
        alias="short_percent_of_outstanding",
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
    cash_conversion_ratio: float | None = Field(
        None, description="Cash conversion ratio (OCF / Net Income)"
    )
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


class FinancialHealthResponse(BaseModel):
    """Response model for financial health scores."""

    symbol: str = Field(..., description="Stock symbol")
    piotroski_fscore: int | None = Field(
        None, ge=0, le=9, description="Piotroski F-Score (0-9, higher is better)"
    )
    fscore_components: dict[str, int] | None = Field(
        None, description="Individual F-Score component scores"
    )
    altman_zscore: float | None = Field(None, description="Altman Z-Score")
    zscore_zone: str | None = Field(None, description="Z-Score zone: 'safe', 'grey', or 'distress'")
    error: str | None = Field(None, description="Error message if calculation failed")
