"""MCP server — exposes portfolio-ai's 3-tier signal stack to Claude Code / Codex CLI.

Stdio transport. Five read-only tools that wrap existing repositories and
services; no LLM inference is triggered from this layer. Auth is OS-level
user trust (per the locked Phase 5 decision in the plan).
"""
