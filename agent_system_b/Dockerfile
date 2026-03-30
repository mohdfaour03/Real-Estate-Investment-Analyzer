# ── Agent System B (Google ADK Independent Valuation) ──
# Multi-stage build: deps first (cached), then app code

# Stage 1 — Install Python dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

COPY agent_system_b/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2 — Lean runtime image
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy only the modules this service actually imports:
#   - agent_system_b/  (this service)
#   - rag_pipeline/    (shared RAG config for Qdrant access)
#   - shared/          (shared logging)
#   - data/            (CSV dataset for comp finder)
COPY agent_system_b/ ./agent_system_b/
COPY rag_pipeline/   ./rag_pipeline/
COPY shared/         ./shared/
COPY data/           ./data/

EXPOSE 8001

# Healthcheck — hit /health every 30s
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')" || exit 1

CMD ["uvicorn", "agent_system_b.main:app", "--host", "0.0.0.0", "--port", "8001"]
