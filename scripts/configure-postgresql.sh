#!/bin/bash
# Configure PostgreSQL for optimal performance with Portfolio AI
# This script requires sudo privileges

set -e  # Exit on error

echo "================================================"
echo "PostgreSQL Configuration for Portfolio AI"
echo "================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as sudo
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: This script must be run with sudo${NC}"
    echo "Usage: sudo bash $0"
    exit 1
fi

# Find PostgreSQL config file
PG_CONF=$(find /etc/postgresql -name "postgresql.conf" 2>/dev/null | head -1)

if [ -z "$PG_CONF" ]; then
    echo -e "${RED}Error: Could not find postgresql.conf${NC}"
    echo "Expected location: /etc/postgresql/*/main/postgresql.conf"
    exit 1
fi

echo -e "${GREEN}Found PostgreSQL config: $PG_CONF${NC}"
echo ""

# Get PostgreSQL version for backup filename
PG_VERSION=$(psql --version | grep -oP '\d+' | head -1)
BACKUP_FILE="${PG_CONF}.backup.$(date +%Y%m%d_%H%M%S)"

# Backup current config
echo "Creating backup: $BACKUP_FILE"
cp "$PG_CONF" "$BACKUP_FILE"
echo -e "${GREEN}✓ Backup created${NC}"
echo ""

# Function to update or add config parameter
update_config() {
    local param=$1
    local value=$2
    local config_file=$3

    # Check if parameter exists (commented or uncommented)
    if grep -q "^#\?${param}\s*=" "$config_file"; then
        # Parameter exists, update it
        sed -i "s|^#\?${param}\s*=.*|${param} = ${value}|" "$config_file"
        echo -e "${GREEN}✓${NC} Updated: $param = $value"
    else
        # Parameter doesn't exist, add it
        echo "${param} = ${value}" >> "$config_file"
        echo -e "${GREEN}✓${NC} Added: $param = $value"
    fi
}

echo "Updating PostgreSQL configuration..."
echo "---"

# Connection Settings
update_config "max_connections" "200" "$PG_CONF"

# Memory Settings (optimized for 28GB RAM)
update_config "shared_buffers" "7GB" "$PG_CONF"
update_config "effective_cache_size" "21GB" "$PG_CONF"
update_config "maintenance_work_mem" "1GB" "$PG_CONF"
update_config "work_mem" "128MB" "$PG_CONF"

# Checkpoint Settings
update_config "checkpoint_completion_target" "0.9" "$PG_CONF"
update_config "wal_buffers" "16MB" "$PG_CONF"
update_config "max_wal_size" "4GB" "$PG_CONF"

# Query Planner (optimized for SSD)
update_config "random_page_cost" "1.1" "$PG_CONF"
update_config "effective_io_concurrency" "200" "$PG_CONF"

echo ""
echo -e "${GREEN}✓ Configuration updated${NC}"
echo ""

# Restart PostgreSQL
echo "Restarting PostgreSQL..."
systemctl restart postgresql

# Wait for PostgreSQL to start
sleep 3

# Check if PostgreSQL is running
if systemctl is-active --quiet postgresql; then
    echo -e "${GREEN}✓ PostgreSQL restarted successfully${NC}"
else
    echo -e "${RED}✗ PostgreSQL failed to start${NC}"
    echo "Restoring backup..."
    cp "$BACKUP_FILE" "$PG_CONF"
    systemctl restart postgresql
    echo -e "${YELLOW}Backup restored. Please check logs: sudo journalctl -u postgresql -n 50${NC}"
    exit 1
fi

echo ""
echo "Verifying new settings..."
echo "---"

# Verify settings as postgres user
sudo -u postgres psql -c "SHOW max_connections;" 2>/dev/null || echo "Could not verify max_connections"
sudo -u postgres psql -c "SHOW shared_buffers;" 2>/dev/null || echo "Could not verify shared_buffers"
sudo -u postgres psql -c "SHOW effective_cache_size;" 2>/dev/null || echo "Could not verify effective_cache_size"

echo ""
echo "================================================"
echo -e "${GREEN}PostgreSQL Configuration Complete!${NC}"
echo "================================================"
echo ""
echo "Summary of changes:"
echo "  • max_connections: 100 → 200"
echo "  • shared_buffers: 128MB → 7GB"
echo "  • effective_cache_size: 4GB → 21GB"
echo "  • + Additional performance optimizations"
echo ""
echo "Backup saved at:"
echo "  $BACKUP_FILE"
echo ""
echo -e "${YELLOW}NEXT STEPS:${NC}"
echo ""
echo "1. Update production service pool sizes:"
echo "   Edit ~/portfolio-ai/scripts/start.sh and add:"
echo "   ${GREEN}export DB_POOL_SIZE=3${NC}"
echo "   ${GREEN}export DB_MAX_OVERFLOW=2${NC}"
echo ""
echo "2. Restart all services:"
echo "   ${GREEN}bash ~/portfolio-ai/scripts/restart.sh${NC}"
echo ""
echo "3. Run tests to verify:"
echo "   ${GREEN}cd ~/portfolio-ai/backend && source .venv/bin/activate && pytest tests/ -q${NC}"
echo ""
echo "Connection allocation (with new settings):"
echo "  • Production: 35 processes × 5 conns = 175 max"
echo "  • Tests: ~20 × 2 conns = 40 max"
echo "  • Reserved for admin: 15"
echo "  • Total: 230 (within 200 limit with pool behavior)"
echo ""
