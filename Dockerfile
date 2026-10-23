# syntax=docker/dockerfile:1.7

FROM node:22.23.4-bookworm-slim AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --silent --strict-ssl=true --engine-strict
COPY LICENSE.md /build/LICENSE.md
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime

ARG VCS_REF=unknown

LABEL org.opencontainers.image.title="Shogun AFM"
LABEL org.opencontainers.image.description="Shogun and The Tenshu production server"
LABEL org.opencontainers.image.vendor="Alpha Horizon"
LABEL org.opencontainers.image.authors="Michael Peric / Alpha Horizon"
LABEL org.opencontainers.image.source="https://github.com/AlphaHorizon-AI/Shogun"
LABEL org.opencontainers.image.revision="${VCS_REF}"
LABEL org.opencontainers.image.url="https://www.alphahorizon.io/shogun/"
LABEL org.opencontainers.image.licenses="Shogun AFM Free Use License"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    SHOGUN_NO_BROWSER=true \
    DEPLOYMENT_MODE=server \
    SHOGUN_VENDOR="Alpha Horizon" \
    SHOGUN_PRODUCT="Shogun AFM" \
    SHOGUN_DISTRIBUTION_CHANNEL=official_docker \
    SHOGUN_SOURCE_REPOSITORY=https://github.com/AlphaHorizon-AI/Shogun
ENV SHOGUN_GIT_SHA=${VCS_REF}

WORKDIR /app

COPY --from=frontend-builder /usr/local/bin/node /usr/local/bin/node
COPY --from=frontend-builder /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
COPY --from=frontend-builder /usr/local/LICENSE /usr/local/share/licenses/node/LICENSE
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm
ENV PLAYWRIGHT_NODEJS_PATH=/usr/local/bin/node

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends ca-certificates curl git tini libatomic1 libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md alembic.ini version.json ./
COPY shogun/ ./shogun/
COPY migrations/ ./migrations/

RUN python shogun/security_maintenance.py bootstrap --allow-system \
    && python shogun/security_maintenance.py check --node \
    && python -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu "torch>=2.4.0" \
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
