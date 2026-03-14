# AI Rules Validation Agent

**Tier 3 Task 3.0** - Automated validation of trading rules configuration

## Overview

The Rules Validation Agent automatically validates trading rules configuration for logical consistency and generates optimization recommendations based on recent trading performance.

## Components

### 1. Rules Validator Agent (`rules_validator_agent.py`)

Core validation logic that performs comprehensive checks on trading rules configuration.

**Validation Checks:**
- **Threshold Ranges**: RSI (0-100), percentages (0-1), drawdowns (0-100)
- **Logical Contradictions**: Min < max, escalating warnings, weight sums
- **Position Sizing Math**: Max position * typical positions <= 100%
- **Fee Assumptions**: Commission not 0, slippage 1-20 bps, institutional < retail

**CLI Usage:**
```bash
source .venv/bin/activate
python -m app.agents.rules_validator_agent
```

**Output:**
```
=== Trading Rules Validation ===

Rules Version: 1.0.0
Timestamp: 2025-12-05T00:04:59+00:00
Overall Status: WARNINGS

=== Validation Errors (1) ===

1. [WARNING] position_sizing
   Field: position_sizing.max_position_percent
   Message: Max position 25.0% * 10 positions = 250.0% exposure (>100%)
   Current: 0.25

Summary: Found: 1 warning(s)
```

### 2. Scheduled Tasks (`tasks/rules_validation_tasks.py`)

Scheduled tasks that run validation and optimization analysis automatically (via Hatchet cron workflows).

#### daily_rules_validation
- **Schedule**: Daily at 03:00 UTC
- **Runs**: All validation checks
- **Alerts**: Critical failures logged to `maintenance_log`
- **Storage**: Results stored in `rules_validation_reports` table

#### weekly_optimization_review
- **Schedule**: Monday at 03:00 UTC
- **Analyzes**: Recent 30-day trading performance
- **Generates**: Optimization recommendations
- **Updates**: Most recent validation report with recommendations

### 3. Database Schema (`migrations/076_rules_validation_reports.sql`)

```sql
CREATE TABLE rules_validation_reports (
    id SERIAL PRIMARY KEY,
    rules_version VARCHAR(50) NOT NULL,
    validation_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    overall_status VARCHAR(20) NOT NULL,  -- 'valid' | 'warnings' | 'critical'
    critical_count INTEGER NOT NULL DEFAULT 0,
    warning_count INTEGER NOT NULL DEFAULT 0,
    info_count INTEGER NOT NULL DEFAULT 0,
    validation_errors JSONB NOT NULL DEFAULT '[]'::jsonb,
    recommendations JSONB NOT NULL DEFAULT '[]'::jsonb,
    summary TEXT NOT NULL,
    performance_data JSONB
);
```

## Validation Error Categories

### Critical Errors
- **Threshold out of range**: RSI > 100, percentages > 1.0
- **Contradictory rules**: Min > max, weights don't sum to 1.0
- **Invalid position sizing**: Sector exposure > 100%

### Warnings
- **Potential over-allocation**: Max position * positions > 100%
- **Unrealistic fees**: Zero commission, extreme slippage
- **Suboptimal thresholds**: RSI < 25 (too extreme)

### Info
- **Suggestions**: Conservative position sizing, unused rules

## Optimization Recommendations

The weekly optimization review analyzes recent trading performance and suggests improvements:

**Example Recommendations:**
```json
{
  "priority": "medium",
  "category": "technical_thresholds",
  "field_path": "technical_thresholds.rsi_oversold",
  "recommendation": "Consider raising RSI oversold threshold",
  "rationale": "Current value 25 may trigger too rarely. RSI < 25 is very oversold.",
  "suggested_value": 30
}
```

## Integration with System Health

### Alerts
- **Critical failures** → `maintenance_log` table
- **System Health API** → `/api/health` shows validation status
- **Journald logs** → All validation results with syslog priorities

### Monitoring
```bash
# Check recent validation status
psql -U portfolio_app -d portfolio_ai -c "
SELECT validation_time, overall_status, summary
FROM rules_validation_reports
ORDER BY validation_time DESC LIMIT 5;
"

# View critical errors only
psql -U portfolio_app -d portfolio_ai -c "
SELECT validation_time, summary, validation_errors::text
FROM rules_validation_reports
WHERE overall_status = 'critical'
ORDER BY validation_time DESC;
"
```

## Example Workflow

1. **Daily Validation (03:00 UTC)**
   - Agent loads `app/rules/rules.yaml`
   - Runs all validation checks
   - Stores results in database
   - Logs warnings/errors
   - Alerts on critical failures

2. **Weekly Optimization (Monday 03:00 UTC)**
   - Fetches recent 30-day performance data
   - Compares rules to actual outcomes
   - Identifies underused rules
   - Suggests threshold adjustments
   - Updates validation report

3. **Manual Review**
   - View validation history in database
   - Review optimization recommendations
   - Update `rules.yaml` if needed
   - Re-run validation to verify

## Testing

```bash
# Manual test (CLI)
source .venv/bin/activate
python -m app.agents.rules_validator_agent

# Task test (Python)
source .venv/bin/activate
python3 << 'EOF'
from app.tasks.rules_validation_tasks import daily_rules_validation

result = daily_rules_validation()
print(f"Status: {result['status']}")
print(f"Errors: {result['error_count']}")
EOF
```

## Future Enhancements

1. **Performance-Based Validation**
   - Flag rules that never trigger
   - Identify redundant thresholds
   - Suggest removal of unused rules

2. **Historical Analysis**
   - Track validation trends over time
   - Alert on regressions (new errors)
   - Show coverage improvements

3. **Automated Remediation**
   - Auto-adjust minor threshold issues
   - Propose specific value changes
   - Generate git commit with fixes

4. **Integration with Strategy Generation**
   - Validate generated strategies
   - Ensure strategy parameters within rules
   - Flag strategies violating risk limits

## References

- **Rules Config**: `backend/app/rules/rules.yaml`
- **Rules Models**: `backend/app/rules/models.py`
- **Hatchet Workflows**: Cron schedules defined in Hatchet workflow definitions
- **Architecture Docs**: `docs/core/ARCHITECTURE.md`
