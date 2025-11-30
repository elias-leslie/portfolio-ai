import os
import sys
import uuid
import time
from datetime import date, timedelta

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.storage.connection import get_connection_manager
from app.agents.tool_executors_trading import TradingTools

def verify_backend_e2e():
    storage = get_connection_manager()
    tools = TradingTools(storage)
    run_id = str(uuid.uuid4())
    
    print("=== 1. Testing Paper Trade Creation ===")
    # Create a trade with "70" confidence (should be normalized to 0.7)
    print("Creating trade with confidence_score=75.0 (expecting 0.75)...")
    result = tools.execute_store_idea(
        agent_run_id=run_id,
        title="E2E Test Trade",
        thesis="Testing end-to-end functionality",
        action="buy",
        confidence_score=75.0,
        risk_level="medium",
        reward_estimate=10.0,
        portfolio_impact=5.0,
        data_needed="None",
        risks="None"
    )
    
    idea_id = result["idea_id"]
    print(f"Created idea {idea_id}")
    
    # Verify in DB
    record = storage.query("SELECT confidence_score FROM agent_ideas WHERE id = %s", [idea_id]).to_dicts()[0]
    score = float(record["confidence_score"])
    print(f"Stored score: {score}")
    
    if abs(score - 0.75) < 0.001:
        print("✅ Confidence score normalized correctly.")
    else:
        print(f"❌ Confidence score incorrect! Expected 0.75, got {score}")
        sys.exit(1)
        
    print("\n=== 2. Testing Backtest Execution ===")
    # Run a quick backtest
    ticker = "AAPL"
    end_date = date.today().isoformat()
    start_date = (date.today() - timedelta(days=30)).isoformat()
    
    print(f"Starting backtest for {ticker} ({start_date} to {end_date})...")
    bt_result = tools.execute_run_backtest(
        agent_run_id=run_id,
        ticker=ticker,
        start_date=start_date,
        end_date=end_date
    )
    
    if bt_result["status"] == "completed":
        print(f"✅ Backtest completed successfully.")
        print(f"Sharpe: {bt_result.get('sharpe_ratio')}")
        print(f"Return: {bt_result.get('total_return_pct')}%")
    else:
        print(f"❌ Backtest failed: {bt_result.get('error')}")
        sys.exit(1)

if __name__ == "__main__":
    verify_backend_e2e()
