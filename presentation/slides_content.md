# Slide Content — Real Estate Investment Analyzer

---

## SLIDE 1: Title

**Real Estate Investment Analyzer**
Multi-Agent System for UAE Rental Market

Mohamad — inmind.academy, AI & ML Track, Spring 2026

---

## SLIDE 2: The Problem — Why a Plain LLM Fails

**Why can't you just ask ChatGPT these questions?**

- **"Find 2-bed apartments under 50k in Sharjah"** — The LLM has no access to live rental listings. It will hallucinate property names and prices that don't exist.
- **"What are the market trends in Dubai Marina?"** — The LLM's training data is months old. The actual trends are in private PDF market reports it has never seen.
- **"Calculate mortgage for a 1.5M AED property"** — The LLM will guess the math. UAE has specific rates (20% down for expats, 4.5% avg rate) that it doesn't reliably know.
- **"Should I invest in Business Bay?"** — This requires combining live data + market reports + financial calculations + comparable analysis. No single LLM call can do this.

**What's needed:** A system that can search a real database, read real PDFs, do real math, and combine all of it — with an LLM as the reasoning engine, not the data source.

**That's what I built.** Multiple specialized AI agents, each with the right tools, orchestrated by a supervisor that knows who to call for what.

---

## SLIDE 3: Architecture — 5 Services

*(Show architecture diagram — screenshot recommended)*

| Service | What It Does | Framework | Port |
|---------|-------------|-----------|------|
| Agent System A | Supervisor routes to 2 specialists | LangGraph + FastAPI | 8000 |
| Agent System B | Independent property valuation | Google ADK + FastAPI | 8001 |
| MCP Server | Mortgage calculator + tax estimator | fastmcp (SSE transport) | 8002 |
| Qdrant | Vector DB for PDF semantic search | Qdrant (Docker image) | 6333 |
| Frontend | Chat UI with voice + streaming | React + Vite → Nginx | 5173 |

**Key point:** Agent A calls Agent B via HTTP POST — not a Python import. They're independent containers that could be deployed by different teams. Agent A connects to MCP via the real MCP protocol with capability negotiation — not REST.

---

## SLIDE 4: Agent System A — Supervisor + Specialists

**How routing works:**
The supervisor uses `with_structured_output` to produce a `RouteDecision` with the route AND a dynamic thinking status — both in a single LLM call. I used `method="function_calling"` because OpenRouter/Claude doesn't support `response_format` JSON schema.

**Routes:**

| Route | Triggers On | Specialist Tools |
|-------|------------|-----------------|
| `property_analyst` | "Find apartments", "calculate mortgage" | search_properties, search_market_reports, get_area_statistics, web_search, calculate_mortgage (MCP), estimate_property_tax (MCP) |
| `market_researcher` | "Market trends", "should I invest" | search_properties, search_market_reports, get_area_statistics, web_search, call_agent_b (HTTP) |
| `both` | Complex queries needing both | Runs both in parallel via ThreadPoolExecutor |
| `direct` | "Hello", off-topic | No tools — direct LLM response |

Both specialists are ReAct agents (LangGraph `create_react_agent`) — they reason, call tools, observe results, and iterate until they have enough information to answer.

---

## SLIDE 5: Agent System B — Independent Valuation

**Why it exists:** Proves multi-system agent collaboration. Different framework (Google ADK), different container, independent reasoning — returns a structured `AgenticResponse` with confidence score and reasoning chain.

**The pipeline state pattern:**
LLMs are unreliable at passing complex JSON between tool calls. Instead of asking the LLM to serialize step 1's output as input to step 2, each tool writes to a shared `_pipeline_state` dictionary. Steps 3 and 4 take zero arguments — they read directly from previous results.

| Step | Tool | What Happens |
|------|------|-------------|
| 1 | `tool_parse_request` | Validates location, type, beds, budget → stores `ParsedCriteria` |
| 2 | `tool_find_comparables` | CSV filter + Qdrant search → stores `CompFinderResult` |
| 3 | `tool_evaluate_comparables` | LLM scores comps, detects outliers, estimates value → stores `EvaluationResult` |
| 4 | `tool_synthesize_response` | Builds final response with reasoning chain |

**What Agent B returns:** estimated_value, confidence_score (High/Medium/Low based on comp count), reasoning_chain, supporting_comps with relevance scores, adjustments_applied ("Furnished premium +8%").

