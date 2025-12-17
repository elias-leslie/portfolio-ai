# SummitFlow Verification Harness

Autonomous agent harness for verifying the SummitFlow extraction plan.
Based on Anthropic's autonomous-coding pattern.

## Overview

This harness runs Claude iteratively to verify that each component in the
SummitFlow extraction plan is correctly categorized (MOVE vs STAY).

## Prerequisites

1. **Claude CLI** with OAuth authentication:
   ```bash
   npm install -g @anthropic-ai/claude-code
   claude auth login
   ```

2. **Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

```bash
# Run verification (unlimited iterations)
python verify_summitflow.py

# Limit iterations for testing
python verify_summitflow.py --max-iterations 3

# Use a specific model
python verify_summitflow.py --model claude-opus-4-5-20251101
```

## How It Works

1. **verification_list.json** - Pre-created list of 67 components to verify
2. **Verification Agent** - Iteratively verifies each component:
   - Checks if file exists at stated location
   - Analyzes code to determine if categorization is correct
   - Updates item status with evidence
3. **Progress Tracking** - Each session updates progress and commits to git

## Files

```
harness/
├── verify_summitflow.py     # Main entry point
├── agent.py                # Session logic
├── client.py               # Claude SDK client setup
├── progress.py             # Progress tracking
├── prompts.py              # Prompt loading
├── prompts/
│   ├── initializer_prompt.md
│   └── verification_prompt.md
├── verification_list.json  # Items to verify (source of truth)
├── verification-progress.txt # Session notes
└── requirements.txt
```

## Authentication

Uses OAuth via Claude CLI - no API key needed.
Credentials stored at: `~/.claude/.credentials.json`

This leverages your MAX account subscription.

## Resuming

To resume after interruption:
```bash
python verify_summitflow.py
```

The harness reads verification_list.json and continues from where it left off.
