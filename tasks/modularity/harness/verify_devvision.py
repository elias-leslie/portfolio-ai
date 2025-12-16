#!/usr/bin/env python3
"""
DeVision Extraction Verification Harness
=========================================

Runs Claude iteratively to verify the DevVision extraction plan.
Uses OAuth authentication via Claude CLI (MAX account).

Usage:
    python verify_devvision.py
    python verify_devvision.py --max-iterations 3
    python verify_devvision.py --model claude-sonnet-4-5-20250929
"""

import argparse
import asyncio
from pathlib import Path

from agent import run_verification_agent


DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
PROJECT_DIR = Path(__file__).parent


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="DeVision Extraction Verification Harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run verification (unlimited iterations until complete)
    python verify_devvision.py

    # Limit iterations for testing
    python verify_devvision.py --max-iterations 3

    # Use a specific model
    python verify_devvision.py --model claude-opus-4-5-20251101

Authentication:
    Uses OAuth via Claude CLI (~/.claude/.credentials.json)
    No ANTHROPIC_API_KEY needed - uses MAX account subscription
        """,
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum number of agent iterations (default: unlimited)",
    )

    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Claude model to use (default: {DEFAULT_MODEL})",
    )

    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Verify Claude CLI is available (OAuth credentials)
    import shutil
    if not shutil.which("claude"):
        print("Error: Claude CLI not found")
        print("\nInstall Claude CLI:")
        print("  npm install -g @anthropic-ai/claude-code")
        print("\nThen authenticate:")
        print("  claude auth login")
        return

    # Check credentials exist
    creds_file = Path.home() / ".claude" / ".credentials.json"
    if not creds_file.exists():
        print("Error: Claude credentials not found")
        print(f"  Expected: {creds_file}")
        print("\nRun: claude auth login")
        return

    print("\n" + "=" * 70)
    print("  DEVISION EXTRACTION VERIFICATION HARNESS")
    print("=" * 70)
    print(f"\nProject directory: {PROJECT_DIR}")
    print(f"Model: {args.model}")
    print("Auth: OAuth via Claude CLI (MAX account)")
    if args.max_iterations:
        print(f"Max iterations: {args.max_iterations}")
    else:
        print("Max iterations: Unlimited")
    print()

    # Run the agent
    try:
        asyncio.run(
            run_verification_agent(
                project_dir=PROJECT_DIR,
                model=args.model,
                max_iterations=args.max_iterations,
            )
        )
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        print("To resume, run the same command again")
    except Exception as e:
        print(f"\nFatal error: {e}")
        raise


if __name__ == "__main__":
    main()
