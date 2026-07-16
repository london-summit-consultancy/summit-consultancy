#!/usr/bin/env bash
set -euo pipefail

# Runs on every Machine start (not in release_command — Fly destroys that
# Machine's filesystem after it runs, so anything written there, like
# collectstatic output, would never reach the Machine that actually serves
# traffic). Safe to repeat on every boot: collectstatic is idempotent.
# --no-sync: the image's venv was already built with `uv sync --frozen --no-dev`
# in the Dockerfile; without this flag, `uv run` re-syncs against pyproject.toml's
# default groups at every boot and pulls dev-only deps (ruff, pytest, ...) into
# the running container.
uv run --no-sync python manage.py collectstatic --noinput

exec uv run --no-sync honcho start
