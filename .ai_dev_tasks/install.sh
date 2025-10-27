#!/bin/bash
# AI Dev Tasks - Command Suite Installer
# Usage: ./install.sh [global|local]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-global}"

echo "🚀 AI Dev Tasks - Command Suite Installer"
echo ""

if [ "$MODE" = "global" ]; then
    TARGET_DIR="$HOME/.config/claude/commands"
    echo "📦 Installing globally to: $TARGET_DIR"
elif [ "$MODE" = "local" ]; then
    TARGET_DIR="$(pwd)/.claude/commands"
    echo "📦 Installing locally to: $TARGET_DIR"
else
    echo "❌ Invalid mode: $MODE"
    echo "Usage: ./install.sh [global|local]"
    exit 1
fi

# Create target directory
mkdir -p "$TARGET_DIR"

# Copy command files
echo ""
echo "Copying command files..."
cp -v "$SCRIPT_DIR/plan_it.md" "$TARGET_DIR/"
cp -v "$SCRIPT_DIR/task_it.md" "$TARGET_DIR/"
cp -v "$SCRIPT_DIR/do_it.md" "$TARGET_DIR/"
cp -v "$SCRIPT_DIR/doc_it.md" "$TARGET_DIR/"
cp -v "$SCRIPT_DIR/next_it.md" "$TARGET_DIR/"

echo ""
echo "✅ Installation complete!"
echo ""
echo "Commands installed:"
echo "  - /plan_it (78 lines)"
echo "  - /task_it (82 lines)"
echo "  - /do_it (91 lines)"
echo "  - /doc_it (199 lines)"
echo "  - /next_it (225 lines)"
echo ""
echo "📝 Next steps:"
echo "  1. Restart Claude Code: /exit"
echo "  2. Start with: /next_it"
echo ""
echo "📚 Documentation: $SCRIPT_DIR/README.md"
