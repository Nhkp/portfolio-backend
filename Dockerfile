FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
ca-certificates \
curl \
libpq-dev \
build-essential \
&& rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_PYTHON=3.12

COPY ./backend/pyproject.toml ./backend/uv.lock* ./

RUN uv sync --frozen --no-dev

COPY ./backend ./
COPY ./data /app/data/

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
# CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
