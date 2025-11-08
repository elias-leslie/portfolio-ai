#!/bin/bash
# Setup Portfolio AI Service Account
# This creates a dedicated system user to run services (more secure, Claude can control)
# Run as: sudo bash setup-service-account.sh

set -e

SERVICE_USER="portfolio-ai"
SERVICE_GROUP="portfolio-ai"
CODE_OWNER="kasadis"
PROJECT_DIR="/home/kasadis/portfolio-ai"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================="
echo "Portfolio AI - Service Account Setup"
echo "========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}ERROR: This script must be run as root (use sudo)${NC}"
    exit 1
fi

echo "Configuration:"
echo "  Service user:  $SERVICE_USER"
echo "  Service group: $SERVICE_GROUP"
echo "  Code owner:    $CODE_OWNER"
echo "  Project dir:   $PROJECT_DIR"
echo ""

# Backup existing service files
echo "1. Backing up existing service files..."
for service in portfolio-backend portfolio-celery portfolio-beat portfolio-frontend; do
    if [ -f "/etc/systemd/system/${service}.service" ]; then
        cp "/etc/systemd/system/${service}.service" "/etc/systemd/system/${service}.service.backup.$(date +%Y%m%d-%H%M%S)"
        echo "   ✓ Backed up ${service}.service"
    fi
done
echo ""

# Create service account
echo "2. Creating service account..."
if id "$SERVICE_USER" &>/dev/null; then
    echo -e "   ${YELLOW}User $SERVICE_USER already exists, skipping creation${NC}"
else
    useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
    echo "   ✓ Created system user: $SERVICE_USER"
fi
echo ""

# Set up group permissions for file access
echo "3. Setting up group permissions..."

# Add service user to kasadis group so it can read code
usermod -a -G "$CODE_OWNER" "$SERVICE_USER"
echo "   ✓ Added $SERVICE_USER to $CODE_OWNER group"

# Make project directories group-readable
chmod g+rx "$PROJECT_DIR"
echo "   ✓ Set project directory permissions"

# Backend: needs write access for Celery Beat schedule files
chmod g+rwx "$BACKEND_DIR"
chmod -R g+rX "$BACKEND_DIR"/app 2>/dev/null || true  # Recursive for all app subdirectories
chmod -R g+rX "$BACKEND_DIR"/.venv 2>/dev/null || true
echo "   ✓ Set backend directory permissions (writable for Celery Beat)"

# Frontend: needs write access for .next build cache
chmod g+rwx "$FRONTEND_DIR"
chmod -R g+rX "$FRONTEND_DIR"/node_modules 2>/dev/null || true
chmod -R g+rX "$FRONTEND_DIR"/app 2>/dev/null || true
chmod -R g+rX "$FRONTEND_DIR"/components 2>/dev/null || true
chmod -R g+rwx "$FRONTEND_DIR"/.next 2>/dev/null || true
echo "   ✓ Set frontend directory permissions (writable for Next.js builds)"

# Create log directory owned by service user
mkdir -p /var/log/portfolio-ai
chown "$SERVICE_USER:$SERVICE_GROUP" /var/log/portfolio-ai
chmod 755 /var/log/portfolio-ai
echo "   ✓ Created log directory: /var/log/portfolio-ai"

# Create numba cache directory for pandas_ta/numba
mkdir -p /var/cache/portfolio-ai/numba
chown "$SERVICE_USER:$SERVICE_GROUP" /var/cache/portfolio-ai/numba
chmod 755 /var/cache/portfolio-ai/numba
echo "   ✓ Created numba cache directory: /var/cache/portfolio-ai/numba"

# Create HuggingFace transformers cache directory
mkdir -p /var/cache/portfolio-ai/huggingface
chown "$SERVICE_USER:$SERVICE_GROUP" /var/cache/portfolio-ai/huggingface
chmod 755 /var/cache/portfolio-ai/huggingface
echo "   ✓ Created HuggingFace cache directory: /var/cache/portfolio-ai/huggingface"

# Fix existing log file permissions (group needs write access)
if [ -f "$BACKEND_DIR/logs/portfolio-ai.log" ]; then
    chmod g+w "$BACKEND_DIR/logs/portfolio-ai.log"
    echo "   ✓ Fixed existing log file permissions"
fi

