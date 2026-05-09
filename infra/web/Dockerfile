FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8.15 /uv /uvx /bin/

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/usr/local

COPY . .
RUN uv sync --no-dev

EXPOSE 8401

CMD ["uv", "run", "uvicorn", "swing_trading_system.web.app:app", "--host", "0.0.0.0", "--port", "8401"]
