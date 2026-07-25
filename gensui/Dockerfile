# ── Stage 1: Build Admin UI ──────────────────────────────────
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend
COPY gensui/frontend/package*.json ./
RUN npm ci --silent
COPY gensui/frontend/ ./
RUN npm run build

# ── Stage 2: Python Runtime ─────────────────────────────────
FROM python:3.12-slim

LABEL maintainer="AlphaHorizon AI"
LABEL description="Gensui — Central Command & Security Control Plane for Shogun"

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (better layer caching)
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Copy application code
COPY gensui/ ./gensui/
COPY gensui/.env.example ./.env.example
COPY gensui/docker-entrypoint.sh /usr/local/bin/gensui-entrypoint

# Copy built frontend from stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Create only the writable runtime directories and drop root privileges.
# Application code remains root-owned and read-only to the runtime user.
RUN groupadd --gid 1000 gensui \
    && useradd --uid 1000 --gid gensui --shell /bin/bash --create-home gensui \
    && mkdir -p /app/data /app/logs \
    && chmod 0755 /usr/local/bin/gensui-entrypoint \
    && chown -R gensui:gensui /app/data /app/logs
USER gensui

# Expose port
EXPOSE 8787

# Data volume for persistent storage
VOLUME /app/data

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8787/api/gensui/health || exit 1

# Default env setup
ENV GENSUI_SERVER_HOST=0.0.0.0
ENV GENSUI_SERVER_PORT=8787
ENV GENSUI_DATABASE_URL=sqlite+aiosqlite:///./data/gensui.db
ENV GENSUI_DATA_PATH=/app/data
ENV GENSUI_LOG_PATH=/app/logs
ENV GENSUI_FRONTEND_DIST=/app/frontend/dist

# Run
ENTRYPOINT ["gensui-entrypoint"]
CMD ["python", "-m", "gensui"]
