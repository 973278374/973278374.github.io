#!/usr/bin/env bash
# 本机 API（仅 127.0.0.1）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate
exec python -m bridge.api
