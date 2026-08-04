FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:0.9.28 /uv /uvx /bin/

WORKDIR /app
ENV PYTHONPATH=/app/src

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project

COPY src/ /app/src