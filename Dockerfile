ARG PYTHON_VERSION=3.12-slim

FROM python:${PYTHON_VERSION}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1

# libmagic1 — required by python-magic (apps.tenders MIME sniffing on upload).
# No libpq-dev/gcc: psycopg[binary] ships precompiled wheels, nothing to build.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /code

# Install deps in their own layer first so `uv sync` is cached across builds
# that only change application code.
COPY pyproject.toml uv.lock /code/
RUN uv sync --frozen --no-dev --no-install-project

COPY . /code
RUN uv sync --frozen --no-dev

# Put the project venv on PATH so a bare `python`/`gunicorn`/`celery` (without
# `uv run`) resolves to the installed deps. This makes the release_command work
# regardless of how Fly invokes it: the app's server-side release_command is a
# stale `python manage.py migrate --noinput` (from an earlier `fly launch`) that
# `flyctl deploy` isn't overwriting, and bare `python` would otherwise hit the
# base image's Django-less system interpreter and exit 1 before any log flushes.
# Belt-and-suspenders with fly.toml's `uv run --no-sync python manage.py migrate`.
ENV PATH="/code/.venv/bin:$PATH" \
    VIRTUAL_ENV="/code/.venv"

RUN chmod +x bin/start.sh

EXPOSE 8000

CMD ["./bin/start.sh"]
