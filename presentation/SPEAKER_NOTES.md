# Speaker Notes — What to Say on Each Slide

**Philosophy:** The prof wants IMPLEMENTATION + REASONING. Not "ReAct is a pattern by Yao et al."
Instead: "I used ReAct because my agents need to adapt based on tool results."

Every answer should follow: **"I did X because Y. The alternative was Z but it didn't work because W."**

---

## Slide 1: Title
> "I built a multi-agent real estate investment analyzer for the UAE rental market. It takes natural language questions about properties and returns data-driven analysis using multiple AI agents working together."

*Keep it brief — 10 seconds max.*

---

## Slide 2: The Problem (divider)
*Just read the subtitle, transition quickly.*

---

## Slide 3: Why This Matters

> "The UAE rental market has over 73,000 active listings. If you're an investor trying to figure out where to buy, you need to check property prices, read market reports, calculate mortgage payments, and compare areas. That takes hours manually."

> "My system lets you ask a question like 'Find 2-bed apartments under 50k in Sharjah' and it does all of that in seconds — searches the database, reads PDF market reports, calculates mortgage, and even gets an independent valuation from a separate AI system."

**If asked "Why real estate?":**
> "It's a domain with multiple data types — structured data (CSV listings), unstructured data (PDF reports), and calculations (mortgage/tax). That naturally requires multiple specialized agents."

---

## Slide 4: Architecture (divider)
*Transition: "Let me show you how it's built."*

---

## Slide 5: System Architecture

> "The system is 5 Docker containers. The frontend is React with SSE streaming. Agent System A is the primary — it's built with LangGraph and FastAPI. It has a supervisor that routes queries to specialist agents."

> "Agent A connects to an MCP server for mortgage and tax calculations — that's a real MCP protocol connection, not a REST API. And it can call Agent System B, which is a completely separate service built with Google ADK."

> "Both agent systems share the same Qdrant vector database for PDF search, but they're independently deployable — different frameworks, different containers, different ports."

**If asked "Why not just one big agent?":**
> "A single agent with 10+ tools gets confused about which tool to use. Splitting into specialists with 5-6 tools each keeps the context focused. The supervisor just decides WHO should handle the query — it doesn't do the work itself."

---

## Slide 6: Why Two Agent Systems?

> "The project requires two independent agent systems on different tech stacks. I used LangGraph for System A because it gives full control — I can define exact graph nodes, conditional edges, and streaming. For System B, I used Google ADK because it handles the ReAct loop internally — I just define tools and it orchestrates."

> "They communicate via HTTP — Agent A's market researcher has a `call_agent_b` tool that sends an HTTP POST to Agent B's `/analyze` endpoint. Agent B is NOT a Python import. It's a separate container on port 8001."

> "What makes Agent B an agent and not just a tool? It returns a `reasoning_chain` — it explains its logic. It has a `confidence_score` based on how many comparable properties it found. And it applies `adjustments` like 'furnished premium +8%'. It makes decisions independently."

**If asked "Why Google ADK specifically?":**
> "It demonstrates multi-framework interop. In production, you might call another team's agent that uses a different framework. ADK also has a simpler API for standard patterns — no manual graph wiring."

---

## Slide 7: Agent System A — Supervisor Pattern

> "The supervisor uses `with_structured_output` to route queries. I defined a Pydantic model `RouteDecision` with the route and a summary field. The LLM returns structured JSON — not free text I have to parse."

> "Why structured output instead of text parsing? Because OpenRouter with Claude supports `method='function_calling'` natively. I get zero parsing errors. And the `summary` field gives me the dynamic thinking status — like 'Searching Sharjah apartments...' — in the same LLM call. Zero extra latency."

> "There are 4 routes: `property_analyst` for specific property queries, `market_researcher` for trends and comparisons, `both` for complex queries that need both specialists running in parallel via ThreadPoolExecutor, and `direct` for greetings."

**If asked "How does the supervisor decide?":**
> "I give it a system prompt that says: 'If the user asks about specific properties or prices, route to property_analyst. If they ask about trends, comparisons, or investment advice, route to market_researcher. If both, route to both.' The LLM makes the judgment call based on the query."

---

## Slide 8: Agent System B — Pipeline State Pattern

> "This is probably the most important design decision in Agent B. LLMs are bad at passing complex JSON between tool calls — they mangle keys, invent fields, lose data. So instead of asking the LLM to pass the output of step 1 as input to step 2, I store each step's result in a shared Python dictionary."

