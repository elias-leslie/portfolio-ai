# Cloud Environment Capability Test

**Purpose**: Determine what commands actually work in cloud Claude Code sandbox environment

**Instructions for Cloud Agent**:
1. Run through each test category below
2. For each command, try to execute it
3. Record: ✅ SUCCESS or ❌ FAILED (with error message)
4. At the end, provide a summary of what works and what doesn't
5. **Be systematic** - try every command even if some fail

---

## Test Results Format

For each command, report like this:
```
Command: <command>
Result: ✅ SUCCESS / ❌ FAILED
Output: <first few lines of output or error>
Notes: <any observations>
```

---

## Category 1: Basic File Operations

### Test 1.1: Read Files
```bash
cat README.md
```

### Test 1.2: List Files
```bash
ls -la
```

### Test 1.3: Find Files
```bash
find . -name "*.py" -type f | head -5
```

### Test 1.4: Search Content
```bash
grep -r "portfolio" --include="*.md" | head -5
```

### Test 1.5: Check Working Directory
```bash
pwd
```

### Test 1.6: Tree Structure (if available)
```bash
tree -L 2 -d
```

---

## Category 2: Git Operations

### Test 2.1: Git Status
```bash
git status
```

### Test 2.2: Git Log
```bash
git log --oneline -5
```

### Test 2.3: Git Branch
```bash
git branch
```

### Test 2.4: Git Diff
```bash
git diff HEAD~1
```

### Test 2.5: Create Test Branch
```bash
git checkout -b test-cloud-capabilities
```

### Test 2.6: Return to Main
```bash
git checkout main
```

### Test 2.7: Delete Test Branch
```bash
git branch -d test-cloud-capabilities
```

---

## Category 3: Python Virtual Environment

### Test 3.1: Check Python
```bash
python --version
```

### Test 3.2: Check Python3
```bash
python3 --version
```

### Test 3.3: Source Venv (EXPECTED TO FAIL/HANG)
**⚠️ WARNING: This might hang - try with short timeout**
```bash
# Try this carefully - it might hang
timeout 5 source backend/.venv/bin/activate
```

### Test 3.4: Check if Venv Exists
```bash
ls -la backend/.venv/bin/activate
```

### Test 3.5: Python in Venv (without activating)
```bash
backend/.venv/bin/python --version
```

### Test 3.6: Run Python Script (without venv)
```bash
python3 -c "print('Hello from Python')"
```

---

## Category 4: Node/NPM Operations

### Test 4.1: Node Version
```bash
node --version
```

### Test 4.2: NPM Version
```bash
npm --version
```

### Test 4.3: Check Package.json
```bash
cat frontend/package.json | head -20
```

### Test 4.4: NPM List (check installed packages)
```bash
npm list --depth=0 2>/dev/null || echo "Failed or not installed"
```

---

## Category 5: Testing Commands

### Test 5.1: Pytest Version
```bash
pytest --version
```

### Test 5.2: Pytest Help
```bash
pytest --help | head -10
```

### Test 5.3: Run Pytest (EXPECTED TO FAIL)
```bash
timeout 5 pytest --version 2>&1
```

### Test 5.4: NPM Test (EXPECTED TO FAIL)
```bash
timeout 5 npm test 2>&1 || echo "Failed as expected"
```

---

## Category 6: Service/Network Operations

### Test 6.1: Curl Command (to external site)
```bash
curl -I https://www.google.com 2>&1 | head -5
```

### Test 6.2: Curl Localhost (EXPECTED TO FAIL)
```bash
timeout 3 curl http://localhost:8000 2>&1
```

### Test 6.3: Check for Running Services
```bash
ps aux | grep -E "(uvicorn|celery|next)" | head -5
```

### Test 6.4: Netstat/SS (check ports)
```bash
netstat -tuln 2>/dev/null || ss -tuln 2>/dev/null || echo "Neither netstat nor ss available"
```

---

## Category 7: Database Operations

### Test 7.1: Which Psql
```bash
which psql
```

