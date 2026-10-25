#!/usr/bin/env bash
set -euo pipefail
mkdir -p .cache
python3 --version
node --version
printf 'Python: %s; Node.js: %s\n' "$(python3 --version)" "$(node --version)" > .cache/ci-summary.md
[[ "$(node -p 'process.versions.node.split(".")[0]')" == 24 ]]
python3 -c 'import sys; assert sys.version_info[:2] == (3, 14)'
npm --prefix site ci
start=$SECONDS
make test
echo "Тесты: $((SECONDS - start)) с" >> .cache/ci-summary.md
start=$SECONDS
make site 2>&1 | tee .cache/site-build.log
{
  echo "Сборка: $((SECONDS - start)) с"
  echo "CACHE HIT: $(grep -c '^CACHE HIT' .cache/site-build.log || true)"
  echo "CACHE MISS: $(grep -c '^CACHE MISS' .cache/site-build.log || true)"
} >> .cache/ci-summary.md
