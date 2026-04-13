"""Model constants - single source of truth.

Update these when new model versions are released.
All code should import from here, not hardcode model strings.
"""

# Claude 4.6 models (Anthropic)
CLAUDE_SONNET = "claude-sonnet-4-6"
CLAUDE_OPUS = "claude-opus-4-6"
CLAUDE_HAIKU = "claude-haiku-4-5"

# Gemini 3 models (Google)
GEMINI_FLASH = "gemini-3-flash-preview"
GEMINI_PRO = "gemini-3.1-pro-preview"

# OpenAI models via Agent Hub / Codex
OPENAI_GPT_5_4 = "codex/gpt-5.4"

# Default models for each use case
DEFAULT_CLAUDE_MODEL = CLAUDE_SONNET
DEFAULT_GEMINI_MODEL = GEMINI_FLASH
DEFAULT_OPENAI_MODEL = OPENAI_GPT_5_4