### Test 7.2: Psql Version
```bash
psql --version
```

### Test 7.3: Psql Connection (EXPECTED TO FAIL)
```bash
timeout 3 psql -U portfolio_ai_user -d portfolio_ai -c "SELECT 1" 2>&1
```

---

## Category 8: Project-Specific Scripts

### Test 8.1: Check Script Exists
```bash
ls -la scripts/restart.sh
```

### Test 8.2: Run Project Script (EXPECTED TO FAIL)
```bash
timeout 5 bash scripts/status.sh 2>&1
```

---

## Category 9: Code Analysis Tools

### Test 9.1: Ruff Version
```bash
ruff --version
```

### Test 9.2: Mypy Version
```bash
mypy --version
```

### Test 9.3: ESLint Version
```bash
npx eslint --version 2>&1
```

### Test 9.4: Run Ruff Check (without venv)
```bash
ruff check backend/app/main.py 2>&1 | head -10
```

---

## Category 10: File Writing/Editing

### Test 10.1: Create Test File
```bash
echo "test content" > /tmp/test-cloud-capabilities.txt
```

### Test 10.2: Read Test File
```bash
cat /tmp/test-cloud-capabilities.txt
```

### Test 10.3: Edit Test File
```bash
echo "modified content" >> /tmp/test-cloud-capabilities.txt
```

### Test 10.4: Verify Edit
```bash
cat /tmp/test-cloud-capabilities.txt
```

### Test 10.5: Delete Test File
```bash
rm /tmp/test-cloud-capabilities.txt
```

---

## Category 11: Advanced Search/Analysis

### Test 11.1: Ripgrep (rg)
```bash
rg --version
```

### Test 11.2: Ripgrep Search
```bash
rg "portfolio" --type md | head -5
```

### Test 11.3: Ack Search
```bash
ack --version
```

### Test 11.4: Locate Command
```bash
locate --version 2>&1 | head -3
```

---

## Category 12: System Information

### Test 12.1: OS Info
```bash
uname -a
```

### Test 12.2: Disk Space
```bash
df -h | head -5
```

### Test 12.3: Memory Info
```bash
free -h 2>/dev/null || echo "free command not available"
```

### Test 12.4: CPU Info
```bash
cat /proc/cpuinfo | head -20 2>/dev/null || echo "Not available"
```

### Test 12.5: Environment Variables
```bash
env | grep -E "(PATH|HOME|USER)" | head -10
```

---

## Final Summary Template

After completing all tests, provide this summary:

```markdown
# Cloud Environment Capability Summary

## ✅ Commands That Work

**File Operations:**
- [List which file commands worked]

**Git Operations:**
- [List which git commands worked]

**Python:**
- [What python commands worked]

**Node/NPM:**
- [What node commands worked]

**Other Tools:**
- [Any other working tools]

---

## ❌ Commands That Failed

**Definitively Broken:**
- [Commands that failed with errors]

**Timeout/Hang:**
- [Commands that timed out or hung]

**Not Available:**
- [Commands not found in environment]

---

## 🔍 Key Findings

1. **Virtual Environments**: [Can/Cannot activate venv]
2. **Testing**: [Can/Cannot run pytest/npm test]
3. **Services**: [Can/Cannot connect to localhost]
4. **Database**: [Can/Cannot connect to postgres]
5. **Network**: [Can/Cannot curl external sites]
6. **File Writing**: [Can/Cannot write to filesystem]

---

## 💡 Recommendations for /cloud_task_it

Based on these results, the cloud agent should:

**Definitely CAN use:**
- [List safe commands]

**Definitely CANNOT use:**
- [List broken commands]

**Use with Caution:**
- [Commands that might work but have issues]
```

---

## Instructions for User

After cloud agent completes this test:

1. **Review the summary**
2. **Share results with dev environment Claude**
3. **Update `/cloud_task_it` command** with accurate constraints
4. **Update task templates** to reflect actual capabilities

This will ensure cloud task lists are accurate and cloud agents don't waste time trying commands that don't work.
