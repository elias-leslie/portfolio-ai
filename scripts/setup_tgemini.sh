#!/bin/bash
#
# This script adds the tgemini function and alias to your .bashrc file,
# mirroring the setup of the tclaude command.
#
# It is idempotent and can be run multiple times safely.
#

set -euo pipefail

BASHRC_FILE="$HOME/.bashrc"
FUNCTION_NAME="tgemini"
ALIAS_NAME="tgemini"

echo "🔧 Checking and updating your ~/.bashrc for the 'tgemini' command..."
echo "------------------------------------------------------------"

# Check if the function is already defined in .bashrc
if grep -q "tgemini()" "$BASHRC_FILE"; then
    echo "✔️ 'tgemini' function already exists in $BASHRC_FILE."
else
    echo "➕ Adding 'tgemini' function to $BASHRC_FILE..."
    # Using a heredoc to append the function definition
    cat << 'EOF' >> "$BASHRC_FILE"

# Function to start or attach to a Gemini tmux session
tgemini() {
    local project_dir="${1:-$HOME/portfolio-ai}"
    if [ ! -d "$project_dir" ]; then
        echo "⚠️  Directory '$project_dir' not found — starting in ~"
        project_dir="$HOME"
    fi
    if tmux has-session -t gemini 2>/dev/null; then
        echo "🔄 Reattaching to existing Gemini session..."
        tmux attach -t gemini
    else
        echo "🚀 Starting new Gemini session in $project_dir"
        tmux new -s gemini "cd '$project_dir' && gemini"
    fi
}
EOF
    echo "   ...function added."
fi

echo ""

# Check if the alias is already defined
if grep -q "alias $ALIAS_NAME='tgemini'" "$BASHRC_FILE"; then
    echo "✔️ 'tgemini' alias already exists in $BASHRC_FILE."
else
    echo "➕ Adding 'tgemini' alias to $BASHRC_FILE..."
    echo "alias tgemini='tgemini'" >> "$BASHRC_FILE"
    echo "   ...alias added."
fi

echo "------------------------------------------------------------"
echo "✅ Setup complete."
echo ""
echo "To apply the changes, please run the following command:"
echo "source ~/.bashrc"
echo ""
echo "You can then use the 'tgemini' command."
