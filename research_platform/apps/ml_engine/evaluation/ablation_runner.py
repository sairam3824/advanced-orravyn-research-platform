"""
Ablation Study Runner for HA-RAG + SR-MAR + Self-RAG pipeline.

Systematically disables each component and measures the performance delta,
producing the ablation table required for tier-1 conference submission.

Usage
-----
    from apps.ml_engine.evaluation.ablation_runner import AblationRunner, STANDARD_ABLATIONS

    queries = [
        {
            "query": "What is the methodology of transformer attention?",
            "relevant_paper_ids": ["42", "17"],
            "reference_answer": "Transformer attention uses...",   # optional
        },
        ...
    ]

    runner = AblationRunner(queries)
    results = runner.run_all()
    runner.print_table(results)
    runner.save_results(results, "ablation_results.json")
"""
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .retrieval_eval import evaluate_retrieval
from .rag_eval import evaluate_rag

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Ablation configuration
# ---------------------------------------------------------------------------

@dataclass
class AblationConfig:
    """Controls which pipeline components are active."""
    name: str
    use_hybrid: bool = True         # BM25 + dense (False = dense-only)
    use_reranker: bool = True       # cross-encoder reranking
    use_decomposer: bool = True     # query decomposition for complex queries
    use_sr_mar: bool = True         # section-routed multi-agent retrieval
    use_self_rag: bool = True       # retrieval decision + chunk relevance scoring
    use_faithfulness: bool = False  # citation faithfulness (LLM call — off by default for speed)


