#!/usr/bin/env bash
# init.sh — Environment verification and initialization
#
# This script is executed by the agent at the INCEPTION of a session and prior to
# declaring any task as `done`. If it fails, the session must not proceed.
#
# Expected output: deterministic exit codes and blocks prefixed with [OK]/[FAIL].

set -u
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

ok()    { printf "${GREEN}[OK]${NC}    %s\n" "$1"; }
warn()  { printf "${YELLOW}[WARN]${NC}  %s\n" "$1"; }
fail()  { printf "${RED}[FAIL]${NC}  %s\n" "$1"; }

EXIT_CODE=0

echo "── 1. Verifying environment ────────────────────────────"

# Detect virtual environment python
PYTHON="python3"
if [ -f "venv/Scripts/python.exe" ]; then
  PYTHON="venv/Scripts/python.exe"
elif [ -f "venv/Scripts/python" ]; then
  PYTHON="venv/Scripts/python"
elif [ -f "venv/bin/python" ]; then
  PYTHON="venv/bin/python"
fi

# Python available
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  fail "python is not installed"
  exit 1
fi
ok "python -> $($PYTHON --version)"

# Minimum version 3.9 (dataclasses + modern typing)
PY_VERSION_OK=$($PYTHON -c 'import sys; print(int(sys.version_info >= (3, 9)))' | tr -d '\r')
if [ "$PY_VERSION_OK" != "1" ]; then
  fail "Python >= 3.9 is required"
  exit 1
fi
ok "Python version is compatible"

echo ""
echo "── 2. Verifying base harness files ─────────────────────"

for f in AGENTS.md feature_list.json progress/current.md docs/architecture.md docs/conventions.md docs/verification.md CHECKPOINTS.md; do
  if [ ! -f "$f" ]; then
    fail "Base file missing: $f"
    EXIT_CODE=1
  else
    ok "Exists $f"
  fi
done

echo ""
echo "── 3. Validating feature_list.json and specs ───────────"

"$PYTHON" - <<'PY'
import json, os, sys
try:
    data = json.load(open("feature_list.json"))
    valid = {"pending", "spec_ready", "in_progress", "done", "blocked"}
    in_progress = [f for f in data["features"] if f["status"] == "in_progress"]
    if len(in_progress) > 1:
        print(f"[FAIL]  There are {len(in_progress)} features in_progress (maximum 1 allowed)")
        sys.exit(1)
    requires_spec = {"spec_ready", "in_progress", "done"}
    spec_errors = []
    for f in data["features"]:
        if f["status"] not in valid:
            print(f"[FAIL]  Invalid status in feature {f['id']}: {f['status']}")
            sys.exit(1)
        if f.get("sdd") and f["status"] in requires_spec:
            spec_dir = os.path.join("specs", f["name"])
            for fname in ("requirements.md", "design.md", "tasks.md"):
                if not os.path.isfile(os.path.join(spec_dir, fname)):
                    spec_errors.append(
                        f"feature {f['id']} ({f['name']}) in {f['status']} "
                        f"missing {spec_dir}/{fname}"
                    )
    if spec_errors:
        for e in spec_errors:
            print(f"[FAIL]  {e}")
        sys.exit(1)
    print(f"[OK]    feature_list.json is valid ({len(data['features'])} features)")
    print(f"[OK]    Specs exist for sdd features with non-pending status")
except SystemExit:
    raise
except Exception as e:
    print(f"[FAIL]  feature_list.json or specs invalid: {e}")
    sys.exit(1)
PY

if [ $? -ne 0 ]; then EXIT_CODE=1; fi

echo ""
echo "── 4. Executing test suite ─────────────────────────────"

if [ -d "tests" ]; then
  if "$PYTHON" -m unittest discover -s tests -v 2>&1; then
    ok "All tests passed successfully"
  else
    fail "There are failing tests"
    EXIT_CODE=1
  fi
else
  warn "Directory tests/ does not exist yet"
fi

echo ""
echo "── 5. Summary ──────────────────────────────────────────"

if [ $EXIT_CODE -eq 0 ]; then
  ok "Environment is ready. You may commence work."
else
  fail "Environment is NOT ready. Resolve the errors before proceeding."
fi

exit $EXIT_CODE
