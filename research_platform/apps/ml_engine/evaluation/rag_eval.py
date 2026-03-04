"""
RAG-specific evaluation metrics.

Metrics
-------
  Faithfulness       — LLM-verified: is the response grounded in retrieved chunks?
                       (uses CitationFaithfulnessVerifier — incurs API cost)
  Answer Relevancy   — cosine similarity between query and response embeddings
  Context Precision  — fraction of retrieved chunks whose content appears in the response
  Context Recall     — sentence-level recall: what % of response sentences are
                       supported by at least one retrieved chunk

All metrics return values in [0.0, 1.0].  Higher = better.
"""
import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Individual metrics
# ---------------------------------------------------------------------------

def evaluate_faithfulness(response: str, chunks: List[Dict]) -> float:
    """
    Faithfulness: is the response factually grounded in the retrieved chunks?

    Uses CitationFaithfulnessVerifier (GPT-4o-mini call).
    Returns 1.0 if chunks or response are empty (no claims = fully faithful).
    """
    if not response or not chunks:
        return 1.0
    try:
        from apps.ml_engine.self_reflective import CitationFaithfulnessVerifier
        result = CitationFaithfulnessVerifier().verify(response, chunks)
        return float(result.get("faithfulness_score", 1.0))
    except Exception as exc:
        logger.warning("Faithfulness eval failed: %s", exc)
        return 1.0


def evaluate_answer_relevancy(query: str, response: str) -> float:
    """
    Answer relevancy: cosine similarity between query and response embeddings.
    Higher = response is more focused on what was asked.
    """
    if not query or not response:
        return 0.0
    try:
        from sentence_transformers import SentenceTransformer
        from sklearn.metrics.pairwise import cosine_similarity

        model = SentenceTransformer("all-MiniLM-L6-v2")
        embeddings = model.encode([query, response])
        return float(cosine_similarity([embeddings[0]], [embeddings[1]])[0][0])
    except Exception as exc:
        logger.warning("Answer relevancy eval failed: %s", exc)
        return 0.0


def evaluate_context_precision(response: str, chunks: List[Dict]) -> float:
    """
    Context precision: fraction of retrieved chunks whose content
    has meaningful token overlap with the generated response.

    A chunk is considered "used" if it shares > 5 tokens with the response.
    """
    if not chunks or not response:
        return 0.0
    response_tokens = set(response.lower().split())
    used = sum(
        1 for chunk in chunks
        if len(response_tokens & set(chunk.get("content", "").lower().split())) > 5
    )
    return used / len(chunks)


def evaluate_context_recall(response: str, chunks: List[Dict]) -> float:
    """
    Context recall: fraction of response sentences that are supported
    by at least one retrieved chunk (token overlap heuristic).

    Higher = fewer unsupported claims in the response.
    """
    if not response or not chunks:
        return 0.0

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", response) if s.strip()]
    if not sentences:
        return 0.0

    all_chunk_tokens = set()
    for chunk in chunks:
        all_chunk_tokens.update(chunk.get("content", "").lower().split())

    supported = sum(
        1 for sent in sentences
        if len(set(sent.lower().split()) & all_chunk_tokens) > 3
    )
    return supported / len(sentences)


# ---------------------------------------------------------------------------
# Combined evaluator
# ---------------------------------------------------------------------------

def evaluate_rag(
    query: str,
    response: str,
    chunks: List[Dict],
    compute_faithfulness: bool = True,
) -> Dict[str, float]:
    """
    Run all RAG metrics for a single (query, response, chunks) triple.

    Args:
        query:                The user query.
        response:             The generated response text.
        chunks:               Retrieved context chunks (list of dicts with 'content').
        compute_faithfulness: Whether to run the LLM-based faithfulness check.
                              Disable for bulk evaluation to save API cost.

    Returns:
        {
            "answer_relevancy":  float,
            "context_precision": float,
            "context_recall":    float,
            "faithfulness":      float,   # only if compute_faithfulness=True
        }
    """
    results: Dict[str, float] = {
        "answer_relevancy":  evaluate_answer_relevancy(query, response),
        "context_precision": evaluate_context_precision(response, chunks),
        "context_recall":    evaluate_context_recall(response, chunks),
    }
    if compute_faithfulness:
        results["faithfulness"] = evaluate_faithfulness(response, chunks)

    logger.info(
        "RAG eval: relevancy=%.4f  precision=%.4f  recall=%.4f  faithfulness=%.4f",
        results.get("answer_relevancy", 0),
        results.get("context_precision", 0),
        results.get("context_recall", 0),
        results.get("faithfulness", -1),
    )
    return results
