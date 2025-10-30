#!/usr/bin/env python3
"""Test PostgreSQL connection pooling under load."""

import concurrent.futures
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.storage.connection import get_connection_manager


def test_connection(conn_id: int) -> tuple[int, float, str]:
    """Test a single connection."""
    start = time.time()
    try:
        mgr = get_connection_manager()
        with mgr.connection() as conn:
            result = conn.execute("SELECT 1 as test, pg_backend_pid()").fetchone()
            duration = time.time() - start
            return (conn_id, duration, f"SUCCESS - PID {result[1]}")
    except Exception as e:
        duration = time.time() - start
        return (conn_id, duration, f"FAILED - {str(e)}")


def main():
    """Run connection pool stress test."""
    print("Testing PostgreSQL connection pool...")
    print("Pool config: size=20, max_overflow=10 (max 30 concurrent)")
    print()

    # Test with 35 connections (exceeds pool_size + max_overflow)
    num_connections = 35
    print(f"Opening {num_connections} connections concurrently...")

    start_time = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=35) as executor:
        futures = [executor.submit(test_connection, i) for i in range(num_connections)]
        results = [f.result() for f in futures]

    duration = time.time() - start_time

    # Analyze results
    successes = [r for r in results if "SUCCESS" in r[2]]
    failures = [r for r in results if "FAILED" in r[2]]
    avg_latency = sum(r[1] for r in successes) / len(successes) if successes else 0

    print(f"\nResults:")
    print(f"  Total connections: {num_connections}")
    print(f"  Successful: {len(successes)}")
    print(f"  Failed: {len(failures)}")
    print(f"  Total time: {duration:.2f}s")
    print(f"  Avg latency: {avg_latency*1000:.1f}ms")

    if failures:
        print(f"\n⚠️  Failures detected:")
        for conn_id, dur, msg in failures[:5]:  # Show first 5
            print(f"  Connection {conn_id}: {msg}")

    # Success criteria
    if len(successes) >= num_connections:
        print(f"\n✅ PASS: All connections succeeded")
        return 0
    elif len(successes) >= num_connections * 0.9:
        print(f"\n⚠️  PARTIAL: 90%+ succeeded, check for timeouts")
        return 1
    else:
        print(f"\n❌ FAIL: <90% success rate")
        return 2


if __name__ == "__main__":
    sys.exit(main())
