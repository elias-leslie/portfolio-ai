#!/bin/bash
# Clean up any zombie Next.js processes before starting the frontend service
# This is called by systemd as ExecStartPre

# Kill any Node.js processes running Next.js dev server from the frontend directory
for pid in $(pgrep -f "portfolio-ai/frontend.*next dev"); do
    # Simple kill without checking PID hierarchy
    kill -9 "$pid" 2>/dev/null || true
done

# Also check for npm processes in the frontend directory
for pid in $(pgrep -f "portfolio-ai/frontend.*npm run dev"); do
    kill -9 "$pid" 2>/dev/null || true
done

# Remove lock file
rm -f "$HOME/portfolio-ai/frontend/.next/dev/lock"

exit 0
