# syntax=docker/dockerfile:1.7

FROM node:22-bookworm-slim AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --silent
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="Shogun Server"
LABEL org.opencontainers.image.description="Shogun and The Tenshu production server"
LABEL org.opencontainers.image.source="https://github.com/AlphaHorizon-AI/Shogun"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    SHOGUN_NO_BROWSER=true \
    DEPLOYMENT_MODE=server

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git tini \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md alembic.ini version.json ./
COPY shogun/ ./shogun/
COPY migrations/ ./migrations/

RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu "torch>=2.4.0" \
    && pip install --no-cache-dir ".[server]" \
    && pip install --no-cache-dir --upgrade \
        "jaraco.context>=6.1.0" \
        "setuptools>=78.1.1" \
        "wheel>=0.46.2" \
    && python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/* /root/.cache

COPY --from=frontend-builder /build/frontend/dist ./frontend/dist
COPY scripts/docker-entrypoint.sh /usr/local/bin/shogun-entrypoint

RUN groupadd --gid 10001 shogun \
    && useradd --uid 10001 --gid shogun --home-dir /app --shell /usr/sbin/nologin shogun \
    && mkdir -p /app/data /app/vault /app/logs /app/configs /app/tmp \
    && touch /app/.env \
    && chmod 0755 /usr/local/bin/shogun-entrypoint \
    && chown -R shogun:shogun \
        /app/data /app/vault /app/logs /app/configs /app/tmp /app/.env \
    && chmod -R a+rX /ms-playwright

USER shogun

EXPOSE 8000
VOLUME ["/app/data", "/app/vault", "/app/logs", "/app/configs"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=5 \
    CMD curl --fail --silent http://127.0.0.1:8000/api/v1/health || exit 1

ENTRYPOINT ["tini", "--", "shogun-entrypoint"]
CMD ["python", "-m", "shogun"]
