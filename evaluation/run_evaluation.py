"""
Evaluation Script — Retrieval metrics + LLM-as-Judge generation scoring.

Aligned with Session 11 slides:
  - Retrieval: Precision@K, Recall@K, MRR (slides 27-28)
  - Generation: LLM-as-Judge on Correctness, Faithfulness, Relevance, Completeness (slide 36)
  - Summary table + failure case analysis (slide 42)

Usage:
    python -m evaluation.run_evaluation          # Full eval (needs Agent A running on 8000)
    python -m evaluation.run_evaluation --retrieval-only  # Retrieval metrics only (needs Qdrant on 6333)

Outputs: evaluation/results.json
"""

import json
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient

load_dotenv()

# -- Config --
API_BASE = "http://localhost:8000"
QDRANT_HOST = os.getenv("QDRANT_HOST", os.getenv("QUADRANT_HOST", "localhost"))
QDRANT_PORT = int(os.getenv("QDRANT_PORT", os.getenv("QUADRANT_PORT", 6333)))
COLLECTION_NAME = "uae_properties"
EMBEDDING_MODEL = "text-embedding-3-small"

TEST_SET_PATH = Path(__file__).parent / "test_set.json"
RESULTS_PATH = Path(__file__).parent / "results.json"

openai_client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)


# ══════════════════════════════════════════════════════════════════════
# PART 1: RETRIEVAL EVALUATION  (Session 11, slides 27-28)
# ══════════════════════════════════════════════════════════════════════

def embed_query(query: str) -> list[float]:
    resp = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=[query])
    return resp.data[0].embedding


def search_qdrant(query: str, top_k: int = 5) -> list[dict]:
    """Query Qdrant directly (bypasses the agent) and return chunks with scores."""
    qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    vector = embed_query(query)
    results = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=vector,
        limit=top_k,
        with_payload=True,
    )
    chunks = []
    for point in results.points:
        text = point.payload.get("text", "")
        source = point.payload.get("source", "unknown")
        chunks.append({"text": text, "source": source, "score": point.score})
    return chunks


def chunk_is_relevant(chunk_text: str, keywords: list[str]) -> bool:
    """A chunk is relevant if it contains at least one expected keyword."""
    lower = chunk_text.lower()
    return any(kw.lower() in lower for kw in keywords)


def precision_at_k(retrieved_chunks: list[dict], keywords: list[str], k: int) -> float:
    """Of the top-K chunks, how many are relevant?"""
    top_k = retrieved_chunks[:k]
    relevant = sum(1 for c in top_k if chunk_is_relevant(c["text"], keywords))
    return relevant / k if k > 0 else 0.0


def recall_at_k(retrieved_chunks: list[dict], keywords: list[str], k: int) -> float:
    """Of all chunks that COULD be relevant, how many did we find in top-K?
    We estimate total relevant by scanning all returned chunks."""
    top_k = retrieved_chunks[:k]
    relevant_in_k = sum(1 for c in top_k if chunk_is_relevant(c["text"], keywords))
    # Estimate: query with higher K to find total relevant
    total_relevant = max(1, sum(1 for c in retrieved_chunks if chunk_is_relevant(c["text"], keywords)))
    return relevant_in_k / total_relevant


def mrr(retrieved_chunks: list[dict], keywords: list[str]) -> float:
    """Reciprocal rank of the first relevant chunk."""
    for i, c in enumerate(retrieved_chunks):
        if chunk_is_relevant(c["text"], keywords):
            return 1.0 / (i + 1)
    return 0.0


