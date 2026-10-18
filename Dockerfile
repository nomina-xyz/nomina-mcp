FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY server.py icon.png ./
COPY nomina ./nomina
# Read-only service: run as an unprivileged user that owns nothing it can write to.
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin nomina
USER nomina
ENV PORT=8000
EXPOSE 8000
LABEL io.modelcontextprotocol.server.name="io.github.nomina-xyz/nomina-mcp"
# The venv is fully synced at build time; invoke it directly so runtime needs no uv cache.
CMD ["/app/.venv/bin/python", "server.py", "--transport", "streamable-http", "--host", "0.0.0.0"]