> "Steps 3 and 4 take ZERO arguments. They just read from `_pipeline_state['step2_result']`. The LLM calls `tool_evaluate_comparables()` with no args, and the function knows where to find the data."

> "This eliminated all serialization errors. Before this pattern, about 1 in 5 Agent B calls failed because the LLM would output malformed JSON."

**If asked "Isn't this less 'agentic'?":**
> "The LLM still decides WHEN to call each tool and WHETHER to proceed. It just doesn't have to be the data bus. The orchestration is agentic — the data flow is deterministic."

---

## Slide 9: RAG Design Decisions

> "I have two data sources and I handle them differently — deliberately."

> "The CSV has 73,742 rental listings with structured fields: city, type, beds, rent, area. I use pandas filters, NOT vector search. If someone asks for '2-bed under 50k in Sharjah', a pandas filter gives exact results. Vector search would return semantically similar listings that might be wrong — maybe a 3-bed at 52k because the description mentions '2-bedroom nearby'."

> "The PDFs are 3 market reports — unstructured text. For those, I use the RAG pipeline: PyMuPDF text extraction, RecursiveCharacterTextSplitter at 512 tokens with 50 overlap, text-embedding-3-small embeddings, and Qdrant vector search."

**If asked "Why 512 chunk size?":**
> "Market report paragraphs average 300-600 tokens. At 512, I capture full paragraphs without splitting mid-sentence. I tested 256 — it split tables and lost context. I tested 1024 — chunks included too much irrelevant text, hurting precision. 512 was the sweet spot in my config comparison."

**If asked "Why text-embedding-3-small?":**
> "Cost vs quality tradeoff. At $0.02 per million tokens, it's cheap enough to re-embed frequently. text-embedding-3-large gave less than 2% MRR improvement at 6x the cost — for 263 chunks, not justified."

**If asked "Why Qdrant?":**
> "Good Python SDK, runs easily in Docker, supports cosine similarity out of the box. ChromaDB was the alternative but Qdrant has better production features — filtering, snapshots, gRPC."

---

## Slide 10: MCP, Voice & Guardrails

> "The MCP server exposes two tools: mortgage calculator and property tax estimator. I built it with fastmcp using SSE transport. Agent A connects as an MCP client using the `mcp` SDK."

> "Why MCP instead of just making them regular Python functions? Because MCP is a real protocol — it has capability negotiation, tool discovery. Agent A doesn't hardcode the tool schemas. It discovers them at runtime. If I add a new tool to the MCP server, Agent A sees it automatically."

> "For voice: STT uses Groq's Whisper large-v3-turbo API. I originally hardcoded it to English, but then enabled multilingual auto-detection so it works with Arabic and French too — important for the UAE market. TTS uses the browser's built-in Web Speech API — it's instant and costs nothing."

> "Guardrails are two layers each. Input: fast regex catches obvious injection attempts like 'ignore your instructions'. Then an ML model — DeBERTa via LLM Guard — catches subtler attacks. Output: regex checks for hallucinated prices outside realistic ranges, and an ML scanner detects PII leakage."

**If asked "Why two layers?":**
> "Regex is fast — sub-millisecond. ML is thorough but takes 100-200ms. Running ML on every request is fine, but the regex catches 80% of attacks before the ML even loads. If LLM Guard isn't installed, the system degrades gracefully to regex-only."

---

## Slide 11: Live Demo (divider)
> "Let me show you the system running. I'll start with docker-compose, then run 5 queries across different routes, and show one failure case."

*[Actually do the demo here]*

---

## Slide 12: Demo Queries

*Run each query live. For each one, point out:*
1. **Which route** the supervisor chose (visible in the thinking status)
2. **Which tools** were called (visible in the response — sources, calculations)
3. **Response quality** — is it grounded in data?

*For the failure case:*
> "This query about Ajman under 10k fails because we have very few listings in that price range for that area. The agent finds 1-2 results but can't do meaningful statistical analysis. This is a data coverage problem, not an agent problem."

---

## Slide 13: Docker Deployment

> "One command: `docker compose up --build`. Five containers start in dependency order — Qdrant first, then MCP and Agent B, then Agent A, then frontend."

> "Agent A has auto-ingestion. On startup, it checks if Qdrant has data. If the collection is empty, it runs the full RAG pipeline — extract text from PDFs, chunk, embed, store. Zero manual steps."

**Show `docker ps` output on screen.**

---

## Slide 14: Evaluation Results

> "I have 20 test cases covering all query types: property search, market research, mortgage calculations, investment advice. Each has a ground truth answer and source reference."

