#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"

cd "$REPO_ROOT"

"$PYTHON_BIN" -m pip install -e 'engine[dev,server,scanner]'
"$PYTHON_BIN" -m playwright install chromium
"$PYTHON_BIN" -m pytest engine -m release_smoke
mvn -f sdk-java/pom.xml test

(
  cd sdk-typescript
  npm ci
  npm test
)