# Note: Runtime directory is now created automatically by systemd via RuntimeDirectory directive
# This ensures it persists across reboots (systemd recreates it)
echo "   ✓ Runtime directory will be managed by systemd"
echo ""

# Update systemd service files
echo "4. Updating systemd service files..."

# Backend service
cat > /etc/systemd/system/portfolio-backend.service << EOF
[Unit]
Description=Portfolio AI Backend (FastAPI)
After=network.target postgresql.service redis-server.service
Wants=postgresql.service redis-server.service

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_GROUP
WorkingDirectory=$BACKEND_DIR
Environment="PATH=$BACKEND_DIR/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="DB_POOL_SIZE=3"
Environment="DB_MAX_OVERFLOW=2"
Environment="NUMBA_CACHE_DIR=/var/cache/portfolio-ai/numba"
Environment="HF_HOME=/var/cache/portfolio-ai/huggingface"
EnvironmentFile=-$BACKEND_DIR/.env
RuntimeDirectory=portfolio-ai
ExecStart=$BACKEND_DIR/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10
StandardOutput=append:/var/log/portfolio-ai/backend.log
StandardError=append:/var/log/portfolio-ai/backend-error.log

[Install]
WantedBy=multi-user.target
EOF
echo "   ✓ Updated portfolio-backend.service"

# Celery worker service
cat > /etc/systemd/system/portfolio-celery.service << EOF
[Unit]
Description=Portfolio AI Celery Worker
After=network.target postgresql.service redis-server.service
Wants=postgresql.service redis-server.service

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_GROUP
WorkingDirectory=$BACKEND_DIR
Environment="PATH=$BACKEND_DIR/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="NUMBA_CACHE_DIR=/var/cache/portfolio-ai/numba"
Environment="HF_HOME=/var/cache/portfolio-ai/huggingface"
EnvironmentFile=-$BACKEND_DIR/.env
RuntimeDirectory=portfolio-ai
ExecStart=$BACKEND_DIR/.venv/bin/celery -A app.celery_app worker --loglevel=info --concurrency=2
Restart=always
RestartSec=10
StandardOutput=append:/var/log/portfolio-ai/celery-worker.log
StandardError=append:/var/log/portfolio-ai/celery-worker-error.log

[Install]
WantedBy=multi-user.target
EOF
echo "   ✓ Updated portfolio-celery.service"

# Celery beat service
cat > /etc/systemd/system/portfolio-beat.service << EOF
[Unit]
Description=Portfolio AI Celery Beat Scheduler
After=network.target postgresql.service redis-server.service
Wants=postgresql.service redis-server.service

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_GROUP
WorkingDirectory=$BACKEND_DIR
Environment="PATH=$BACKEND_DIR/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="NUMBA_CACHE_DIR=/var/cache/portfolio-ai/numba"
Environment="HF_HOME=/var/cache/portfolio-ai/huggingface"
EnvironmentFile=-$BACKEND_DIR/.env
RuntimeDirectory=portfolio-ai
ExecStart=$BACKEND_DIR/.venv/bin/celery -A app.celery_app beat --loglevel=info
Restart=always
RestartSec=10
StandardOutput=append:/var/log/portfolio-ai/celery-beat.log
StandardError=append:/var/log/portfolio-ai/celery-beat-error.log

[Install]
WantedBy=multi-user.target
EOF
echo "   ✓ Updated portfolio-beat.service"

# Frontend service
cat > /etc/systemd/system/portfolio-frontend.service << EOF
[Unit]
Description=Portfolio AI Frontend (Next.js)
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_GROUP
WorkingDirectory=$FRONTEND_DIR
Environment="PATH=$FRONTEND_DIR/node_modules/.bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="NODE_ENV=development"
EnvironmentFile=-$FRONTEND_DIR/.env.local
RuntimeDirectory=portfolio-ai
ExecStart=/usr/bin/npm run dev
Restart=always
RestartSec=10
StandardOutput=append:/var/log/portfolio-ai/frontend.log
StandardError=append:/var/log/portfolio-ai/frontend-error.log

[Install]
WantedBy=multi-user.target
EOF
echo "   ✓ Updated portfolio-frontend.service"
echo ""

# Update sudoers with !requiretty
echo "5. Updating sudoers configuration..."

SUDOERS_FILE="/etc/sudoers.d/portfolio-ai-services"

