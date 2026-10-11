FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.30 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY . .
RUN useradd --system --uid 10001 app
USER app
ENV PATH="/app/.venv/bin:$PATH"
# API доступен только из внутренней сети compose, поэтому X-Forwarded-* от nginx можно доверять
CMD ["sh", "-c", "python -m scripts.init_db && python -m scripts.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers --forwarded-allow-ips='*'"]