**Logging:** Each step logs its output — `Step 2: Found 8 comparables | market_context_chunks=3`. If the ADK agent fails, a fallback runs the pipeline directly without LLM orchestration.

---

## SLIDE 6: RAG Pipeline — Two Data Sources, Two Strategies

**CSV Data (rental listings):**
Structured fields — city, type, beds, rent, area, furnishing. I use Pandas filters, NOT vector search. A query for "2-bed under 50k in Sharjah" needs exact filtering. Embedding this data would destroy the structure — vector search might return a 3-bed at 52k because the description is "semantically similar."

**PDF Data (3 market reports → Qdrant):**
Unstructured text about trends, transaction volumes, forecasts. This IS the right use case for RAG.

**Chunking decision:**
- `RecursiveCharacterTextSplitter` at **2000 characters (~512 tokens)** with 200-char overlap
- I originally used 512 characters thinking it meant tokens — that's only ~128 tokens, way too small. Paragraphs got split mid-sentence. After fixing to 2000 chars, chunks capture full paragraphs and retrieval recall improved significantly.
- Separators: `["\n\n", "\n", " ", ""]` — tries paragraph breaks first, then sentences

**Embedding:**
- `text-embedding-3-small` (1536 dims, cosine distance)
- Chose over `text-embedding-3-large` because <2% MRR improvement at 6x cost — not justified for 95 chunks

**Metadata:** Each chunk stores `source` (filename) and `page` (page number) for citation.

---

## SLIDE 7: MCP Server + Voice Interface

**MCP Server:**
Two tools exposed via fastmcp with SSE transport:

| Tool | Inputs | UAE-Specific Logic |
|------|--------|-------------------|
| `calculate_mortgage` | price, down_pct, rate, years | Defaults: 20% down, 4.5% rate, 25yr (UAE expat standard) |
| `estimate_property_tax` | rent, property_value, emirate | Dubai: 5% housing + 0.5% municipality. Abu Dhabi: 3%. Sharjah: 2%. Registration: Dubai 4%, others 2% |

Agent A connects as an MCP client using the `mcp` SDK. The connection goes through SSE with full capability negotiation — the agent discovers available tools at runtime. If I add a third tool to the MCP server, Agent A sees it automatically without code changes.

**Voice Interface:**
- **STT:** Groq Whisper `large-v3-turbo` API — multilingual auto-detection (no hardcoded language). Frontend records via MediaRecorder, sends audio blob to `/transcribe` endpoint.
- **TTS:** Browser Web Speech API — strips markdown before reading, instant playback, zero API cost. Integrated in the message actions component (play/stop per message).

---

## SLIDE 8: Guardrails — Input + Output

**Input Guardrails (run before supervisor):**
- **Layer 1 — Regex (fast, <1ms):** 10+ injection patterns — "ignore your instructions", "ignore previous", "you are now", "DAN mode", ChatML injection (`<|im_start|>`), system prompt extraction attempts. Also checks query length and off-topic detection.
- **Layer 2 — ML (thorough):** DeBERTa-based prompt injection scanner via LLM Guard library (`protectai/deberta-v3-base-prompt-injection`, threshold 0.5). Catches subtle attacks that regex misses.
- **Graceful degradation:** If LLM Guard isn't installed (heavy dependency — torch + transformers), falls back to regex-only. System still works.

**Output Guardrails (run after response generated):**
- **Price hallucination check:** Flags annual rent values outside realistic AED ranges (too low or too high)
- **Empty/short response detection:** Catches agent failures before they reach the user
- **PII scanning:** Regex patterns for sensitive data that shouldn't be in responses

**Integration:** Both are called in the FastAPI endpoint handlers — `validate_input()` before `supervisor.ainvoke()`, `validate_output()` after response extraction. Blocked requests return a clean error message, not a stack trace.

**Iteration limits:** `recursion_limit=25` passed to LangGraph at invocation time — caps total node executions to prevent infinite agent loops.

---

## SLIDE 9: Evaluation Results

**Test set:** 20 questions with ground truth answers and source references, covering property search, market research, mortgage calculations, investment advice, comparisons, and greetings.

**Retrieval metrics (10 PDF-sourced questions):**

