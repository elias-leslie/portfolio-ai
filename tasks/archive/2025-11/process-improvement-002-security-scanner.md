# Process Improvement #2: Security Scanner Tuning

**Date**: 2025-11-09
**Issue**: High false positive rate in security checks (14 reported critical issues, 0 actual vulnerabilities)
**Impact**: Noise reduces signal, wastes time investigating false positives

---

## 📊 False Positive Analysis

### Current Results:
- **Reported**: 14 critical security issues
- **Actual**: 0 exploitable vulnerabilities
- **False Positive Rate**: 100%

### Categories:

#### 1. API Key Detection (9 false positives)
**Pattern detected**: `api_key=` in code
**Reality**: All keys from `os.environ.get()`, none hardcoded
**Example**:
```python
# Scanner flags this:
finnhub_source = FinnhubSource(api_key=finnhub_key)

# But finnhub_key comes from:
finnhub_key = os.environ.get("FINNHUB_API_KEY")  # Safe!
```

**Fix**: Scanner should check if value comes from `os.environ/os.getenv`

#### 2. SQL Injection Detection (5 false positives)
**Pattern detected**: f-strings in SQL (`f"DELETE FROM {table_name}"`)
**Reality**: All table names hardcoded, no user input
**Example**:
```python
# Scanner flags this:
conn.execute(f"DELETE FROM {table_name}")

# But all callers use hardcoded values:
storage.insert_dataframe("day_bars", result_df)  # Safe!
```

**Fix**: Scanner should:
- Check if variable comes from function parameter that accepts user input
- Whitelist known-safe table name sources
- Or require explicit validation marker

---

## ✅ Recommended Scanner Improvements

### Priority 1: Reduce False Positives

1. **Context-aware API key detection**
   ```bash
   # Bad (current):
   grep "api_key" | count as "exposed"

   # Good (improved):
   grep "api_key\s*=\s*[\"']" | exclude lines with "os.environ"
   ```

2. **Flow analysis for SQL injection**
   ```bash
   # Check if f-string variables come from:
   # - Function parameters with @validate_table_name
   # - Hardcoded strings
   # - Enum values
   # Only flag if source is user-controlled
   ```

3. **Severity levels**
   - CRITICAL: Actually exploitable (user input → SQL/secrets)
   - WARNING: Dangerous pattern but currently safe
   - INFO: Best practice violation but no risk

### Priority 2: Add Real Checks

Things the scanner SHOULD catch but doesn't:

1. **Hardcoded credentials** (passwords, tokens in code)
   ```python
   # Should flag:
   PASSWORD = "admin123"
   TOKEN = "sk-abc123..."
   ```

2. **Unsafe deserialization**
   ```python
   # Should flag:
   pickle.loads(user_data)  # RCE risk!
   eval(user_input)  # Code injection!
   ```

3. **Command injection**
   ```python
   # Should flag:
   os.system(f"curl {user_url}")  # Shell injection!
   ```

4. **Path traversal**
   ```python
   # Should flag:
   open(f"data/{user_filename}")  # Can access ../../../etc/passwd
   ```

### Priority 3: Documentation

1. **False Positive Suppression**
   ```python
   # nosec: table_name from enum, not user input
   conn.execute(f"DELETE FROM {table_name}")
   ```

2. **Security Patterns Document**
   - How to handle API keys (environment only)
   - How to build SQL safely (parameterized queries, whitelists)
   - How to validate user input (sanitization, validation)

---

## 🔧 Proposed Implementation

### Updated `check-security.sh`

```bash
#!/bin/bash
# Enhanced security check with reduced false positives

# 1. Hardcoded credentials (CRITICAL)
echo "Checking for hardcoded credentials..."
rg -i '(password|secret|token)\s*=\s*["\'][^"\']+["\']' \
   --type py \
   --glob '!test_*.py' \
   --glob '!conftest.py'

# 2. API keys NOT from environment (CRITICAL)
echo "Checking for hardcoded API keys..."
rg 'api_key\s*=\s*["\'][^"\']+["\']' \
   --type py \
   --glob '!test_*.py'

# 3. SQL injection patterns (WARNING if validated, CRITICAL if not)
echo "Checking for potential SQL injection..."
# Only flag if no validation comment
rg 'f"(SELECT|INSERT|UPDATE|DELETE).*\{[^}]+\}"' \
   --type py \
   --glob '!test_*.py' \
   | grep -v '# nosec:' \
   | grep -v 'validated'

# 4. Command injection (CRITICAL)
echo "Checking for command injection risks..."
rg '(os\.system|subprocess\.(call|run|Popen)).*f"' \
   --type py

# 5. Unsafe deserialization (CRITICAL)
echo "Checking for unsafe deserialization..."
rg '(pickle\.loads|eval|exec)\(' \
   --type py \
   --glob '!test_*.py'
```

### Updated Pre-Commit Hook

```yaml
- id: check-critical-security
  name: Security check (hardcoded credentials, code injection)
  entry: bash .claude/skills/code-quality/scripts/check-security-v2.sh
  # Only reports CRITICAL (exploitable), not WARNING (safe patterns)
```

---

## 📈 Success Metrics

**Before**:
- 14 reported issues
- 0 real vulnerabilities
- 100% false positive rate
- Developers ignore warnings

**After** (Target):
- 0-2 reported issues
- 0 real vulnerabilities
- <10% false positive rate
- Developers trust and act on warnings

---

## 🎯 Action Items

1. **Short term** (current task):
   - [x] Document findings
   - [ ] Add table name validation to IngestionManager
   - [ ] Add validation markers (`# validated:` comments)
   - [ ] Update security documentation

2. **Medium term** (next sprint):
   - [ ] Implement check-security-v2.sh with improvements
   - [ ] Add real vulnerability checks (command injection, unsafe deser)
   - [ ] Update pre-commit hooks to use v2

3. **Long term** (future enhancement):
   - [ ] Integrate proper SAST tool (bandit, semgrep)
   - [ ] Add security testing to CI/CD
   - [ ] Regular security audit schedule

---

## 📚 Related Documentation

- Security best practices: `docs/security-patterns.md` (to be created)
- Code quality standards: `docs/core/DEVELOPMENT.md`
- Pre-commit hooks: `.pre-commit-config.yaml`

---

**Status**: Documented, awaiting implementation
**Priority**: MEDIUM (no actual vulnerabilities, but pattern improvements valuable)
**Effort**: 3-4 hours for validation + documentation