# Read existing file if it exists, otherwise create new
if [ -f "$SUDOERS_FILE" ]; then
    BACKUP_SUDOERS="${SUDOERS_FILE}.backup.$(date +%Y%m%d-%H%M%S)"
    cp "$SUDOERS_FILE" "$BACKUP_SUDOERS"
    echo "   ✓ Backed up existing sudoers file"
fi

cat > "$SUDOERS_FILE" << 'EOF'
# Portfolio AI - Passwordless sudo for service management
# User: kasadis
# Service user: portfolio-ai
# Created: 2025-11-07

# CRITICAL: Allow sudo without TTY (needed for Claude Code Bash tool)
Defaults:kasadis !requiretty

# Status commands
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl status portfolio-backend.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl status portfolio-celery.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl status portfolio-beat.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl status portfolio-frontend.service

# Start commands
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl start portfolio-backend.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl start portfolio-celery.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl start portfolio-beat.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl start portfolio-frontend.service

# Stop commands
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl stop portfolio-backend.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl stop portfolio-celery.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl stop portfolio-beat.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl stop portfolio-frontend.service

# Restart commands
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl restart portfolio-backend.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl restart portfolio-celery.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl restart portfolio-beat.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl restart portfolio-frontend.service

# Reload commands
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl reload portfolio-backend.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl reload portfolio-celery.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl reload portfolio-beat.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl reload portfolio-frontend.service

# is-active commands (for status checking)
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl is-active portfolio-backend.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl is-active portfolio-celery.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl is-active portfolio-beat.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl is-active portfolio-frontend.service

# Journalctl commands (for log viewing)
kasadis ALL=(root) NOPASSWD: /usr/bin/journalctl -u portfolio-backend.service*
kasadis ALL=(root) NOPASSWD: /usr/bin/journalctl -u portfolio-celery.service*
kasadis ALL=(root) NOPASSWD: /usr/bin/journalctl -u portfolio-beat.service*
kasadis ALL=(root) NOPASSWD: /usr/bin/journalctl -u portfolio-frontend.service*

# Daemon reload (for service file updates)
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl daemon-reload

# Redis service (optional)
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl status redis-server.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl restart redis-server.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl stop redis-server.service

# pkill commands for cleanup (used in test scripts)
kasadis ALL=(root) NOPASSWD: /usr/bin/pkill -9 -f uvicorn
kasadis ALL=(root) NOPASSWD: /usr/bin/pkill -9 -f celery
kasadis ALL=(root) NOPASSWD: /usr/bin/pkill -9 -f "next dev"

# Backup services - Veeam
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl start veeam-smart-backup.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl stop veeam-smart-backup.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl restart veeam-smart-backup.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl status veeam-smart-backup.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl is-active veeam-smart-backup.service
kasadis ALL=(root) NOPASSWD: /usr/bin/journalctl -u veeam-smart-backup.service*

# Veeam backup commands
kasadis ALL=(root) NOPASSWD: /usr/bin/veeamconfig job start *
kasadis ALL=(root) NOPASSWD: /usr/bin/veeamconfig job stop *
kasadis ALL=(root) NOPASSWD: /usr/bin/veeamconfig job list
kasadis ALL=(root) NOPASSWD: /usr/bin/veeamconfig session list

# Backup logs
kasadis ALL=(root) NOPASSWD: /usr/bin/cat /var/log/veeam-smart-backup.log
kasadis ALL=(root) NOPASSWD: /usr/bin/smbclient *
EOF

chmod 0440 "$SUDOERS_FILE"
echo "   ✓ Updated sudoers file with !requiretty"

# Validate sudoers syntax
if visudo -c -f "$SUDOERS_FILE"; then
    echo "   ✓ Sudoers file validated"
else
    echo -e "   ${RED}✗ Sudoers file has syntax errors!${NC}"
    if [ -f "$BACKUP_SUDOERS" ]; then
        mv "$BACKUP_SUDOERS" "$SUDOERS_FILE"
        echo "   ✓ Restored backup"
    fi
    exit 1
fi
echo ""

# Reload systemd
echo "6. Reloading systemd daemon..."
systemctl daemon-reload
echo "   ✓ Systemd reloaded"
echo ""

