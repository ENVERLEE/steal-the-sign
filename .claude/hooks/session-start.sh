#!/bin/bash
# Claude Code on the web: 파이프라인 의존성 설치 (jinja2·sympy·numpy·jsonschema·playwright)
# 브라우저는 컨테이너에 미리 설치된 Chromium을 scripts/common.launch_chromium이 찾아 쓴다.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"
python3 -m pip install --quiet --disable-pip-version-check -r requirements.txt
