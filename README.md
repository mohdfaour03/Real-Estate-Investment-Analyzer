# Real Estate Investment Analyzer

Multi-agent AI system for analyzing the UAE rental market. You ask questions in plain English, and specialized agents search through 73,742 rental listings, PDF market reports, and live web data to give you investment-grade analysis.

Built as a final project for inmind.academy (AI & ML Track, Spring 2026).

---

## What it does

You type something like:
- *"Find me 2-bed apartments under 50k in Sharjah"*
- *"Compare Dubai Marina vs JBR for rental yield"*
- *"Should I invest in Business Bay?"*

The system figures out which agents to involve, runs them (sometimes in parallel), and streams back a markdown-formatted response in real time. It can also do mortgage math, estimate property taxes, get a second opinion from an independent valuation agent, and search the web for current market news.

You can also upload your own PDFs -- they get chunked, embedded, and stored in Qdrant automatically so the agents can reference them in future answers.

---

## How it's structured

There are 5 services, all orchestrated via Docker Compose:

**Qdrant** (port 6333) -- vector database holding 263 chunks from 3 PDF market reports. Both agent systems query it for semantic search.

**Agent System A** (port 8000) -- the main brain. Built with LangGraph and FastAPI. A supervisor agent looks at each query and routes it to the right specialist:
- *Property Analyst* has 6 tools: property search (pandas on 73K CSV rows), market report search (Qdrant), area stats, web search, mortgage calculator, and tax estimator.
- *Market Researcher* has 5 tools: same data tools plus the ability to call Agent B for an independent valuation.
- For complex queries like "should I invest in X?", both run in parallel and the supervisor synthesizes their outputs.

**Agent System B** (port 8001) -- a separate microservice built with Google ADK (not LangGraph, intentionally different). It runs a 4-step pipeline: parse the request, find comparable properties, score them with an LLM, and synthesize a final valuation with confidence level and reasoning chain. The whole point is to demonstrate multi-framework agent collaboration.

**MCP Server** (port 8002) -- serves mortgage and property tax calculation tools over the Model Context Protocol (SSE transport). Agent A discovers and calls these tools at runtime through capability negotiation, not hardcoded REST calls.

**Frontend** (port 5173) -- React + Vite chat UI served through Nginx. Dark theme, SSE streaming with live thinking status, PDF upload, voice input via Groq Whisper. Nginx also reverse-proxies all API calls to Agent A so nothing hits localhost directly.

---

## Running it

