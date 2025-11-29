
import datetime as dt
from app.storage import get_storage
import pandas as pd

def test_freshness_query():
    storage = get_storage()
    with storage.connection() as conn:
        # Get all watchlist items with last snapshot timestamp
        result = conn.execute(
            """
            SELECT
                wi.symbol,
                MAX(ws.fetched_at) as last_fetched
            FROM watchlist_items wi
            LEFT JOIN watchlist_snapshots ws ON wi.id = ws.item_id
            GROUP BY wi.symbol
            """
        ).df()
        
        print(f"Type of result: {type(result)}")
        print(f"Columns: {result.columns}")
        print(f"Empty: {result.empty}")
        print(result)
        
        if not result.empty:
             now = dt.datetime.now(dt.UTC)
             # Check if last_fetched is datetime
             print(f"Type of last_fetched: {result['last_fetched'].dtype}")
             
             # Try calculation
             try:
                 result["age_hours"] = (now - result["last_fetched"]).dt.total_seconds() / 3600
                 print("Calculation successful")
                 print(result["age_hours"])
             except Exception as e:
                 print(f"Calculation failed: {e}")

if __name__ == "__main__":
    test_freshness_query()
