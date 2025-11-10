#!/bin/bash
#
# Portfolio AI - Comprehensive Permission Fix Script
# This script fixes all permission issues for kasadis (dev) and portfolio-ai (service) users
#
# Safe to run multiple times (idempotent)
#

set -e  # Exit on error

echo "=================================================="
echo "Portfolio AI - Permission Fix Script"
echo "=================================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running with sudo for parts that need it
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}ERROR: This script must be run with sudo${NC}"
    echo "Usage: sudo bash $0"
    exit 1
fi

echo "Step 1: Fixing config directory permissions..."
echo "  Current: $(ls -ld /home/kasadis/portfolio-ai/backend/config | awk '{print $1, $3, $4}')"
chmod 750 /home/kasadis/portfolio-ai/backend/config
echo "  Fixed:   $(ls -ld /home/kasadis/portfolio-ai/backend/config | awk '{print $1, $3, $4}')"
echo -e "${GREEN}✓ Config directory now readable by portfolio-ai group${NC}"
echo ""

echo "Step 2: Creating and fixing sources directory..."
if [ ! -d "/home/kasadis/portfolio-ai/backend/config/sources" ]; then
    mkdir -p /home/kasadis/portfolio-ai/backend/config/sources
    echo "  Created sources directory"
else
    echo "  Sources directory already exists"
fi
chown -R kasadis:portfolio-ai /home/kasadis/portfolio-ai/backend/config
chmod 750 /home/kasadis/portfolio-ai/backend/config/sources
echo "  Ownership: $(ls -ld /home/kasadis/portfolio-ai/backend/config/sources | awk '{print $3, $4}')"
echo -e "${GREEN}✓ Sources directory ready for API quotas${NC}"
echo ""

echo "Step 3: Fixing log file ownership..."
LOG_COUNT=0
for logfile in /var/log/portfolio-ai/*.log; do
    if [ -f "$logfile" ]; then
        CURRENT_OWNER=$(stat -c '%U:%G' "$logfile")
        if [ "$CURRENT_OWNER" != "portfolio-ai:portfolio-ai" ]; then
            chown portfolio-ai:portfolio-ai "$logfile"
            echo "  Fixed: $(basename $logfile) ($CURRENT_OWNER → portfolio-ai:portfolio-ai)"
            ((LOG_COUNT++))
        fi
    fi
done
if [ $LOG_COUNT -eq 0 ]; then
    echo "  All log files already have correct ownership"
fi
echo -e "${GREEN}✓ Log files now owned by portfolio-ai${NC}"
echo ""

echo "Step 4: Adding SupplementaryGroups to systemd services..."
SERVICES_UPDATED=0
for service_name in portfolio-backend portfolio-celery portfolio-beat portfolio-frontend; do
    SERVICE_FILE="/etc/systemd/system/${service_name}.service"

    if [ ! -f "$SERVICE_FILE" ]; then
        echo -e "  ${YELLOW}Warning: $service_name.service not found${NC}"
        continue
    fi

    # Check if SupplementaryGroups already configured
    if grep -q "^SupplementaryGroups=" "$SERVICE_FILE"; then
        CURRENT_GROUPS=$(grep "^SupplementaryGroups=" "$SERVICE_FILE" | cut -d= -f2)
        echo "  $service_name: Already has SupplementaryGroups=$CURRENT_GROUPS"
    else
        # Add SupplementaryGroups after Group= line
        sed -i '/^Group=portfolio-ai/a SupplementaryGroups=kasadis adm' "$SERVICE_FILE"
        echo "  $service_name: Added SupplementaryGroups=kasadis adm"
        ((SERVICES_UPDATED++))
    fi
done

if [ $SERVICES_UPDATED -gt 0 ]; then
    echo ""
    echo "  Reloading systemd daemon..."
    systemctl daemon-reload
    echo -e "${GREEN}✓ Updated $SERVICES_UPDATED service(s)${NC}"
else
    echo -e "${GREEN}✓ All services already configured${NC}"
fi
echo ""

echo "Step 5: Verification..."
echo ""
echo "  Config directory permissions:"
ls -ld /home/kasadis/portfolio-ai/backend/config | awk '{print "    " $1, $3, $4}'

echo ""
echo "  Sources directory:"
if [ -d "/home/kasadis/portfolio-ai/backend/config/sources" ]; then
    ls -ld /home/kasadis/portfolio-ai/backend/config/sources | awk '{print "    " $1, $3, $4}'
else
    echo -e "    ${RED}✗ Not found${NC}"
fi

echo ""
echo "  Sample log file ownership:"
ls -l /var/log/portfolio-ai/backend.log 2>/dev/null | awk '{print "    " $3, $4}' || echo "    (no logs yet)"

echo ""
echo "  Service configurations:"
for svc in backend celery beat frontend; do
    SUPP=$(systemctl show portfolio-$svc -p SupplementaryGroups --value 2>/dev/null || echo "N/A")
    if [ "$SUPP" = "kasadis adm" ]; then
        echo -e "    portfolio-$svc: ${GREEN}✓ $SUPP${NC}"
    elif [ -z "$SUPP" ]; then
        echo -e "    portfolio-$svc: ${YELLOW}⚠ Not set (need to restart)${NC}"
    else
        echo "    portfolio-$svc: $SUPP"
    fi
done

echo ""
echo "=================================================="
echo "Permission fixes complete!"
echo "=================================================="
echo ""
echo -e "${YELLOW}IMPORTANT: Restart services to apply changes:${NC}"
echo "  bash ~/portfolio-ai/scripts/restart.sh"
echo ""
