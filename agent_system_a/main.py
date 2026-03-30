"""
Agent System A — Main FastAPI Application

Exposes POST /chat endpoint that:
1. Receives user query + session_id
2. Passes to Supervisor agent
3. Supervisor routes to specialist(s)
4. Returns streaming response via SSE
"""

import os
import time
import uuid
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from sse_starlette.sse import EventSourceResponse
import json

import asyncio

from agent_system_a.config import HOST, PORT, GROQ_API_KEY
from agent_system_a.agents.supervisor import supervisor
from agent_system_a.guardrails.input_guardrails import validate_input
from agent_system_a.guardrails.output_guardrails import validate_output
from agent_system_a.tools.rag_tool import get_available_documents
from shared.logging_config import get_logger
from shared.cost_tracker import cost_tracker
from shared.observability import trace_llm_call

logger = get_logger("agent_system_a.api")

# Allowed CORS origins — configurable via env, defaults to localhost for dev
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")


# --- Auto-ingestion on startup ---
# Ensures Qdrant has PDF embeddings without any manual steps after `docker compose up`.

def _auto_ingest():
    """Check if Qdrant collection has data; if not, run the RAG ingestion pipeline.
    Runs in a background thread so it doesn't block the server from accepting requests."""
    from qdrant_client import QdrantClient
    from rag_pipeline.config import QDRANT_HOST, QDRANT_PORT, COLLECTION_NAME

    MAX_RETRIES = 10
    RETRY_DELAY = 3  # seconds — Qdrant may still be starting up

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=10)
            collections = [c.name for c in client.get_collections().collections]

            if COLLECTION_NAME in collections:
                info = client.get_collection(COLLECTION_NAME)
                if info.points_count and info.points_count > 0:
                    logger.info(
                        f"Qdrant collection '{COLLECTION_NAME}' already has "
                        f"{info.points_count} vectors — skipping ingestion"
                    )
                    return

            # Collection missing or empty — run the full pipeline
            logger.info("Qdrant collection empty or missing — starting auto-ingestion...")
            from rag_pipeline.ingest import create_collection, ingest_pdfs
            create_collection()
            ingest_pdfs()
            logger.info("Auto-ingestion complete!")
            return

        except Exception as e:
            logger.warning(
                f"Auto-ingest attempt {attempt}/{MAX_RETRIES} failed: "
                f"{type(e).__name__}: {e}"
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    logger.error("Auto-ingestion failed after all retries — RAG search may be empty")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: kick off auto-ingestion in a background thread on startup."""
    thread = threading.Thread(target=_auto_ingest, daemon=True, name="auto-ingest")
    thread.start()
    yield
    # Shutdown: nothing to clean up — the thread is a daemon

# --- In-memory conversation history (keyed by session_id) ---
# Thread-safe via _sessions_lock; TTL prevents unbounded growth.
_sessions: dict[str, dict] = {}  # {sid: {"messages": [...], "last_active": timestamp}}
_sessions_lock = threading.Lock()
SESSION_TTL_SECONDS = 3600  # 1 hour — evict idle sessions


def _get_session(sid: str) -> list[dict]:
    """Get or create a session's message history (thread-safe)."""
    with _sessions_lock:
        if sid not in _sessions:
            _sessions[sid] = {"messages": [], "last_active": time.time()}
        _sessions[sid]["last_active"] = time.time()
        return _sessions[sid]["messages"]


async def _build_messages_with_doc_context(history: list[dict]) -> list[dict]:
    """Prepend a system message listing available documents so agents always know
    what's in the knowledge base — regardless of session state."""
    # Run sync Qdrant call in a thread to avoid blocking the async event loop
    docs = await asyncio.to_thread(get_available_documents)
    if not docs:
        return list(history)
    doc_list = ", ".join(f'"{d}"' for d in docs)
    context_msg = {
        "role": "system",
        "content": (
            f"The following documents are available in the knowledge base: {doc_list}. "
            f"When the user's query could relate to these documents, use the "
            f"search_market_reports tool to retrieve relevant content from them."
        ),
    }
    return [context_msg] + list(history)


def _cleanup_stale_sessions():
    """Remove sessions that haven't been active within TTL (called periodically)."""
    cutoff = time.time() - SESSION_TTL_SECONDS
    with _sessions_lock:
        stale = [sid for sid, data in _sessions.items() if data["last_active"] < cutoff]
        for sid in stale:
            del _sessions[sid]
        if stale:
            logger.info(f"Cleaned up {len(stale)} stale sessions")


# --- Request/Response models ---

class ChatRequest(BaseModel):
    """Incoming chat request from frontend."""
    query: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Non-streaming response."""
    response: str
    session_id: str


# --- FastAPI app ---

app = FastAPI(
    title="Real Estate Investment Analyzer",
    description="Multi-agent system for UAE rental property analysis",
    lifespan=lifespan,
)

# Allow frontend to connect — restrict origins via CORS_ORIGINS env var
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/chat")
async def chat(request: ChatRequest):
    """Main chat endpoint — sends query to supervisor, returns analysis."""
    trace_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    sid = request.session_id or "default"
    logger.info(f"POST /chat | trace={trace_id} | session={sid} | query='{request.query[:80]}...'")

    # Periodic cleanup of stale sessions (lightweight, non-blocking)
    _cleanup_stale_sessions()

    # ── Input guardrail ──
    input_check = validate_input(request.query)
    if not input_check.is_safe:
        logger.warning(f"Input blocked | trace={trace_id} | session={sid} | reason={input_check.blocked_reason}")
        return ChatResponse(response=input_check.blocked_reason, session_id=sid)

    history = _get_session(sid)
    history.append({"role": "user", "content": input_check.sanitized_query})

    try:
        result = await supervisor.ainvoke(
            {"messages": await _build_messages_with_doc_context(history)},
            config={"recursion_limit": 25},
        )
    except Exception as e:
        logger.error(f"POST /chat failed | trace={trace_id} | session={sid} | error={e}")
        history.pop()  # rollback — keep history clean for the next request
        raise

    # Extract the final response from the last AI message
    ai_messages = [
        msg for msg in result["messages"]
        if hasattr(msg, "type") and msg.type == "ai" and msg.content
    ]
    response_text = ai_messages[-1].content if ai_messages else "No response generated."

    # ── Output guardrail ──
    output_check = validate_output(response_text, original_query=request.query)
    if not output_check.is_safe:
        logger.warning(f"Output blocked | session={sid} | reason={output_check.blocked_reason}")
        response_text = output_check.blocked_reason
    else:
        response_text = output_check.cleaned_response
        # Append warnings as a footnote if any
        if output_check.warnings:
            logger.info(f"Output warnings | session={sid} | warnings={output_check.warnings}")

    history.append({"role": "assistant", "content": response_text})

    duration = round(time.time() - start_time, 2)

    # Estimate token usage for cost tracking (rough: 1 token ~ 4 chars)
    est_input = len(request.query) // 4 + 500  # query + system prompt overhead
    est_output = len(response_text) // 4
    trace_llm_call("openrouter/auto", input_tokens=est_input, output_tokens=est_output, duration_ms=duration * 1000)

    logger.info(f"POST /chat done | trace={trace_id} | session={sid} | duration={duration}s | response_len={len(response_text)}")

    return ChatResponse(
        response=response_text,
        session_id=sid,
    )


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Streaming chat endpoint — uses astream(updates) for node-level status,
    then streams the finished response in small chunks via SSE.

    We use stream_mode="updates" (NOT astream_events) so we get one update per
    graph node without the noise of every internal ReAct token.  This lets us
    emit a route-specific thinking status after the router decides, while the
    specialist agent works.
    """
    trace_id = str(uuid.uuid4())[:8]
    stream_start = time.time()
    sid = request.session_id or "default"
    logger.info(f"POST /chat/stream | trace={trace_id} | session={sid} | query='{request.query[:80]}...'")

    # ── Input guardrail ──
    input_check = validate_input(request.query)
    if not input_check.is_safe:
        logger.warning(f"Input blocked (stream) | trace={trace_id} | session={sid} | reason={input_check.blocked_reason}")
        async def blocked_generator():
            yield {"data": json.dumps({"type": "error", "message": input_check.blocked_reason})}
            yield {"data": "[DONE]"}
        return EventSourceResponse(blocked_generator())

    async def event_generator():
        # Periodic cleanup of stale sessions
        _cleanup_stale_sessions()
        history = _get_session(sid)
        history.append({"role": "user", "content": input_check.sanitized_query})

        # Immediate status — user sees this while the router LLM runs (~1s)
        yield {"data": json.dumps({"type": "status", "message": "Thinking..."})}

        try:
            result_messages = []
            messages_with_ctx = await _build_messages_with_doc_context(history)
            async for update in supervisor.astream(
                {"messages": messages_with_ctx},
                stream_mode="updates",
                config={"recursion_limit": 25},
            ):
                for node_name, node_output in update.items():
                    # After router completes: emit the LLM-generated status summary
                    if node_name == "router" and isinstance(node_output, dict):
                        status = node_output.get("status", "")
                        if status:
                            yield {"data": json.dumps({"type": "status", "message": status})}

                    # Capture messages from specialist nodes (last one wins)
                    if isinstance(node_output, dict) and "messages" in node_output:
                        result_messages = node_output["messages"]
        except Exception as e:
            logger.error(f"Stream processing failed | session={sid} | error={type(e).__name__}: {e}")
            history.pop()  # rollback — keep history clean for the next request
            yield {"data": json.dumps({"type": "error", "message": "Agent processing failed. Please try again."})}
            yield {"data": "[DONE]"}
            return

        # Extract the final AI response
        ai_messages = [
            msg for msg in result_messages
            if hasattr(msg, "type") and msg.type == "ai" and msg.content
        ]
        response_text = ai_messages[-1].content if ai_messages else "No response generated."

        # ── Output guardrail ──
        output_check = validate_output(response_text, original_query=request.query)
        if not output_check.is_safe:
            logger.warning(f"Output blocked (stream) | session={sid} | reason={output_check.blocked_reason}")
            response_text = output_check.blocked_reason
        else:
            response_text = output_check.cleaned_response
            if output_check.warnings:
                logger.info(f"Output warnings (stream) | session={sid} | warnings={output_check.warnings}")

        duration = round(time.time() - stream_start, 2)
        logger.info(f"Stream response ready | trace={trace_id} | session={sid} | duration={duration}s | length={len(response_text)} chars")

        history.append({"role": "assistant", "content": response_text})

        # Clear the thinking status before tokens start flowing
        yield {"data": json.dumps({"type": "status", "message": ""})}

        # Stream the response in small chunks with delay for a visible typing effect
        CHUNK_SIZE = 4
        for i in range(0, len(response_text), CHUNK_SIZE):
            chunk = response_text[i : i + CHUNK_SIZE]
            yield {"data": json.dumps({"token": chunk})}
            await asyncio.sleep(0.02)  # 20ms between chunks — visible typing cadence

        yield {"data": "[DONE]"}

    return EventSourceResponse(event_generator())


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...), language: str = None):
    """Speech-to-text via Groq Whisper API.
    Frontend sends recorded audio blob, we forward to Groq and return the text.

    Args:
        language: Optional ISO 639-1 code (e.g., "en", "ar", "fr").
                  If omitted, Whisper auto-detects the language.
    """
    if not GROQ_API_KEY:
        return {"text": "", "error": "GROQ_API_KEY not configured"}

    from openai import OpenAI
    groq_client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")

    audio_bytes = await file.read()
    filename = file.filename or "recording.webm"

    try:
        # Build kwargs — omit language to let Whisper auto-detect (multilingual support)
        transcribe_kwargs = {
            "model": "whisper-large-v3-turbo",
            "file": (filename, audio_bytes),
            "response_format": "json",
        }
        if language:
            transcribe_kwargs["language"] = language

        transcription = groq_client.audio.transcriptions.create(**transcribe_kwargs)

        # Track Groq API usage
        trace_llm_call("whisper-large-v3-turbo", input_tokens=0, output_tokens=0)

        detected = f" | lang={language or 'auto'}"
        logger.info(f"Transcription complete | {len(audio_bytes)} bytes{detected} | text='{transcription.text[:80]}...'")
        return {"text": transcription.text}
    except Exception as e:
        logger.error(f"Transcription failed: {type(e).__name__}: {e}")
        return {"text": "", "error": str(e)}


