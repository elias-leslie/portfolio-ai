"""
Claude SDK Client Configuration
===============================

Functions for creating and configuring the Claude Agent SDK client.
Uses OAuth authentication via Claude CLI (MAX account).
"""

import json
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient


# Built-in tools for verification
BUILTIN_TOOLS = [
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "Bash",
]


def create_client(project_dir: Path, model: str) -> ClaudeSDKClient:
    """
    Create a Claude Agent SDK client using OAuth authentication.

    Args:
        project_dir: Directory for the project (working directory)
        model: Claude model to use

    Returns:
        Configured ClaudeSDKClient

    Authentication:
        Uses OAuth via Claude CLI (~/.claude/.credentials.json)
        No API key needed - leverages MAX account subscription
    """
    # Security settings - restrict to project and portfolio-ai directories
    portfolio_ai_dir = Path.home() / "portfolio-ai"

    security_settings = {
        "permissions": {
            "defaultMode": "acceptEdits",
            "allow": [
                # Allow file operations in project directory
                "Read(./**)",
                "Write(./**)",
                "Edit(./**)",
                "Glob(./**)",
                "Grep(./**)",
                # Allow reading portfolio-ai for verification
                f"Read({portfolio_ai_dir}/**)",
                f"Glob({portfolio_ai_dir}/**)",
                f"Grep({portfolio_ai_dir}/**)",
                # Bash for exploration commands
                "Bash(*)",
            ],
        },
    }

    # Ensure project directory exists
    project_dir.mkdir(parents=True, exist_ok=True)

    # Write settings to file
    settings_file = project_dir / ".claude_settings.json"
    with open(settings_file, "w") as f:
        json.dump(security_settings, f, indent=2)

    print(f"Created settings at {settings_file}")
    print(f"   - Filesystem access: {project_dir}, {portfolio_ai_dir}")
    print("   - Auth: OAuth via Claude CLI")
    print()

    return ClaudeSDKClient(
        options=ClaudeAgentOptions(
            model=model,
            system_prompt="""You are a meticulous verification agent for the DeVision extraction project.
Your job is to verify that the extraction plan correctly categorizes all components.

For each verification item:
1. Check if the component exists at the specified location
2. Analyze its code to determine if it's dev tooling or domain-specific
3. Verify the categorization (MOVE vs STAY) is correct
4. Document any findings or corrections needed

Be thorough. Check actual file contents, not just paths.""",
            allowed_tools=BUILTIN_TOOLS,
            max_turns=500,
            cwd=str(project_dir.resolve()),
            settings=str(settings_file.resolve()),
        )
    )
