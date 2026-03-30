# ── Agent System A (LangGraph Supervisor + Specialists) ──
# Multi-stage build: deps first (cached), then app code

# Stage 1 — Install Python dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

# Install only what this service needs from requirements.txt
COPY agent_system_a/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2 — Lean runtime image
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy only the modules this service actually imports:
#   - agent_system_a/  (this service)
#   - rag_pipeline/    (shared RAG config)
#   - shared/          (shared logging)
#   - data/            (CSV dataset for pandas queries)
COPY agent_system_a/ ./agent_system_a/
COPY rag_pipeline/   ./rag_pipeline/
COPY shared/         ./shared/
COPY data/           ./data/

EXPOSE 8000

# Healthcheck — hit /health every 30s, mark unhealthy after 3 failures
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run with uvicorn (0.0.0.0 so Docker can route traffic in)
CMD ["uvicorn", "agent_system_a.main:app", "--host", "0.0.0.0", "--port", "8000"]
