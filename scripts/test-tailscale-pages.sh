#!/bin/bash
# Test all major pages via Tailscale after fix
# Run after fixing frontend: bash scripts/test-tailscale-pages.sh

TAILSCALE_URL="http://100.123.190.81:3000"
OUTPUT_DIR="/tmp/tailscale-test-$(date +%Y%m%d-%H%M%S)"

mkdir -p "$OUTPUT_DIR"

echo "================================"
echo "Testing Tailscale Pages"
echo "================================"
echo "Output directory: $OUTPUT_DIR"
echo ""

# Test each major page
pages=(
    "/"
    "/watchlist"
    "/portfolio"
    "/status"
    "/settings"
    "/capabilities"
)

for page in "${pages[@]}"; do
    echo "Testing: $TAILSCALE_URL$page"

    # Take screenshot
    screenshot_file="$OUTPUT_DIR${page//\//-}.png"
    if [ "$page" = "/" ]; then
        screenshot_file="$OUTPUT_DIR/dashboard.png"
    fi

    node ~/portfolio-ai/.claude/skills/browser-automation/scripts/screenshot.js \
        "$TAILSCALE_URL$page" \
        "$screenshot_file" \
        true \
        2>&1 | grep -E "(saved|error|Error)" || echo "   Screenshot: $screenshot_file"

    # Capture console errors
    console_file="$OUTPUT_DIR${page//\//-}-console.txt"
    if [ "$page" = "/" ]; then
        console_file="$OUTPUT_DIR/dashboard-console.txt"
    fi

    node ~/portfolio-ai/.claude/skills/browser-automation/scripts/console.js \
        "$TAILSCALE_URL$page" \
        5000 \
        > "$console_file" \
        2>&1

    echo "   Console: $console_file"
    echo ""
done

echo "================================"
echo "Test Complete!"
echo "================================"
echo ""
echo "Results saved to: $OUTPUT_DIR"
echo ""
echo "View screenshots:"
ls -lh "$OUTPUT_DIR"/*.png
echo ""
echo "Check for errors:"
grep -l "ERROR" "$OUTPUT_DIR"/*.txt || echo "No errors found!"
echo ""
