# ── MCP Server (Financial Tools — Mortgage & Tax) ──
# Multi-stage build: deps first (cached), then app code

# Stage 1 — Install Python dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

COPY mcp_server/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2 — Lean runtime image
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy only the MCP server module (no data or RAG needed)
COPY mcp_server/ ./mcp_server/
COPY shared/     ./shared/

EXPOSE 8002

# Healthcheck — MCP uses SSE, not REST; check if the process is alive
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/sse')" || exit 1

CMD ["python", "-m", "mcp_server.main"]