# Standard ablations — one component disabled at a time
STANDARD_ABLATIONS: List[AblationConfig] = [
    AblationConfig("Full Pipeline (ours)"),
    AblationConfig("w/o SR-MAR",       use_sr_mar=False),
    AblationConfig("w/o Reranker",     use_reranker=False),
    AblationConfig("w/o Decomposer",   use_decomposer=False),
    AblationConfig("w/o Self-RAG",     use_self_rag=False),
    AblationConfig("w/o Hybrid",       use_hybrid=False, use_sr_mar=False),
    AblationConfig("Dense-Only",       use_hybrid=False, use_sr_mar=False,
                   use_reranker=False, use_decomposer=False, use_self_rag=False),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class AblationRunner:
    """
    Runs the retrieval + RAG pipeline under different ablation configurations
    and collects metrics for the paper's ablation table.
    """

    DISPLAY_METRICS = [
        "ndcg@10", "mrr@10", "recall@10",
        "answer_relevancy", "context_precision", "context_recall",
        "latency_ms",
    ]

    def __init__(self, test_queries: List[Dict]):
        """
        Args:
            test_queries: List of query dicts, each containing:
                - "query":               str   (required)
                - "relevant_paper_ids":  list  (required for retrieval metrics)
                - "reference_answer":    str   (optional, for RAG metrics)
        """
        self.test_queries = test_queries

    def _retrieve(self, query: str, config: AblationConfig) -> List[Dict]:
        """Choose retrieval strategy based on ablation config."""
        if config.use_sr_mar and config.use_hybrid:
            from apps.ml_engine.multi_agent_retrieval import get_orchestrator
            return get_orchestrator().search(query, n_results=10)

        if config.use_hybrid:
            from apps.ml_engine.hybrid_retrieval import get_hybrid_retriever
            return get_hybrid_retriever().search(query, n_results=10)

        # Dense-only fallback
        from apps.ml_engine.vector_store import search_papers
        return search_papers(query, n_results=10)

    def _rerank(self, query: str, chunks: List[Dict], config: AblationConfig) -> List[Dict]:
        if not config.use_reranker or not chunks:
            return chunks
        try:
            from apps.ml_engine.reranker import get_reranker
            return get_reranker().rerank(query, chunks, top_k=8)
        except Exception as exc:
            logger.warning("Reranker failed: %s", exc)
            return chunks

    def _score_chunks(self, query: str, chunks: List[Dict], config: AblationConfig) -> List[Dict]:
        if not config.use_self_rag or not chunks:
            return chunks
        try:
            from apps.ml_engine.self_reflective import ChunkRelevanceScorer
            return ChunkRelevanceScorer().score_chunks(query, chunks)
        except Exception as exc:
            logger.warning("Chunk scoring failed: %s", exc)
            return chunks

    def run_single(self, config: AblationConfig) -> Dict[str, float]:
        """Run one ablation configuration and return averaged metrics."""
        retrieved_ids_all: List[List[str]] = []
        relevant_ids_all: List[List[str]] = []
        rag_results: List[Dict] = []
        latencies: List[float] = []

        for item in self.test_queries:
            query = item["query"]
            relevant = item.get("relevant_paper_ids", [])

            t0 = time.perf_counter()

            # Retrieval
            chunks = self._retrieve(query, config)
            chunks = self._rerank(query, chunks, config)
            chunks = self._score_chunks(query, chunks, config)

            latency_ms = (time.perf_counter() - t0) * 1000
            latencies.append(latency_ms)

            # Retrieval metrics
            paper_ids = [
                str(c.get("metadata", {}).get("paper_id", ""))
                for c in chunks
            ]
            retrieved_ids_all.append(paper_ids)
            relevant_ids_all.append([str(r) for r in relevant])

            # RAG generation + eval (only if reference answer provided)
            if "reference_answer" in item and chunks:
                try:
                    from apps.ml_engine.rag_pipeline import query_rag
                    result = query_rag(query)
                    rag_score = evaluate_rag(
                        query=query,
                        response=result["response"],
                        chunks=chunks,
                        compute_faithfulness=config.use_faithfulness,
                    )
                    rag_results.append(rag_score)
                except Exception as exc:
                    logger.warning(
                        "RAG eval failed for query '%s': %s", query[:50], exc
                    )

        # Aggregate
        metrics = evaluate_retrieval(retrieved_ids_all, relevant_ids_all)
        metrics["latency_ms"] = sum(latencies) / len(latencies) if latencies else 0.0

        if rag_results:
            for key in rag_results[0]:
                vals = [r[key] for r in rag_results if key in r]
                metrics[key] = sum(vals) / len(vals) if vals else 0.0

        return metrics

    def run_all(
        self,
        configs: Optional[List[AblationConfig]] = None,
    ) -> Dict[str, Dict[str, float]]:
        """
        Run all ablation configurations.

        Returns:
            {config_name: {metric_name: value, ...}, ...}
        """
        configs = configs or STANDARD_ABLATIONS
        results: Dict[str, Dict[str, float]] = {}

        for config in configs:
            logger.info("Running ablation: %s", config.name)
            try:
                scores = self.run_single(config)
                results[config.name] = scores
                logger.info(
                    "  → NDCG@10=%.4f  MRR@10=%.4f  Latency=%.1fms",
                    scores.get("ndcg@10", 0),
                    scores.get("mrr@10", 0),
                    scores.get("latency_ms", 0),
                )
            except Exception as exc:
                logger.error("Ablation '%s' failed: %s", config.name, exc)
                results[config.name] = {"error": str(exc)}

        return results

    def print_table(self, results: Dict[str, Dict[str, float]]) -> None:
        """Print a formatted ablation comparison table."""
        metrics = self.DISPLAY_METRICS
        col_w = 15
        name_w = 30

        header = f"{'Configuration':<{name_w}}" + "".join(
            f"{m:>{col_w}}" for m in metrics
        )
        sep = "=" * len(header)

        print(f"\n{sep}")
        print("ABLATION STUDY RESULTS")
        print(sep)
        print(header)
        print("-" * len(header))

        for name, scores in results.items():
            if "error" in scores:
                print(f"{name:<{name_w}}  ERROR: {scores['error']}")
                continue
            row = f"{name:<{name_w}}" + "".join(
                f"{scores.get(m, float('nan')):>{col_w}.4f}" for m in metrics
            )
            print(row)

        print(sep)

    def save_results(
        self,
        results: Dict[str, Dict[str, float]],
        path: str = "ablation_results.json",
    ) -> None:
        """Save ablation results to a JSON file."""
        with open(path, "w") as f:
            json.dump(results, f, indent=2)
        logger.info("Ablation results saved to %s", path)
