FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY server.py ./
COPY nomina ./nomina
ENV PORT=8000
EXPOSE 8000
LABEL io.modelcontextprotocol.server.name="io.github.nomina-xyz/nomina-mcp"
CMD ["uv", "run", "--frozen", "--no-dev", "--no-sync", "server.py", "--transport", "streamable-http", "--host", "0.0.0.0"]
