"""
Buyback data source using yfinance cash flow statements.

Extracts 'Repurchase Of Capital Stock' from quarterly cash flow data.
FEAT-175: Share Buybacks
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import yfinance as yf

from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

logger = get_logger(__name__)


def fetch_buyback_data(symbol: str) -> list[dict]:
    """
    Fetch buyback (share repurchase) data from yfinance cash flow.

    Args:
        symbol: Stock ticker symbol

    Returns:
        List of buyback records with date and amount
    """
    try:
        ticker = yf.Ticker(symbol)
        cf = ticker.quarterly_cashflow

        if cf is None or cf.empty:
            logger.debug("no_cashflow_data", symbol=symbol)
            return []

        # Look for repurchase row
        repurchase_rows = [r for r in cf.index if "repurchase" in str(r).lower()]
        if not repurchase_rows:
            logger.debug("no_repurchase_data", symbol=symbol)
            return []

        row_name = repurchase_rows[0]
        buybacks = []

        for col in cf.columns:
            value = cf.loc[row_name, col]
            if value is not None and value < 0:  # Repurchases are negative (cash outflow)
                action_date = col.date() if hasattr(col, "date") else col
                buybacks.append(
                    {
                        "symbol": symbol,
                        "action_type": "buyback",
                        "action_date": action_date,
                        "repurchase_amount": abs(float(value)),  # Store as positive
                        "source": "yfinance",
                    }
                )

        logger.info(
            "buyback_data_fetched",
            symbol=symbol,
            records=len(buybacks),
        )
        return buybacks

    except Exception as e:
        logger.error(
            "buyback_fetch_failed",
            symbol=symbol,
            error=str(e),
            error_type=type(e).__name__,
        )
        return []


def store_buyback_data(
    storage: PortfolioStorage,
    buybacks: list[dict],
) -> int:
    """
    Store buyback data in corporate_actions table.

    Args:
        storage: Database storage facade
        buybacks: List of buyback records

    Returns:
        Number of records upserted
    """
    if not buybacks:
        return 0

    sql = """
        INSERT INTO corporate_actions (
            symbol, action_type, action_date, repurchase_amount, source
        ) VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (symbol, action_type, action_date)
        DO UPDATE SET
            repurchase_amount = EXCLUDED.repurchase_amount,
            source = EXCLUDED.source,
            updated_at = NOW()
    """

    with storage.connection() as conn:
        for record in buybacks:
            conn.execute(
                sql,
                [
                    record["symbol"],
                    record["action_type"],
                    record["action_date"],
                    record["repurchase_amount"],
                    record["source"],
                ],
            )
        conn.commit()

    logger.info("buybacks_stored", count=len(buybacks))
    return len(buybacks)


def fetch_and_store_buybacks(
    storage: PortfolioStorage,
    symbols: list[str],
) -> dict:
    """
    Fetch and store buyback data for multiple symbols.

    Args:
        storage: Database storage facade
        symbols: List of stock symbols

    Returns:
        Summary dict with success/failure counts
    """
    total_stored = 0
    failed_symbols = []

    for symbol in symbols:
        try:
            buybacks = fetch_buyback_data(symbol)
            if buybacks:
                stored = store_buyback_data(storage, buybacks)
                total_stored += stored
        except Exception as e:
            logger.error(
                "symbol_buyback_failed",
                symbol=symbol,
                error=str(e),
            )
            failed_symbols.append(symbol)

    return {
        "symbols_processed": len(symbols),
        "records_stored": total_stored,
        "failed_symbols": failed_symbols,
    }
