"""Manual test script for LLM execution verification.

This script tests real LLM execution with both Gemini and Claude CLIs.
It documents auth/quota issues and provides recommendations for fixes.
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.agents.llm_client import ClaudeCLIClient, DualProviderClient, GeminiCLIClient


def test_gemini_cli_availability() -> dict[str, str]:
    """Test Gemini CLI availability and current quota status.

    Returns:
        Dictionary with status and details
    """
    print("\n=== TESTING GEMINI CLI ===")
    try:
        client = GeminiCLIClient()
        is_available = client.is_available()
        print(f"✓ Gemini CLI found at: {client.cli_path}")
        print(f"  Model: {client.get_model_name()}")
        print(f"  Available: {is_available}")

        if is_available:
            # Try a simple call
            print("  Attempting real API call...")
            try:
                response = client.generate(prompt="Say 'test' only", max_tokens=10)
                print(f"✓ Response: {response.content[:100]}")
                return {"status": "WORKS", "provider": "gemini", "model": client.model}
            except RuntimeError as e:
                error_msg = str(e)
                if "429" in error_msg or "exhausted" in error_msg.lower():
                    return {
                        "status": "QUOTA_EXCEEDED",
                        "provider": "gemini",
                        "error": "Free quota exhausted",
                    }
                if "RATE_LIMIT" in error_msg:
                    return {
                        "status": "RATE_LIMITED",
                        "provider": "gemini",
                        "error": error_msg,
                    }
                return {"status": "ERROR", "provider": "gemini", "error": error_msg}
        else:
            return {"status": "UNAVAILABLE", "provider": "gemini", "error": "CLI not functional"}

    except RuntimeError as e:
        return {"status": "NOT_INSTALLED", "provider": "gemini", "error": str(e)}


def test_claude_cli_availability() -> dict[str, str]:
    """Test Claude CLI availability and authentication status.

    Returns:
        Dictionary with status and details
    """
    print("\n=== TESTING CLAUDE CLI ===")
    try:
        client = ClaudeCLIClient()
        is_available = client.is_available()
        print(f"✓ Claude CLI found at: {client.cli_path}")
        print(f"  Model: {client.get_model_name()}")
        print(f"  Available: {is_available}")

        if is_available:
            # Try a simple call
            print("  Attempting real API call...")
            try:
                response = client.generate(prompt="Say 'test' only", max_tokens=10)
                print(f"✓ Response: {response.content[:100]}")
                return {"status": "WORKS", "provider": "claude", "model": client.model}
            except RuntimeError as e:
                error_msg = str(e)
                if "Invalid API key" in error_msg or "api key" in error_msg.lower():
                    return {
                        "status": "AUTH_FAILED",
                        "provider": "claude",
                        "error": "Invalid API key configuration",
                    }
                if "429" in error_msg or "rate limit" in error_msg.lower():
                    return {
                        "status": "RATE_LIMITED",
                        "provider": "claude",
                        "error": "Rate limited by Anthropic API",
                    }
                return {"status": "ERROR", "provider": "claude", "error": error_msg}
        else:
            return {"status": "UNAVAILABLE", "provider": "claude", "error": "CLI not functional"}

    except RuntimeError as e:
        return {"status": "NOT_INSTALLED", "provider": "claude", "error": str(e)}


def test_dual_provider_client() -> dict[str, object]:
    """Test DualProviderClient with automatic failover.

    Returns:
        Dictionary with test results
    """
    print("\n=== TESTING DUAL PROVIDER CLIENT ===")
    try:
        # Try with Gemini as primary, Claude as fallback
        print("Creating DualProviderClient(primary='gemini')...")
        client = DualProviderClient(primary="gemini")

        print(f"Available providers: {list(client.providers.keys())}")
        print(f"Client is available: {client.is_available()}")

        if not client.is_available():
            return {"status": "NO_PROVIDERS", "error": "No providers available"}

        # Try to generate
        print("Attempting to generate with failover...")
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
        if "details" in result:
            for key, value in result["details"].items():
                print(f"  {key}: {value}")

    # Determine overall status
    gemini_result = next((r for r in results if "gemini" in r.get("name", "").lower()), None)
    claude_result = next((r for r in results if "claude" in r.get("name", "").lower()), None)
    dual_result = next((r for r in results if "dual" in r.get("name", "").lower()), None)

    print("\n" + "-" * 60)
    print("RECOMMENDATIONS:")
    print("-" * 60)

    if gemini_result and gemini_result["status"] == "QUOTA_EXCEEDED":
        print("\n⚠️  GEMINI QUOTA ISSUE:")
        print("  - Free tier quota exhausted for gemini-2.5-pro")
        print("  - Solution: Use Claude CLI instead (paid tier available)")
        print("  - Or: Wait for quota reset (typically monthly)")

    if claude_result and claude_result["status"] == "AUTH_FAILED":
        print("\n⚠️  CLAUDE AUTH ISSUE:")
        print("  - Claude CLI configured with invalid API key")
        print("  - Current: ANTHROPIC_API_KEY='${ANTHROPIC_API_KEY}' (literal, not expanded)")
        print("  - Solution:")
        print("    1. Configure actual API key: export ANTHROPIC_API_KEY=sk-...'")
        print("    2. Or use OAuth: 'claude --auth' to set up with browser")
        print("    3. Claude Code subscription provides $5/month API credit")

    if dual_result and dual_result["status"] == "SUCCESS":
        print("\n✓ DUAL PROVIDER CLIENT WORKING:")
        print(f"  - Using {dual_result['provider']} (fallback successful)")
        print("  - Workflows can execute with automatic failover")

    elif not (
        (gemini_result and gemini_result["status"] == "WORKS")
        or (claude_result and claude_result["status"] == "WORKS")
    ):
        print("\n❌ CRITICAL: NO WORKING LLM PROVIDERS")
        print("  - Gemini: " + (gemini_result["status"] if gemini_result else "N/A"))
        print("  - Claude: " + (claude_result["status"] if claude_result else "N/A"))
        print("\nAction Required:")
        print("  1. Fix Claude API key configuration")
        print("  2. Or wait for Gemini quota reset")
        print("  3. Without LLM access, workflows cannot execute")


if __name__ == "__main__":
    print("LLM Execution Verification Test")
    print("=" * 60)

    results = []

    # Test individual providers
    gemini_result = test_gemini_cli_availability()
    results.append({"name": "Gemini CLI", "status": gemini_result["status"], **gemini_result})

    claude_result = test_claude_cli_availability()
    results.append({"name": "Claude CLI", "status": claude_result["status"], **claude_result})

    # Test dual provider
    dual_result = test_dual_provider_client()
    results.append({"name": "Dual Provider Client", "status": dual_result["status"], **dual_result})

    # Print summary and recommendations
    print_summary(results)