@app.post("/ingest")
async def ingest_pdf(file: UploadFile = File(...), session_id: str = None):
    """Upload a PDF and ingest it into the Qdrant vector store.
    If session_id is provided, injects a system message so the agent knows about the upload."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return {"success": False, "error": "Only PDF files are accepted"}

    import tempfile
    import fitz
    from rag_pipeline.config import QDRANT_HOST, QDRANT_PORT, COLLECTION_NAME
    from rag_pipeline.chunker import get_text_splitter
    from rag_pipeline.embedder import embed_texts
    from rag_pipeline.ingest import create_collection, _embed_and_store
    from qdrant_client import QdrantClient

    try:
        pdf_bytes = await file.read()

        # Save the PDF to data/Documents/ so it persists across restarts
        from rag_pipeline.config import DOCS_DIR
        os.makedirs(DOCS_DIR, exist_ok=True)
        saved_path = os.path.join(DOCS_DIR, file.filename)
        with open(saved_path, "wb") as f:
            f.write(pdf_bytes)

        # Extract text and chunk directly from the saved file
        doc = fitz.open(saved_path)
        splitter = get_text_splitter()
        chunks, metas = [], []

        for page_num, page in enumerate(doc, start=1):
            page_text = page.get_text()
            if not page_text.strip():
                continue
            for chunk in splitter.split_text(page_text):
                chunks.append(chunk)
                metas.append({"source": file.filename, "page": page_num})

        doc.close()

        if not chunks:
            return {"success": False, "error": "No text could be extracted from the PDF"}

        # Ensure collection exists
        create_collection()

        # Delete previous chunks from this file to avoid duplicates on re-upload
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        qdrant_client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=Filter(
                must=[FieldCondition(key="source", match=MatchValue(value=file.filename))]
            ),
        )

        _embed_and_store(chunks, metas)

        logger.info(f"POST /ingest | file={file.filename} | {len(chunks)} chunks ingested")
        return {"success": True, "filename": file.filename, "chunks_ingested": len(chunks)}

    except Exception as e:
        logger.error(f"POST /ingest failed | file={file.filename} | error={type(e).__name__}: {e}")
        return {"success": False, "error": str(e)}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "agent_system_a"}


@app.get("/costs")
async def costs():
    """Return cumulative API cost and token usage summary."""
    return cost_tracker.get_summary()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