def run_retrieval_evaluation(test_set: list[dict]) -> dict:
    """Run retrieval metrics on PDF-sourced questions that have retrieval_keywords."""
    pdf_cases = [tc for tc in test_set if tc.get("retrieval_keywords")]
    if not pdf_cases:
        return {"message": "No retrieval test cases found", "cases": []}

    print(f"\n{'-'*60}")
    print(f"  RETRIEVAL EVALUATION ({len(pdf_cases)} questions)")
    print(f"{'-'*60}")

    all_p5, all_r5, all_mrr = [], [], []
    case_results = []

    for tc in pdf_cases:
        q = tc["question"]
        kws = tc["retrieval_keywords"]

        # Query Qdrant with K=10 so we can compute recall against a larger pool
        chunks = search_qdrant(q, top_k=10)

        p5 = precision_at_k(chunks, kws, 5)
        r5 = recall_at_k(chunks, kws, 5)
        m = mrr(chunks, kws)

        all_p5.append(p5)
        all_r5.append(r5)
        all_mrr.append(m)

        case_results.append({
            "id": tc["id"],
            "question": q,
            "keywords": kws,
            "precision_at_5": round(p5, 2),
            "recall_at_5": round(r5, 2),
            "mrr": round(m, 2),
            "top_chunk_preview": chunks[0]["text"][:120] + "..." if chunks else "EMPTY",
        })

        status = "OK" if p5 >= 0.4 else "LOW"
        print(f"  [{status}] Q{tc['id']}: P@5={p5:.2f}  R@5={r5:.2f}  MRR={m:.2f}  | {q[:50]}...")

    avg_p5 = sum(all_p5) / len(all_p5)
    avg_r5 = sum(all_r5) / len(all_r5)
    avg_mrr = sum(all_mrr) / len(all_mrr)

    print(f"\n  {'Metric':<20} {'Score':<10}")
    print(f"  {'-'*30}")
    print(f"  {'Avg Precision@5':<20} {avg_p5:.3f}")
    print(f"  {'Avg Recall@5':<20} {avg_r5:.3f}")
    print(f"  {'Avg MRR':<20} {avg_mrr:.3f}")

    return {
        "avg_precision_at_5": round(avg_p5, 3),
        "avg_recall_at_5": round(avg_r5, 3),
        "avg_mrr": round(avg_mrr, 3),
        "num_cases": len(pdf_cases),
        "cases": case_results,
    }


# ══════════════════════════════════════════════════════════════════════
# PART 2: GENERATION EVALUATION — LLM-as-Judge  (Session 11, slide 36)
# ══════════════════════════════════════════════════════════════════════

