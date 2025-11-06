# SEC EDGAR Schema Fix - Polars Type Compatibility Issue

**Status**: Debugging in progress
**Error**: `polars.exceptions.SchemaError: type String is incompatible with expected type Null`
**Location**: `multi_source_fetcher.py:420` during `pl.concat(all_data, how="diagonal")`

---

## Root Cause

When Polars concatenates dataframes with `how="diagonal"`, it attempts to align schemas. However, if one dataframe has a column with all `None` values (inferred as `Null` type) and another has `String` values, concat fails.

## Schemas Observed

### YFinance, Finnhub, Polygon (10 columns each)
```
ticker: String
headline: String
url: String
summary: String
news_source_name: String
author: Null  ← PROBLEM: Inferred as Null type
image_url: String
published_at: Datetime
raw_payload: String
source: String
```

### SEC EDGAR (14 columns)
```
All above columns PLUS:
vendor: String
filing_type: String
is_material_event: Boolean
plain_language_headline: String

BUT with explicit Null casting:
author: Utf8 (cast from Null)
image_url: Utf8 (cast from Null)
raw_payload: Utf8 (cast from Null)
```

## Attempted Fixes (Failed)

1. ✅ Added standard schema fields to SEC EDGAR → Still fails
2. ✅ Changed concat to `how="diagonal"` → Still fails
3. ✅ Explicit type casting in SEC EDGAR → Still fails

**Issue**: The problem is OTHER sources have `Null` type for `author` column, not SEC EDGAR!

---

## Solution (To Implement)

### Option A: Fix at Source Level (RECOMMENDED)
Add explicit type casting to **ALL** news sources for nullable columns:

**Files to modify**:
1. `backend/app/sources/yfinance_source.py:fetch_news_payload()`
2. `backend/app/sources/polygon_source.py:fetch_news_payload()`
3. `backend/app/sources/finnhub_source.py:fetch_news_payload()`
4. All RSS sources in `backend/app/sources/rss_source.py`

**Change**: After creating dataframe from records, add:
```python
df = pl.from_dicts(records)

# Explicitly cast nullable columns to String type
if len(df) > 0:
    df = df.with_columns([
        pl.col("author").cast(pl.Utf8, strict=False),
        pl.col("image_url").cast(pl.Utf8, strict=False),
        # Any other nullable columns
    ])

return df
```

### Option B: Fix at Concat Level
Add schema normalization in `multi_source_fetcher.py` before concat:

```python
def _normalize_news_schema(df: pl.DataFrame) -> pl.DataFrame:
    """Ensure consistent schema across all news sources."""
    # Define expected schema with explicit types
    schema_casts = {
        "ticker": pl.Utf8,
        "headline": pl.Utf8,
        "url": pl.Utf8,
        "summary": pl.Utf8,
        "news_source_name": pl.Utf8,
        "author": pl.Utf8,  # Cast Null → Utf8
        "image_url": pl.Utf8,  # Cast Null → Utf8
        "published_at": pl.Datetime("us", "UTC"),
        "raw_payload": pl.Utf8,  # Cast Null → Utf8
        "source": pl.Utf8,
    }

    # Apply casts
    for col, dtype in schema_casts.items():
        if col in df.columns:
            df = df.with_columns(pl.col(col).cast(dtype, strict=False))

    return df

# In fetch_with_fallback, before concat:
all_data = [_normalize_news_schema(df) for df in all_data]
combined = pl.concat(all_data, how="diagonal")
```

### Option C: Disable SEC EDGAR Temporarily
Set `SEC_EDGAR_ENABLED=0` in environment until fixed.

---

## Testing the Fix

```bash
cd ~/portfolio-ai/backend && source .venv/bin/activate

# Test after fix
python3 << 'EOF'
from app.services.news_service import NewsService
from app.storage import get_storage

news_service = NewsService(get_storage())
news_service._refresh_cache(ticker="NVDA", query="NVDA", max_articles=10)

news = news_service.build_news_payload(tickers=["NVDA"], lookback_hours=24*7)
print(f"✅ SUCCESS! Found {len(news)} articles")

# Check sources
sources = {}
for article in news:
    sources[article.get('vendor', 'unknown')] = sources.get(article.get('vendor', 'unknown'), 0) + 1

print("\nArticles by source:")
for vendor, count in sorted(sources.items()):
    print(f"  {vendor}: {count}")
EOF
```

---

## Next Steps

1. Implement Option A or B (recommend Option B for centralized fix)
2. Test with multiple tickers
3. Verify SEC filing metadata appears in responses
4. Complete Phase 1 testing
5. Update WORK_TRACKER.md

**Estimated time**: 30-60 minutes

---

**Created**: 2025-11-06 17:17
**Last Updated**: 2025-11-06 17:17
