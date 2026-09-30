#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
trap 'docker compose -p themisto-tests -f compose.test.yaml down --volumes' EXIT
docker compose -p themisto-tests -f compose.test.yaml up --build --abort-on-container-exit --exit-code-from tests
