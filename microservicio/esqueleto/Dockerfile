FROM python:3.11-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11-slim
COPY --from=builder /install /usr/local
RUN useradd -r -s /bin/false appuser
WORKDIR /app
COPY app/ app/
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .
USER appuser
EXPOSE {{SERVICE_PORT}}
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:{{SERVICE_PORT}}/api/v1/health/live')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "{{SERVICE_PORT}}"]
