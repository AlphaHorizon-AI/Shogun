FROM python:3.12-slim

LABEL org.opencontainers.image.title="Shogun Installation Telemetry" \
      org.opencontainers.image.vendor="Alpha Horizon" \
      org.opencontainers.image.source="https://github.com/AlphaHorizon-AI/Shogun" \
      org.opencontainers.image.licenses="Shogun AFM Free Use License"

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN groupadd --gid 10002 telemetry \
    && useradd --uid 10002 --gid telemetry --home-dir /app --shell /usr/sbin/nologin telemetry
COPY telemetry_service/requirements.txt ./requirements.txt
COPY shogun ./shogun
COPY telemetry_service ./telemetry_service
RUN pip install --no-cache-dir -r requirements.txt
RUN mkdir -p /app/data && chown -R telemetry:telemetry /app/data
USER telemetry
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health')"]
CMD ["uvicorn", "telemetry_service.app:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log", "--proxy-headers"]
