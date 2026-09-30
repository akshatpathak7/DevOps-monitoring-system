FROM ghcr.io/astral-sh/uv:0.11.6 AS uv
FROM python:3.12-slim AS base
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
ENV PATH="/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
RUN useradd --uid 10001 --create-home app

FROM base AS test
RUN uv sync --frozen --no-install-project
COPY tests ./tests
USER app
CMD ["pytest", "-q", "-p", "no:cacheprovider"]

FROM base AS runtime
USER app
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --no-proxy-headers"]
