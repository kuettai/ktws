FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app.py server.py ./
COPY lib ./lib
COPY tools ./tools
COPY context ./context
ENV MCP_TRANSPORT=http PORT=8000 PYTHONUNBUFFERED=1
EXPOSE 8000
USER nobody
CMD [".venv/bin/python", "server.py"]