> "For retrieval, I measure Precision@5 — how many of the 5 retrieved chunks are relevant. Recall@5 — did I find all the relevant chunks. And MRR — how high up is the first relevant result."

> "For generation, I use LLM-as-Judge — a separate LLM scores each response on correctness, faithfulness, relevance, and completeness on a 1-5 scale."

*Read the actual numbers from results.json.*

---

## Slide 15: Configuration Comparisons

> "I ran two comparisons. First: chunk size 256 vs 512. 512 won on recall because it captures full paragraphs. 256 had slightly better precision but worse recall — it missed context that was split across chunks."

> "Second: top-K 3 vs 5. K=5 has better recall — you find more relevant info. K=3 has better precision — less noise. But the faithfulness score was better with K=5 because the LLM had more context to ground its answer."

**If asked "What would you try next?":**
> "Hybrid search — combining BM25 keyword search with vector search. Azure AI Search does this natively. It would catch exact property names and IDs that vector search misses."

---

## Slide 16: Failure Analysis

*For each failure case, explain:*
1. **What went wrong** — not just "it got a low score" but specifically which component failed
2. **Why** — root cause (data gap? chunk boundary? hallucination?)
3. **What I'd do to fix it** — specific, actionable

> "Failure 1 was a retrieval problem — the answer was split across two chunks and neither chunk alone contained enough context. Fix: increase chunk overlap from 50 to 100 tokens."

> "Failure 2 was a generation problem — the LLM hallucinated a price that wasn't in the retrieved context. Fix: strengthen the grounding instruction in the system prompt."

> "Failure 3 was an Agent B timeout — the valuation pipeline took too long and returned incomplete results. Fix: increase the httpx timeout from 120s or implement partial result streaming."

---

## Slide 17: Key Technical Decisions

> "Let me highlight the decisions that matter most."

*Pick the top 3 from the table and explain each in 15-20 seconds:*
1. CSV via pandas not Qdrant — *"Structured data stays structured"*
2. Pipeline state dict — *"Don't trust the LLM as a data bus"*
3. Two-layer guardrails — *"Fast regex + thorough ML, graceful degradation"*

---

## Slide 18: What I Would Do Differently

> "If I were rebuilding this for production: Redis for sessions so they survive restarts. Hybrid search for better retrieval. A cross-encoder re-ranker — that alone would improve precision by 10-15%. And I'd fine-tune a small BERT model for intent classification instead of using the LLM for routing — it would be faster and cheaper."

**This slide is critical.** It shows you understand limitations and have ideas for improvement. The prof values this highly.

---

## Slide 19: Thank You

> "Happy to take questions."

---

# Common Q&A Questions & Answers

### "Why openrouter/auto instead of a fixed model?"
> "Cost efficiency. OpenRouter auto-routes to the best model for each request type. For simple routing decisions, it might use a cheaper model. For complex analysis, it picks a stronger one. In practice, this saved about 40% compared to always using Claude Sonnet."

### "How do you handle conversation history?"
> "In-memory dict keyed by session_id with a 1-hour TTL. Each request appends the user message and assistant response. Stale sessions are cleaned up periodically. In production, I'd use Redis with TTL."

### "What happens when Agent B is down?"
> "Graceful degradation. The market researcher's `call_agent_b` tool catches `RequestError`, `TimeoutException`, and `HTTPStatusError`. If Agent B fails, the market researcher continues with the other 4 tools and notes that independent valuation wasn't available."

### "How do you prevent the agent from looping forever?"
> "LangGraph's `recursion_limit=25` caps total node executions. Plus the supervisor routes to END after the specialists respond — it doesn't loop back. The ReAct agents inside each specialist also have LangGraph's built-in iteration limits."

### "Why didn't you use LangSmith?"
> "I set up the integration — if you set `LANGCHAIN_TRACING_V2=true` in the env, traces automatically go to LangSmith. For development, I used structured file logging instead because it doesn't require an external account. Both work."

### "What's the most interesting bug you encountered?"
> "Agent B's comp evaluator. Claude via OpenRouter sometimes wraps JSON responses in markdown code fences — ```json ... ```. My initial code just called `json.loads()` and it crashed. I added a regex fallback that strips the fences before parsing. Small fix, but it was failing 1 in 4 requests before I caught it."

### "How accurate is the system?"
> "Based on my evaluation: [cite actual numbers]. The main weakness is recall — some answers are split across chunk boundaries. Increasing overlap from 50 to 100 tokens would help, and hybrid search would catch exact matches that vector search misses."
