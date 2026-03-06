"""Manual test script for LLM execution verification via Agent Hub.

This script tests real LLM execution through Agent Hub API.
Requires Agent Hub service running at localhost:8003.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.agents.llm_client import AgentHubAPIClient, DualProviderClient

pytestmark = [pytest.mark.manual, pytest.mark.slow]


def test_agent_hub_availability() -> dict[str, str]:
    """Test Agent Hub availability.

    Returns:
        Dictionary with status and details
    """
    print("\n=== TESTING AGENT HUB ===")
    try:
        client = AgentHubAPIClient(model="claude-sonnet-4-5-20250514")
        is_available = client.is_available()
        print(f"  Model: {client.get_model_name()}")
        print(f"  Available: {is_available}")

        if is_available:
            # Try a simple call
            print("  Attempting real API call...")
            try:
                response = client.generate(prompt="Say 'test' only", max_tokens=10)
                print(f"  Response: {response.content[:100]}")
                return {"status": "WORKS", "provider": response.provider, "model": response.model}
            except RuntimeError as e:
                error_msg = str(e)
                return {"status": "ERROR", "provider": "agent_hub", "error": error_msg}
        else:
            return {
                "status": "UNAVAILABLE",
                "provider": "agent_hub",
                "error": "Service not reachable",
            }

    except Exception as e:
        return {"status": "ERROR", "provider": "agent_hub", "error": str(e)}


def test_agent_hub_gemini() -> dict[str, str]:
    """Test Agent Hub with Gemini model.

    Returns:
        Dictionary with status and details
    """
    print("\n=== TESTING AGENT HUB (GEMINI) ===")
    try:
        client = AgentHubAPIClient(model="gemini-3-flash-preview")
        is_available = client.is_available()
        print(f"  Model: {client.get_model_name()}")
        print(f"  Available: {is_available}")

        if is_available:
            print("  Attempting real API call...")
            try:
                response = client.generate(prompt="Say 'hello' only", max_tokens=10)
                print(f"  Response: {response.content[:100]}")
                return {"status": "WORKS", "provider": response.provider, "model": response.model}
            except RuntimeError as e:
                return {"status": "ERROR", "provider": "gemini", "error": str(e)}
        else:
            return {"status": "UNAVAILABLE", "provider": "gemini", "error": "Service not reachable"}

    except Exception as e:
        return {"status": "ERROR", "provider": "gemini", "error": str(e)}


def test_dual_provider_client() -> dict[str, object]:
    """Test DualProviderClient (Agent Hub wrapper).

    Returns:
        Dictionary with test results
    """
    print("\n=== TESTING DUAL PROVIDER CLIENT ===")
    try:
        print("Creating DualProviderClient(primary='gemini')...")
        client = DualProviderClient(primary="gemini")

        print(f"  Model: {client.get_model_name()}")
        print(f"  Client is available: {client.is_available()}")

        if not client.is_available():
            return {"status": "NO_PROVIDERS", "error": "Agent Hub not available"}

        # Try to generate
        print("  Attempting to generate...")
        try:
            response = client.generate(
                prompt="What is 2+2?",
                system="You are a helpful assistant.",
                max_tokens=50,
            )
            return {
                "status": "SUCCESS",
                "provider": response.provider,
                "model": response.model,
                "content": response.content[:100],
                "tokens": response.usage.get("total_tokens", 0),
            }
        except RuntimeError as e:
            return {"status": "GENERATION_FAILED", "error": str(e)}

    except RuntimeError as e:
        return {"status": "INITIALIZATION_FAILED", "error": str(e)}


def print_summary(results: list[dict[str, object]]) -> None:
    """Print test summary and recommendations.

    Args:
        results: List of test results
    """
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for result in results:
        print(f"\n{result['name']}:")
        print(f"  Status: {result['status']}")
        if "error" in result:
            print(f"  Error: {result['error']}")
        if "model" in result:
            print(f"  Model: {result['model']}")
        if "provider" in result:
            print(f"  Provider: {result['provider']}")

    # Check overall status
    any_working = any(r["status"] == "WORKS" or r["status"] == "SUCCESS" for r in results)

    print("\n" + "-" * 60)
    if any_working:
        print("AGENT HUB WORKING")
        print("  LLM requests can be executed via Agent Hub API")
    else:
        print("AGENT HUB NOT AVAILABLE")
        print("  Ensure Agent Hub service is running at localhost:8003")
        print("  Start with: bash ~/agent-hub/scripts/restart.sh")


if __name__ == "__main__":
    print("LLM Execution Verification Test (via Agent Hub)")
    print("=" * 60)

    results: list[dict[str, object]] = []

    # Test Agent Hub with Claude
    claude_result = test_agent_hub_availability()
    results.append(
        {"name": "Agent Hub (Claude)", "status": claude_result["status"], **claude_result}
    )

    # Test Agent Hub with Gemini
    gemini_result = test_agent_hub_gemini()
    results.append(
        {"name": "Agent Hub (Gemini)", "status": gemini_result["status"], **gemini_result}
    )

    # Test dual provider
    dual_result = test_dual_provider_client()
    results.append({"name": "Dual Provider Client", "status": dual_result["status"], **dual_result})

    # Print summary
    print_summary(results)
