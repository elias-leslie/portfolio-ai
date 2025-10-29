# Portfolio AI Platform - Service Management

Quick reference for starting, stopping, and managing Portfolio AI Platform services.

---

## 🚀 Quick Start

### Start All Services

```bash
cd ~/portfolio-ai
./scripts/start.sh
```

This starts:
- Redis (message broker for Celery)
- Backend API (FastAPI on port 8000)
- Celery worker (background jobs)
- Frontend (Next.js on port 3000)

### Restart All Services

```bash
cd ~/portfolio-ai
./scripts/restart.sh
```

**Use this when:**
- You've changed `.env.local` or environment variables
- Backend code changes aren't being picked up
- Frontend isn't reflecting API changes

### Stop All Services

```bash
cd ~/portfolio-ai
./scripts/shutdown.sh
```

You'll be prompted whether to stop Redis (usually leave it running).

---

## 📋 Service Details

### Backend API (FastAPI)

**URL:** http://localhost:8000
**Docs:** http://localhost:8000/docs (Swagger UI)
**Log:** `/tmp/portfolio-backend.log`

**Manual Start:**
```bash
cd ~/portfolio-ai/backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Check Status:**
```bash
curl http://localhost:8000/
pgrep -f "uvicorn.*main:app"
```

### Frontend (Next.js)

**URL:** http://localhost:3000
**Log:** `/tmp/portfolio-frontend.log`

**Manual Start:**
```bash
cd ~/portfolio-ai/frontend
npm run dev
```

**Check Status:**
```bash
curl http://localhost:3000/
pgrep -f "next.*dev"
```

### Celery Worker

**Log:** `/tmp/portfolio-celery.log`

**Manual Start:**
```bash
cd ~/portfolio-ai/backend
source .venv/bin/activate
celery -A app.celery_app worker --loglevel=info
```

**Check Status:**
```bash
pgrep -f "celery.*worker"
```

### Redis

**Manual Start:**
```bash
redis-server --daemonize yes
```

**Check Status:**
```bash
pgrep -x redis-server
redis-cli ping  # Should return PONG
```

---

## 🔍 Monitoring & Logs

### View Real-Time Logs

**Backend:**
```bash
tail -f /tmp/portfolio-backend.log
```

**Frontend:**
```bash
tail -f /tmp/portfolio-frontend.log
```

**Celery:**
```bash
tail -f /tmp/portfolio-celery.log
```

**All at once (tmux recommended):**
```bash
# Terminal 1
tail -f /tmp/portfolio-backend.log

# Terminal 2
tail -f /tmp/portfolio-frontend.log

# Terminal 3
tail -f /tmp/portfolio-celery.log
```

### Check Service Status

```bash
echo "Redis:    $(pgrep -x redis-server > /dev/null && echo 'Running' || echo 'Stopped')"
echo "Backend:  $(pgrep -f 'uvicorn.*main:app' > /dev/null && echo 'Running' || echo 'Stopped')"
echo "Celery:   $(pgrep -f 'celery.*worker' > /dev/null && echo 'Running' || echo 'Stopped')"
echo "Frontend: $(pgrep -f 'next.*dev' > /dev/null && echo 'Running' || echo 'Stopped')"
```

---

## 🛠️ Troubleshooting

### "Failed to fetch watchlist: Not Found"

**Solution:** Restart the frontend to pick up API URL changes
```bash
pkill -f "next.*dev"
cd ~/portfolio-ai/frontend
npm run dev
```

### Backend not responding

**Check if it's running:**
```bash
curl http://localhost:8000/
```

**View recent errors:**
```bash
tail -50 /tmp/portfolio-backend.log
```

**Restart backend:**
```bash
pkill -f "uvicorn.*main:app"
cd ~/portfolio-ai/backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend not loading

**Check if it's running:**
```bash
pgrep -f "next.*dev"
```

**View build errors:**
```bash
tail -50 /tmp/portfolio-frontend.log
```

**Clear cache and restart:**
```bash
pkill -f "next.*dev"
cd ~/portfolio-ai/frontend
rm -rf .next
npm run dev
```

### Redis connection errors

**Start Redis:**
```bash
redis-server --daemonize yes
```

**Test connection:**
```bash
redis-cli ping
# Should return: PONG
```

### Port already in use

**Backend (port 8000):**
```bash
# Find process using port 8000
lsof -i :8000
# Kill it
kill -9 <PID>
```

**Frontend (port 3000):**
```bash
# Find process using port 3000
lsof -i :3000
# Kill it
kill -9 <PID>
```

---

## 🔧 Configuration

### Environment Variables

**Backend:** `~/portfolio-ai/backend/.env` (optional, uses defaults)

**Frontend:** `~/portfolio-ai/frontend/.env.local` (required)
```bash
# Set API URL for local development
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Verify Configuration

**Backend:**
```bash
cd ~/portfolio-ai/backend
source .venv/bin/activate
python -c "from app.config import get_config; print(get_config())"
```

**Frontend:**
```bash
cd ~/portfolio-ai/frontend
cat .env.local
```

---

## 📝 Development Workflow

### Typical Development Session

```bash
# 1. Start all services
cd ~/portfolio-ai
./scripts/start.sh

# 2. Make code changes...

# 3. Backend changes are auto-reloaded
# 4. Frontend changes are auto-reloaded via hot reload

# 5. If environment changes, restart
./scripts/restart.sh

# 6. When done for the day
./scripts/shutdown.sh
```

### Running Tests

**Backend:**
```bash
cd ~/portfolio-ai/backend
source .venv/bin/activate
pytest tests/ -v
```

**Linting:**
```bash
cd ~/portfolio-ai
./scripts/lint.sh
```

---

## 🎯 Watchlist Feature Testing

### Access Watchlist UI

```bash
# Ensure services are running
./scripts/start.sh

# Open browser to:
# http://localhost:3000/watchlist
```

### Test Checklist

- [ ] Add ticker (e.g., AAPL)
- [ ] View watchlist table
- [ ] Sort by different columns
- [ ] Expand row to see details
- [ ] Edit notes
- [ ] Delete ticker
- [ ] Manual refresh
- [ ] Navigate to Settings
- [ ] Adjust watchlist preferences (refresh interval, weights)
- [ ] Save settings

### API Testing

**List watchlist:**
```bash
curl "http://localhost:8000/api/watchlist?account_id=default" | jq
```

**Add ticker:**
```bash
curl -X POST http://localhost:8000/api/watchlist \
  -H "Content-Type: application/json" \
  -d '{"account_id":"default","symbol":"AAPL","note":"Apple Inc."}'
```

**Refresh scores:**
```bash
curl -X POST http://localhost:8000/api/watchlist/refresh \
  -H "Content-Type: application/json" \
  -d '{"account_id":"default"}'
```

---

## 🔄 Common Commands

| Task | Command |
|------|---------|
| Start all | `./scripts/start.sh` |
| Restart all | `./scripts/restart.sh` |
| Stop all | `./scripts/shutdown.sh` |
| Backend logs | `tail -f /tmp/portfolio-backend.log` |
| Frontend logs | `tail -f /tmp/portfolio-frontend.log` |
| Celery logs | `tail -f /tmp/portfolio-celery.log` |
| Run tests | `cd ~/portfolio-ai/backend && source .venv/bin/activate && pytest tests/` |
| Run linter | `cd ~/portfolio-ai && ./scripts/lint.sh` |
| API docs | Open http://localhost:8000/docs |
| Watchlist UI | Open http://localhost:3000/watchlist |

---

**Last Updated:** 2025-10-29
**Version:** 1.2.0-dev (Watchlist Phase 1 Complete)
