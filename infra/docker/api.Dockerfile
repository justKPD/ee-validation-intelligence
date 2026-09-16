FROM python:3.12-slim
# uv version matches the one that wrote uv.lock, so `--frozen` accepts the lockfile
COPY --from=ghcr.io/astral-sh/uv:0.12.15 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 UV_NO_CACHE=1 PYTHONUNBUFFERED=1
COPY . .
RUN uv sync --frozen --no-dev --extra postgres
ENV EE_API_HOST=0.0.0.0 EE_API_PORT=8000 PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=90s --retries=12 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"
# migrate + (re)seed authoritative data from seed 42, then serve; agentic tables are preserved across restarts
CMD ["sh", "-c", "ee-seed --seed ${EE_SEED:-42} && ee-api"]