# Stop existing services (whether manual or systemd)
echo "7. Stopping existing services and processes..."
systemctl stop portfolio-backend.service 2>/dev/null || true
systemctl stop portfolio-celery.service 2>/dev/null || true
systemctl stop portfolio-beat.service 2>/dev/null || true
systemctl stop portfolio-frontend.service 2>/dev/null || true
sleep 2
pkill -9 -f "uvicorn.*main:app" 2>/dev/null || true
pkill -9 -f "celery.*worker" 2>/dev/null || true
pkill -9 -f "celery.*beat" 2>/dev/null || true
pkill -9 -f "next dev" 2>/dev/null || true
sleep 2
echo "   ✓ All services and processes stopped"
echo ""

# Start services
echo "8. Starting services as $SERVICE_USER..."
systemctl start portfolio-backend.service
sleep 2
systemctl start portfolio-celery.service
systemctl start portfolio-beat.service
systemctl start portfolio-frontend.service
sleep 3
echo "   ✓ Services started"
echo ""

# Verify services
echo "9. Verifying services..."
BACKEND_STATUS=$(systemctl is-active portfolio-backend.service || echo "inactive")
CELERY_STATUS=$(systemctl is-active portfolio-celery.service || echo "inactive")
BEAT_STATUS=$(systemctl is-active portfolio-beat.service || echo "inactive")
FRONTEND_STATUS=$(systemctl is-active portfolio-frontend.service || echo "inactive")

echo "   Backend:       $BACKEND_STATUS"
echo "   Celery Worker: $CELERY_STATUS"
echo "   Celery Beat:   $BEAT_STATUS"
echo "   Frontend:      $FRONTEND_STATUS"
echo ""

# Check process ownership
echo "10. Verifying process ownership..."
BACKEND_USER=$(ps aux | grep "uvicorn.*main:app" | grep -v grep | awk '{print $1}' | head -1)
CELERY_USER=$(ps aux | grep "celery.*worker" | grep -v grep | awk '{print $1}' | head -1)

if [ "$BACKEND_USER" = "$SERVICE_USER" ] && [ "$CELERY_USER" = "$SERVICE_USER" ]; then
    echo -e "   ${GREEN}✓ Processes running as $SERVICE_USER${NC}"
else
    echo -e "   ${YELLOW}⚠ Backend user: $BACKEND_USER, Celery user: $CELERY_USER${NC}"
fi
echo ""

# Test sudo without TTY (simulate Claude's Bash tool)
echo "11. Testing sudo without TTY (simulating Claude Code)..."
if su - kasadis -c "sudo systemctl is-active portfolio-backend.service" >/dev/null 2>&1; then
    echo -e "   ${GREEN}✓ Sudo works without TTY${NC}"
else
    echo -e "   ${YELLOW}⚠ Sudo without TTY might have issues${NC}"
fi
echo ""

# Final summary
echo "========================================="
echo -e "${GREEN}✓ Service Account Setup Complete${NC}"
echo "========================================="
echo ""
echo "Configuration:"
echo "  Service user:  $SERVICE_USER (system account)"
echo "  Service group: $SERVICE_GROUP"
echo "  Log directory: /var/log/portfolio-ai"
echo "  Run directory: /var/run/portfolio-ai"
echo ""
echo "Services running:"
echo "  Backend:       $BACKEND_STATUS"
echo "  Celery Worker: $CELERY_STATUS"
echo "  Celery Beat:   $BEAT_STATUS"
echo "  Frontend:      $FRONTEND_STATUS"
echo ""
echo "Benefits:"
echo "  ✓ More secure (service user has minimal permissions)"
echo "  ✓ Services persist when kasadis logs out"
echo "  ✓ Claude Code can control services autonomously (!requiretty)"
echo "  ✓ Production-ready pattern"
echo ""
echo "Logs:"
echo "  tail -f /var/log/portfolio-ai/backend.log"
echo "  tail -f /var/log/portfolio-ai/celery-worker.log"
echo "  tail -f /var/log/portfolio-ai/celery-beat.log"
echo "  tail -f /var/log/portfolio-ai/frontend.log"
echo ""
echo "Control services (same as before):"
echo "  bash ~/portfolio-ai/scripts/start.sh"
echo "  bash ~/portfolio-ai/scripts/restart.sh"
echo "  bash ~/portfolio-ai/scripts/shutdown.sh"
echo ""
echo "Or directly:"
echo "  sudo systemctl status portfolio-backend"
echo "  sudo systemctl restart portfolio-celery"
echo ""
