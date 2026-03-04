"""
Retrieval evaluation metrics for HA-RAG + SR-MAR benchmarking.

Metrics
-------
  NDCG@K   — Normalized Discounted Cumulative Gain
  MRR@K    — Mean Reciprocal Rank
  Recall@K — fraction of relevant docs retrieved in top-K
  MAP@K    — Mean Average Precision

All functions accept:
    retrieved_ids  : List[List[str]]  — ranked doc IDs per query
    relevant_ids   : List[List[str]]  — relevant doc IDs per query (unranked)

Compatible with BEIR benchmark evaluation format.
"""
import logging
from typing import Dict, List

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core metric functions
# ---------------------------------------------------------------------------

def _dcg(retrieved: List[str], relevant_set: set, k: int) -> float:
    gain = 0.0
    for i, doc_id in enumerate(retrieved[:k], start=1):
        if doc_id in relevant_set:
            gain += 1.0 / np.log2(i + 1)
    return gain


def _idcg(relevant_set: set, k: int) -> float:
    gain = 0.0
    for i in range(min(len(relevant_set), k)):
        gain += 1.0 / np.log2(i + 2)
    return gain


def compute_ndcg_at_k(
    retrieved_ids: List[List[str]],
    relevant_ids: List[List[str]],
    k: int = 10,
) -> float:
    """NDCG@K averaged over all queries."""
    scores = []
    for retrieved, relevant in zip(retrieved_ids, relevant_ids):
        rel_set = set(relevant)
        ideal = _idcg(rel_set, k)
        if ideal == 0:
            scores.append(0.0)
            continue
        scores.append(_dcg(retrieved, rel_set, k) / ideal)
    return float(np.mean(scores)) if scores else 0.0


def compute_mrr(
    retrieved_ids: List[List[str]],
    relevant_ids: List[List[str]],
    k: int = 10,
) -> float:
    """Mean Reciprocal Rank@K averaged over all queries."""
    scores = []
    for retrieved, relevant in zip(retrieved_ids, relevant_ids):
        rel_set = set(relevant)
        rr = 0.0
        for i, doc_id in enumerate(retrieved[:k], start=1):
            if doc_id in rel_set:
                rr = 1.0 / i
                break
        scores.append(rr)
    return float(np.mean(scores)) if scores else 0.0


def compute_recall_at_k(
    retrieved_ids: List[List[str]],
    relevant_ids: List[List[str]],
    k: int = 10,
) -> float:
    """Recall@K averaged over all queries."""
    scores = []
    for retrieved, relevant in zip(retrieved_ids, relevant_ids):
        rel_set = set(relevant)
        if not rel_set:
            continue
        hits = sum(1 for doc_id in retrieved[:k] if doc_id in rel_set)
        scores.append(hits / len(rel_set))
    return float(np.mean(scores)) if scores else 0.0


def compute_hit_at_k(
    retrieved_ids: List[List[str]],
    relevant_ids: List[List[str]],
    k: int = 5,
) -> float:
    """Hit@K: fraction of queries where at least one relevant doc appears in top-K."""
    scores = []
    for retrieved, relevant in zip(retrieved_ids, relevant_ids):
        rel_set = set(relevant)
        if not rel_set:
            continue
        hit = any(doc_id in rel_set for doc_id in retrieved[:k])
        scores.append(1.0 if hit else 0.0)
    return float(np.mean(scores)) if scores else 0.0


def compute_map(
    retrieved_ids: List[List[str]],
    relevant_ids: List[List[str]],
    k: int = 10,
) -> float:
    """Mean Average Precision@K averaged over all queries."""
    scores = []
    for retrieved, relevant in zip(retrieved_ids, relevant_ids):
        rel_set = set(relevant)
        if not rel_set:
            continue
        hits, precision_sum = 0, 0.0
        for i, doc_id in enumerate(retrieved[:k], start=1):
            if doc_id in rel_set:
                hits += 1
                precision_sum += hits / i
        scores.append(precision_sum / min(len(rel_set), k))
    return float(np.mean(scores)) if scores else 0.0


# ---------------------------------------------------------------------------
# Combined evaluator
# ---------------------------------------------------------------------------

def evaluate_retrieval(
    retrieved_ids: List[List[str]],
    relevant_ids: List[List[str]],
    k_values: List[int] = [1, 5, 10],
) -> Dict[str, float]:
    """
    Run NDCG, MRR, Recall, MAP at multiple K values.

    Args:
        retrieved_ids: Ranked list of retrieved document IDs per query.
        relevant_ids:  Ground-truth relevant document IDs per query.
        k_values:      List of cutoff ranks to evaluate at.

    Returns:
        Flat dict: {"ndcg@10": 0.71, "mrr@10": 0.68, "recall@10": 0.80, ...}
    """
    results: Dict[str, float] = {}
    for k in k_values:
        results[f"ndcg@{k}"]   = compute_ndcg_at_k(retrieved_ids, relevant_ids, k)
        results[f"mrr@{k}"]    = compute_mrr(retrieved_ids, relevant_ids, k)
        results[f"recall@{k}"] = compute_recall_at_k(retrieved_ids, relevant_ids, k)
        results[f"map@{k}"]    = compute_map(retrieved_ids, relevant_ids, k)
        results[f"hit@{k}"]    = compute_hit_at_k(retrieved_ids, relevant_ids, k)

    logger.info(
        "Retrieval eval: NDCG@10=%.4f  MRR@10=%.4f  Recall@10=%.4f",
        results.get("ndcg@10", 0),
        results.get("mrr@10", 0),
        results.get("recall@10", 0),
    )
    return results
