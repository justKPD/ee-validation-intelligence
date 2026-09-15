FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
COPY . .
RUN uv sync --frozen --no-dev --extra postgres
ENV EE_API_HOST=0.0.0.0 EE_API_PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uv run --no-dev ee-seed --seed ${EE_SEED:-42} && uv run --no-dev ee-api"]