| Metric | Score | Meaning |
|--------|-------|---------|
| Precision@5 | 0.640 | 64% of retrieved chunks are relevant |
| Recall@5 | 0.527 | 53% of all relevant chunks found |
| MRR | 0.833 | First relevant chunk usually ranked #1 |

**Generation scores (LLM-as-Judge, 20 questions):**

| Metric | Score (/5) |
|--------|-----------|
| Correctness | 3.05 |
| Faithfulness | 3.50 |
| Relevance | 3.80 |
| Completeness | 3.00 |
| **Overall** | **3.34** |

**Best performers:** Property search queries (5.0/5), mortgage calculations (5.0/5), greetings (5.0/5)
**Weakest:** PDF-specific factual questions requiring exact numbers from reports

---

## SLIDE 10: Configuration Comparisons

**Comparison 1: Top-K Retrieval (K=3 vs K=5)**

| Metric | K=3 | K=5 | Winner |
|--------|-----|-----|--------|
| Precision | 0.667 | 0.640 | K=3 |
| Recall | 0.342 | 0.527 | **K=5** |
| MRR | 0.833 | 0.833 | Tie |

**Why K=5 wins:** Higher recall means less missing context. In RAG, missing context causes hallucination — the LLM invents facts to fill gaps. K=3 is slightly more precise but misses too much.

**Comparison 2: Chunk Size (256 vs 512 tokens)**

| Metric | 256 tokens | 512 tokens | Winner |
|--------|-----------|-----------|--------|
| Precision | 0.580 | 0.640 | **512** |
| Recall | 0.342 | 1.000 | **512** |
| MRR | 0.803 | 0.833 | **512** |

**Why 512 wins:** 256-token chunks split market report paragraphs at sentence boundaries. A paragraph about "Dubai Marina rental yields" gets cut in half — neither half alone answers the question. Recall drops from 1.0 to 0.34. That's 66% of relevant information lost.

---

## SLIDE 11: Failure Analysis

**Failure 1: "Find cheapest apartment in Al Ain" (1.0/5)**
- **What failed:** Data coverage + timeout. Very few Al Ain listings in CSV. Agent B was called for valuation but timed out — not enough comparable properties to analyze.
- **Component:** Inter-service communication
- **Fix:** Add a low-data fast-path — if CSV returns <3 results, skip Agent B and present what we have directly.

**Failure 2: "What are the market trends in Dubai Marina?" (1.5/5)**
- **What failed:** Retrieval. P@5 was only 0.20 for this query — the vector search returned general Dubai market chunks, not Marina-specific ones. Without the right context, the LLM couldn't answer.
- **Component:** Retrieval (vector search too broad)
- **Fix:** Hybrid search (BM25 + vector) would catch the exact keyword "Dubai Marina" that semantic search misses.

**Failure 3: "How many rental contracts registered in Dubai 2024?" (1.75/5)**
- **What failed:** Document parsing. The exact number exists in the PDF but was inside a table that got flattened to plain text during PyMuPDF extraction. The chunk lost its tabular structure.
- **Component:** PDF parsing + retrieval
- **Fix:** Use a table-aware parser (Unstructured.io or Azure Document Intelligence) that preserves table structure as markdown.

---

## SLIDE 12: Docker Design + What I'd Improve

**Docker Compose design:**
- 5 services with dependency ordering: Qdrant starts first (with TCP health check), then MCP + Agent B (depend on Qdrant healthy), then Agent A (depends on all), then Frontend (depends on Agent A)
- Each service has its own Dockerfile (multi-stage Python 3.11-slim builds for backend, Node 20 → Nginx for frontend)
- Auto-ingestion: On startup, Agent A checks Qdrant — if empty, runs the full RAG pipeline automatically. Zero manual steps after `docker compose up`.
- Environment variables injected from `.env` — API keys never hardcoded

**Session management:** In-memory dict with 1-hour TTL. Stale sessions cleaned up periodically.

**Cost tracking:** Token usage estimated per request, accessible via `/costs` endpoint.

**What I'd improve:**
- **Redis for sessions** — survive container restarts
- **Hybrid search** (BM25 + vector) — fixes the Marina retrieval failure
- **Cross-encoder re-ranking** — 10-15% precision improvement
- **Table-aware PDF parsing** — fixes the table extraction failure
- **Streaming from Agent B** — currently blocks until full pipeline completes
- **Fine-tuned BERT classifier** for routing — faster and cheaper than using the LLM

---

*END*
