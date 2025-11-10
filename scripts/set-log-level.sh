#!/bin/bash
# Set log level for all Portfolio AI services
# Usage: bash set-log-level.sh <LEVEL>
# Valid levels: DEBUG, INFO, WARN, ERROR, CRITICAL

set -e

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <LEVEL>"
    echo "Valid levels: DEBUG, INFO, WARN, ERROR, CRITICAL"
    exit 1
fi

LEVEL="$1"

# Validate level
case "$LEVEL" in
    DEBUG|INFO|WARN|WARNING|ERROR|CRITICAL)
        ;;
    *)
        echo "Error: Invalid log level '$LEVEL'"
        echo "Valid levels: DEBUG, INFO, WARN, ERROR, CRITICAL"
        exit 1
        ;;
esac

# Normalize WARNING to WARN
if [ "$LEVEL" = "WARNING" ]; then
    LEVEL="WARN"
fi

SERVICES=(
    "portfolio-backend"
    "portfolio-celery"
    "portfolio-beat"
    "portfolio-frontend"
)

echo "Setting log level to: $LEVEL"
echo ""

for service in "${SERVICES[@]}"; do
    OVERRIDE_DIR="/etc/systemd/system/${service}.service.d"
    OVERRIDE_FILE="$OVERRIDE_DIR/journald-logging.conf"

    if [ ! -f "$OVERRIDE_FILE" ]; then
        echo "⚠ Warning: $OVERRIDE_FILE not found, skipping $service"
        continue
    fi

    echo "Updating $service..."

    # Create temporary file with updated config
    sudo tee "$OVERRIDE_FILE" > /dev/null <<EOF
[Service]
# Override file logging with journald
StandardOutput=journal
StandardError=journal

# Set log level identifier for filtering
SyslogIdentifier=${service}

# Log level configuration
Environment="LOG_LEVEL=${LEVEL}"
EOF

    echo "  ✓ Updated $OVERRIDE_FILE"
done

echo ""
echo "Reloading systemd configuration..."
sudo systemctl daemon-reload

echo ""
echo "✅ Log level set to: $LEVEL"
echo ""
echo "Restart services to apply:"
echo "  bash ~/portfolio-ai/scripts/restart.sh"
