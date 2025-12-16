"""
Prompt Loading Utilities
========================

Functions for loading prompt templates.
"""

from pathlib import Path


PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(name: str) -> str:
    """Load a prompt template from the prompts directory."""
    prompt_path = PROMPTS_DIR / f"{name}.md"
    return prompt_path.read_text()


def get_initializer_prompt(project_dir: Path) -> str:
    """
    Load the initializer prompt.

    Reads the NEXT-SESSION-PROMPT.md and generates verification_list.json.
    """
    prompt = load_prompt("initializer_prompt")

    # Read the planning document to include in prompt
    planning_doc = project_dir.parent / "NEXT-SESSION-PROMPT.md"
    if planning_doc.exists():
        planning_content = planning_doc.read_text()
        prompt = prompt.replace("{{PLANNING_DOC}}", planning_content)
    else:
        prompt = prompt.replace("{{PLANNING_DOC}}", "[PLANNING DOC NOT FOUND]")

    return prompt


def get_verification_prompt(project_dir: Path) -> str:
    """
    Load the verification prompt for continuing sessions.
    """
    prompt = load_prompt("verification_prompt")

    # Include path to portfolio-ai for context
    portfolio_ai = Path.home() / "portfolio-ai"
    prompt = prompt.replace("{{PORTFOLIO_AI_PATH}}", str(portfolio_ai))

    return prompt
