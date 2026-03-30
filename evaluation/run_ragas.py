"""
RAGAS Evaluation — Automated RAG quality metrics.

Complements run_evaluation.py (manual metrics) with RAGAS framework metrics:
  - Faithfulness: Is the answer grounded in retrieved context?
  - Answer Relevancy: Does the answer address the question?
  - Context Precision: Are retrieved chunks relevant?
  - Context Recall: Did retrieval find everything needed?

Aligned with Session 11, slides 33-35.

Usage:
    pip install ragas datasets
    python -m evaluation.run_ragas           # Needs Agent A on :8000 + Qdrant on :6333
    python -m evaluation.run_ragas --dry-run # Show what would be evaluated

Outputs: evaluation/ragas_results.json
"""

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

TEST_SET_PATH = Path(__file__).parent / "test_set.json"
RESULTS_PATH = Path(__file__).parent / "ragas_results.json"
API_BASE = "http://localhost:8000"

QDRANT_HOST = os.getenv("QDRANT_HOST", os.getenv("QUADRANT_HOST", "localhost"))
QDRANT_PORT = int(os.getenv("QDRANT_PORT", os.getenv("QUADRANT_PORT", 6333)))
COLLECTION_NAME = "uae_properties"
EMBEDDING_MODEL = "text-embedding-3-small"


def get_agent_response(question: str) -> str:
    """Query Agent A and return the response text."""
    try:
        resp = httpx.post(
            f"{API_BASE}/chat",
            json={"query": question, "session_id": f"ragas-eval"},
            timeout=120,
        )
        return resp.json().get("response", "")
    except Exception as e:
        print(f"  [Error querying agent: {e}]")
        return ""


def get_retrieved_contexts(question: str, top_k: int = 5) -> list[str]:
    """Query Qdrant directly for retrieved contexts."""
    from openai import OpenAI
    from qdrant_client import QdrantClient

    openai_client = OpenAI(
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
    )

    resp = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=[question])
    vector = resp.data[0].embedding

    qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    results = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=vector,
        limit=top_k,
        with_payload=True,
    )
    return [p.payload.get("text", "") for p in results.points]


def build_ragas_dataset(test_set: list[dict]) -> dict:
    """Build the dataset dict that RAGAS expects: question, answer, contexts, ground_truth."""
    # Only use PDF-sourced cases (they have retrieval context)
    pdf_cases = [tc for tc in test_set if tc.get("retrieval_keywords")]

    questions, answers, contexts, ground_truths = [], [], [], []

    for i, tc in enumerate(pdf_cases):
        q = tc["question"]
        print(f"  [{i+1}/{len(pdf_cases)}] Querying: {q[:60]}...", flush=True)

        answer = get_agent_response(q)
        retrieved = get_retrieved_contexts(q)

        questions.append(q)
        answers.append(answer)
        contexts.append(retrieved)
        ground_truths.append(tc["expected_answer"])

    return {
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths,
    }


def run_ragas_evaluation(eval_data: dict) -> dict:
    """Run RAGAS metrics on the prepared dataset."""
    try:
        from ragas import evaluate
        from ragas.metrics import (
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        )
        from datasets import Dataset
    except ImportError:
        print("\n  RAGAS not installed. Install with: pip install ragas datasets")
        print("  Falling back to manual metric approximations...\n")
        return _approximate_ragas_metrics(eval_data)

    dataset = Dataset.from_dict(eval_data)

    print("\n  Running RAGAS evaluation (this calls the evaluator LLM)...")
    results = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    )

    return {
        "faithfulness": round(results["faithfulness"], 3),
        "answer_relevancy": round(results["answer_relevancy"], 3),
        "context_precision": round(results["context_precision"], 3),
        "context_recall": round(results["context_recall"], 3),
    }


def _approximate_ragas_metrics(eval_data: dict) -> dict:
    """Lightweight approximation when RAGAS is not installed.
    Uses keyword overlap as a proxy — not as accurate as LLM-based RAGAS."""
    from collections import Counter

    scores = {"faithfulness": [], "answer_relevancy": [], "context_precision": [], "context_recall": []}

    for q, ans, ctxs, gt in zip(
        eval_data["question"], eval_data["answer"],
        eval_data["contexts"], eval_data["ground_truth"]
    ):
        ans_lower = ans.lower()
        ctx_combined = " ".join(ctxs).lower()
        gt_lower = gt.lower()

        # Faithfulness proxy: what fraction of answer words appear in context?
        ans_words = set(ans_lower.split())
        ctx_words = set(ctx_combined.split())
        if ans_words:
            scores["faithfulness"].append(len(ans_words & ctx_words) / len(ans_words))

        # Answer relevancy proxy: word overlap between answer and question
        q_words = set(q.lower().split()) - {"what", "is", "the", "a", "an", "how", "much", "for", "in"}
        if q_words:
            scores["answer_relevancy"].append(len(ans_words & q_words) / len(q_words))

        # Context precision proxy: fraction of contexts containing ground truth keywords
        gt_keywords = [w for w in gt_lower.split() if len(w) > 3]
        relevant_ctxs = sum(1 for c in ctxs if any(kw in c.lower() for kw in gt_keywords))
        scores["context_precision"].append(relevant_ctxs / max(len(ctxs), 1))

        # Context recall proxy: fraction of ground truth keywords found in any context
        found = sum(1 for kw in gt_keywords if kw in ctx_combined)
        scores["context_recall"].append(found / max(len(gt_keywords), 1))

    return {
        metric: round(sum(vals) / max(len(vals), 1), 3)
        for metric, vals in scores.items()
    }


def main():
    dry_run = "--dry-run" in sys.argv

    with open(TEST_SET_PATH) as f:
        test_set = json.load(f)

    pdf_cases = [tc for tc in test_set if tc.get("retrieval_keywords")]

    print(f"\n{'='*60}")
    print(f"  RAGAS EVALUATION")
    print(f"  Test cases with retrieval: {len(pdf_cases)}")
    print(f"{'='*60}")

    if dry_run:
        for tc in pdf_cases:
            print(f"  Q{tc['id']}: {tc['question'][:60]}...")
        print(f"\n  Run without --dry-run to execute evaluation.")
        return

    eval_data = build_ragas_dataset(test_set)
    results = run_ragas_evaluation(eval_data)

    print(f"\n{'='*60}")
    print(f"  RAGAS RESULTS")
    print(f"{'='*60}")
    print(f"  {'Metric':<25} {'Score':<10}")
    print(f"  {'─'*35}")
    for metric, score in results.items():
        quality = "Good" if score >= 0.7 else "Acceptable" if score >= 0.5 else "Needs work"
        print(f"  {metric:<25} {score:.3f}  ({quality})")

    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
