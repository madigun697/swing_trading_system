FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN uv sync --frozen --no-dev

EXPOSE 8401
CMD ["uv", "run", "uvicorn", "swing_trading_system.web.app:app", "--host", "0.0.0.0", "--port", "8401"]