You need Docker, an OpenRouter API key ([openrouter.ai/keys](https://openrouter.ai/keys)), and optionally a Groq key for voice input.

```bash
git clone https://github.com/<your-username>/Agentic_System.git
cd Agentic_System
cp .env.example .env
# add your API keys to .env
docker compose up --build -d
```

First startup takes a couple minutes (building images, ingesting PDFs into Qdrant). After that, open `http://localhost:5173`.

To check everything is healthy:
```bash
docker compose ps
```

---

## The data

**73,742 UAE rental listings** in a CSV file, queried with pandas. I deliberately didn't embed these in Qdrant -- tabular data with structured fields (city, beds, rent, sqft) needs exact filtering, not semantic similarity. A vector search for "2-bed under 50k in Sharjah" would return semantically similar but potentially wrong results.

**3 PDF market reports** (DLD, CBRE, Knight Frank) chunked into 263 pieces, embedded with `text-embedding-3-small` (1536 dimensions), stored in Qdrant with cosine distance. The chunking is 2000 characters with 200-char overlap -- big enough to keep full paragraphs intact.

Users can also **upload their own PDFs** through the chat UI. The system extracts text, chunks it, embeds it, and upserts to Qdrant. If you re-upload the same file, it deletes the old chunks first to avoid duplicates. On every request, the system queries Qdrant for all available document names and tells the agents about them, so you don't have to explicitly say "look at the file I uploaded."

---

## API endpoints

Agent A exposes these through FastAPI:

- `POST /chat/stream` -- SSE streaming. Sends status updates while agents work, then streams the response in small chunks. This is what the frontend uses.
- `POST /chat` -- same thing but returns the full response at once.
- `POST /ingest` -- upload a PDF, get it chunked and embedded into Qdrant.
- `POST /transcribe` -- send audio, get text back (Groq Whisper, supports Arabic/English/French).
- `GET /health` and `GET /costs` -- health check and token usage tracking.

Agent B has `POST /analyze` (takes property criteria, returns valuation) and `GET /health`.

---

## Some design choices worth explaining

**Pipeline state dict in Agent B.** I tried having the LLM pass complex JSON between tool calls and it kept mangling the data. So steps 3 and 4 of the pipeline take zero arguments -- they just read from a shared dictionary that previous steps wrote to. Fixed about 20% of Agent B failures.

**Structured output via function calling.** OpenRouter with Claude doesn't support `response_format` JSON schema, so I use `with_structured_output(method="function_calling")` instead. Works perfectly and I get the routing decision + a thinking status message in a single call.

**Two-layer guardrails.** First layer is regex (runs in under 1ms, catches the obvious stuff). Second layer is a DeBERTa model via LLM Guard for subtle prompt injection. If LLM Guard isn't installed, it falls back to regex-only without crashing.

**Nginx reverse proxy.** The frontend doesn't call `localhost:8000` directly -- everything goes through Nginx. This avoids IPv6/IPv4 issues on Windows and is how you'd do it in production anyway.

---

## What's not perfect

- Sessions are in-memory, so they don't survive restarts. You'd want Redis in production.
- No hybrid search -- pure vector retrieval. Adding BM25 would help with exact name/ID lookups.
- Agent B's response isn't streamed, so there's a noticeable wait while its 4-step pipeline runs.
- Cost tracking is approximate (estimates tokens from string length rather than reading API metadata).
- Agents respond in English even if you ask in Arabic -- Whisper handles multilingual input but the prompts are English-only.

---

## Tech stack

| | What | Why |
|-|------|-----|
| LLM | OpenRouter | Routes to different models, has a free tier |
| Embeddings | text-embedding-3-small | Cheap, fast, 1536-dim, good enough for 263 chunks |
| Agent framework A | LangGraph | Streaming, conditional routing, industry standard |
| Agent framework B | Google ADK | Deliberately different -- shows multi-framework interop |
| Vector DB | Qdrant | Fast, good SDK, easy Docker setup |
| Data queries | Pandas | Exact filters on structured CSV data |
| Tool protocol | MCP (fastmcp + mcp SDK) | Real protocol with tool discovery, not REST wrappers |
| API | FastAPI + sse-starlette | Async, SSE streaming, auto-docs |
| Frontend | React + Vite + Nginx | Fast builds, reverse proxy |
| Voice | Groq Whisper | Free, fast, multilingual |
| Guardrails | LLM Guard + regex | Two layers, graceful fallback |

---

## Project structure

```
Agentic_System/
├── agent_system_a/          # LangGraph supervisor + Property Analyst + Market Researcher
│   ├── agents/              # supervisor.py, property_analyst.py, market_researcher.py
│   ├── guardrails/          # input + output validation (regex + ML)
│   ├── tools/               # RAG tools, MCP client, web search
│   ├── main.py              # FastAPI app
│   └── Dockerfile
├── agent_system_b/          # Google ADK valuation agent
│   ├── pipeline/            # parse -> find -> evaluate -> synthesize
│   ├── main.py
│   └── Dockerfile
├── mcp_server/              # Mortgage & tax calculators (MCP protocol)
│   ├── tools/
│   ├── main.py
│   └── Dockerfile
├── rag_pipeline/            # PDF -> chunks -> embeddings -> Qdrant
├── shared/                  # Logging, cost tracking, observability
├── frontend/                # React chat UI + Nginx config
│   └── Dockerfile
├── evaluation/              # 20 test cases, retrieval metrics, RAGAS
├── data/                    # CSV (73K listings) + PDF market reports
├── presentation/            # Slides + speaker notes
├── docker-compose.yml       # All 5 services
├── .env.example             # Environment template
└── requirements.txt
```

---

*Built by Mohamad -- inmind.academy, Spring 2026*
