#!/usr/bin/env bash
set -euo pipefail

# collectstatic does NOT run here — it runs at image build time (see Dockerfile).
# It cannot go in release_command (Fly discards that Machine's filesystem, so the
# output would never reach the Machine serving traffic), but the image layer is
# on every Machine, which is what it needed all along. Running it on boot cost
# ~5 minutes before gunicorn could bind and made health checks time out the
# deploy. Keep this script's path to `exec` short: the health check starts
# probing 30s after boot (fly.toml grace_period).
#
# --no-sync: the image's venv was already built with `uv sync --frozen --no-dev`
# in the Dockerfile; without this flag, `uv run` re-syncs against pyproject.toml's
# default groups at every boot and pulls dev-only deps (ruff, pytest, ...) into
# the running container.

# Redis is optional (kept out of the baseline deployment to avoid a paid Upstash
# instance). When REDIS_URL is set, run gunicorn AND the Celery worker together
# via honcho (the Procfile). When it is unset, Celery runs tasks eagerly/inline
# (see config/settings/production.py) so there is no broker and no worker to run
# — just serve the web process. Set REDIS_URL later to move async work off the
# request path with no other change. The bind port must match fly.toml's
# internal_port and the Procfile web line.
if [ -n "${REDIS_URL:-}" ]; then
  exec uv run --no-sync honcho start
else
  exec uv run --no-sync gunicorn config.wsgi:application \
    --bind 0.0.0.0:8443 --workers 3 --timeout 120
fi
