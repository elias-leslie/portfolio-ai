# Journald Logging Configuration

## Current Status

**PostgreSQL and Redis**: ✅ Configured and logging to journald
**Backend/Celery/Frontend**: ❌ Still logging to files, need configuration

## Problem

The systemd service files currently have:
```
StandardOutput=append:/var/log/portfolio-ai/backend.log
StandardError=append:/var/log/portfolio-ai/backend-error.log
```

This redirects all output to files instead of journald, preventing the unified log stream from showing these services.

## Solution

Run the configuration script to create systemd overrides:

```bash
# Configure all services for journald
bash ~/portfolio-ai/scripts/configure-services-journald.sh

# Restart services to apply changes
bash ~/portfolio-ai/scripts/restart.sh

# Verify services are logging to journald
journalctl -u portfolio-backend -n 20 --no-pager
journalctl -u portfolio-celery -n 20 --no-pager
```

## What the Script Does

1. Creates override files at `/etc/systemd/system/{service}.service.d/journald-logging.conf`
2. Sets `StandardOutput=journal` and `StandardError=journal`
3. Adds `SyslogIdentifier` for each service
4. Reloads systemd daemon

## Rollback

If you need to revert to file logging:

```bash
sudo rm -rf /etc/systemd/system/portfolio-*.service.d/journald-logging.conf
sudo systemctl daemon-reload
bash ~/portfolio-ai/scripts/restart.sh
```

## Benefits of Journald

- **Unified chronological stream**: See events from all services in order
- **Microsecond precision**: Accurate timing for debugging race conditions
- **Structured data**: Filter by service, level, time range
- **Automatic rotation**: No manual log rotation needed
- **Query performance**: Fast filtering with journalctl

## File Logs vs Journald

**Before** (File logs):
- Separate log files per service
- Manual correlation needed
- No unified timestamps
- Manual rotation/cleanup

**After** (Journald):
- Single chronological stream
- Automatic timestamps
- Fast filtering (`journalctl -u service --since "5 min ago"`)
- Automatic management

## Verification Commands

```bash
# Check all services are running
bash ~/portfolio-ai/scripts/status.sh

# View unified logs (last 5 minutes)
curl -s "http://localhost:8000/api/status/unified-logs?lines=100"

# View specific service
curl -s "http://localhost:8000/api/status/unified-logs?service=backend&lines=50"

# View only errors
curl -s "http://localhost:8000/api/status/unified-logs?level=ERROR&lines=50"

# Direct journalctl access
journalctl -u portfolio-backend -u portfolio-celery -u postgresql@16-main --since "5 min ago" --no-pager
```