def llm_as_judge(question: str, expected: str, actual: str) -> dict:
    """Use LLM to score the response on 4 dimensions (1-5 each)."""
    prompt = f"""Score this AI response on a scale of 1-5 for each dimension.
Return ONLY valid JSON with keys: correctness, faithfulness, relevance, completeness.
Each value must be an integer 1-5.

Question: {question}
Expected answer: {expected}
Actual response: {actual[:2000]}

Scoring:
1 = Complete failure  2 = Mostly wrong  3 = Partial, missing key details
4 = Mostly correct, minor issues  5 = Perfect or near-perfect

JSON:"""

    try:
        resp = openai_client.chat.completions.create(
            model="openrouter/auto",
            messages=[
                {"role": "system", "content": "You are a strict evaluation judge. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=100,
        )
        text = resp.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(text)
    except Exception as e:
        print(f"    [Judge error: {e}]")
        return {"correctness": 0, "faithfulness": 0, "relevance": 0, "completeness": 0}


def run_query(question: str, session_id: str) -> dict:
    """Send a query to Agent A via /chat and return response + timing."""
    start = time.time()
    try:
        resp = httpx.post(
            f"{API_BASE}/chat",
            json={"query": question, "session_id": session_id},
            timeout=120,
        )
        elapsed = time.time() - start
        data = resp.json()
        return {"response": data.get("response", ""), "latency": round(elapsed, 2), "ok": True}
    except Exception as e:
        return {"response": f"ERROR: {e}", "latency": round(time.time() - start, 2), "ok": False}


def run_generation_evaluation(test_set: list[dict]) -> dict:
    """Run all test queries through the agent and score with LLM-as-Judge."""
    print(f"\n{'-'*60}")
    print(f"  GENERATION EVALUATION ({len(test_set)} questions)")
    print(f"{'-'*60}")

    results = []
    total_latency = 0

    for i, tc in enumerate(test_set):
        qid = tc["id"]
        question = tc["question"]
        expected = tc["expected_answer"]

        print(f"  [{i+1}/{len(test_set)}] Q{qid}: {question[:55]}...", end=" ", flush=True)

        result = run_query(question, session_id=f"eval-{qid}")
        total_latency += result["latency"]

        scores = llm_as_judge(question, expected, result["response"])
        avg = sum(scores.values()) / max(len(scores), 1)

        results.append({
            **tc,
            "actual_response": result["response"][:500],
            "latency_seconds": result["latency"],
            "scores": scores,
            "avg_score": round(avg, 2),
        })

        print(f"({result['latency']}s) avg={avg:.1f} {scores}")

    # Aggregate
    valid = [r for r in results if any(r["scores"].values())]
    n = len(valid) or 1
    summary = {
        "total_questions": len(test_set),
        "avg_latency": round(total_latency / len(test_set), 2),
        "avg_correctness": round(sum(r["scores"]["correctness"] for r in valid) / n, 2),
        "avg_faithfulness": round(sum(r["scores"]["faithfulness"] for r in valid) / n, 2),
        "avg_relevance": round(sum(r["scores"]["relevance"] for r in valid) / n, 2),
        "avg_completeness": round(sum(r["scores"]["completeness"] for r in valid) / n, 2),
    }
    summary["overall"] = round(
        (summary["avg_correctness"] + summary["avg_faithfulness"] +
         summary["avg_relevance"] + summary["avg_completeness"]) / 4, 2
    )

    return {"summary": summary, "results": results}


# ══════════════════════════════════════════════════════════════════════
# PART 3: FAILURE ANALYSIS  (Session 11, slide 42 — "3 failure cases")
# ══════════════════════════════════════════════════════════════════════

def analyze_failures(gen_results: list[dict]) -> list[dict]:
    """Pick the 3 lowest-scoring responses and explain why they failed."""
    scored = [r for r in gen_results if r.get("avg_score", 0) > 0]
    sorted_by_score = sorted(scored, key=lambda r: r["avg_score"])
    worst_3 = sorted_by_score[:3]

    failures = []
    for r in worst_3:
        diagnosis = []
        s = r["scores"]
        if s.get("correctness", 0) <= 2:
            diagnosis.append("Factually incorrect — wrong data or numbers")
        if s.get("faithfulness", 0) <= 2:
            diagnosis.append("Hallucination — claims not grounded in retrieved context")
        if s.get("relevance", 0) <= 2:
            diagnosis.append("Off-topic — did not address the actual question")
        if s.get("completeness", 0) <= 2:
            diagnosis.append("Incomplete — missing key information from the expected answer")
        if not diagnosis:
            diagnosis.append("Partial issues across multiple dimensions")

        failures.append({
            "question": r["question"],
            "expected": r["expected_answer"],
            "actual_preview": r.get("actual_response", "")[:200],
            "scores": s,
            "avg_score": r["avg_score"],
            "diagnosis": diagnosis,
        })

    return failures


# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════

def main():
    retrieval_only = "--retrieval-only" in sys.argv

    with open(TEST_SET_PATH) as f:
        test_set = json.load(f)

    print(f"\n{'='*60}")
    print(f"  REAL ESTATE INVESTMENT ANALYZER — EVALUATION")
    print(f"  Test set: {len(test_set)} questions")
    print(f"{'='*60}")

    # Always run retrieval eval (only needs Qdrant)
    retrieval = run_retrieval_evaluation(test_set)

    if retrieval_only:
        output = {"retrieval": retrieval}
        with open(RESULTS_PATH, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\nResults saved to {RESULTS_PATH}")
        return

    # Full eval: run generation + judge
    generation = run_generation_evaluation(test_set)
    failures = analyze_failures(generation["results"])

    # Print summary table
    s = generation["summary"]
    print(f"\n{'='*60}")
    print(f"  EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"  {'Metric':<25} {'Score':<10}")
    print(f"  {'-'*35}")
    print(f"  {'Retrieval P@5':<25} {retrieval['avg_precision_at_5']:.3f}")
    print(f"  {'Retrieval R@5':<25} {retrieval['avg_recall_at_5']:.3f}")
    print(f"  {'Retrieval MRR':<25} {retrieval['avg_mrr']:.3f}")
    print(f"  {'-'*35}")
    print(f"  {'Correctness':<25} {s['avg_correctness']:.2f} / 5.00")
    print(f"  {'Faithfulness':<25} {s['avg_faithfulness']:.2f} / 5.00")
    print(f"  {'Relevance':<25} {s['avg_relevance']:.2f} / 5.00")
    print(f"  {'Completeness':<25} {s['avg_completeness']:.2f} / 5.00")
    print(f"  {'-'*35}")
    print(f"  {'OVERALL':<25} {s['overall']:.2f} / 5.00")
    print(f"  {'Avg Latency':<25} {s['avg_latency']:.1f}s")

    # Print failure analysis
    print(f"\n  FAILURE ANALYSIS (3 worst cases):")
    print(f"  {'-'*50}")
    for i, f_case in enumerate(failures):
        print(f"  {i+1}. Q: {f_case['question'][:60]}...")
        print(f"     Score: {f_case['avg_score']}/5  |  Scores: {f_case['scores']}")
        for d in f_case["diagnosis"]:
            print(f"     -> {d}")
        print()

    # Save
    output = {
        "retrieval": retrieval,
        "generation": generation,
        "failures": failures,
    }
    with open(RESULTS_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"  Full results saved to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
