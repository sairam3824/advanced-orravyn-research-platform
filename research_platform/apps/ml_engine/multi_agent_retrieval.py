"""
Section-Routed Multi-Agent Retrieval (SR-MAR).

Problem solved
--------------
Standard RAG uses one retrieval path for every query.
"What is the methodology?" and "What are the experimental results?"
go through the same pipeline — no domain specialization.

Solution
--------
1. QueryIntentClassifier  — maps the query to one or more section intents
                            using keyword heuristics (no extra LLM call).
2. SectionAgent           — searches ONLY its section's boosted chunks in
                            ChromaDB (e.g. MethodologyAgent → section=Methodology).
3. MultiAgentOrchestrator — runs relevant agents in parallel, merges with
                            section-weighted fusion, supplements with hybrid
                            retrieval if section chunks are sparse.

This exploits the section-boosted ChromaDB index already built by
vector_store.index_paper() — those chunks carry section metadata
(section_boosted=True, section="Methodology" etc.) that regular
retrieval ignores.  SR-MAR makes that metadata actionable.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Agent configuration
# Mirrors SECTION_WEIGHTS in section_summarizer.py so that sections
# that are more research-valuable are also weighted higher in retrieval.
# ---------------------------------------------------------------------------

_AGENT_CONFIGS: List[Tuple[str, List[str], float]] = [
    ("methodology", ["Methodology", "Methods"],                       0.35),
    ("results",     ["Results", "Experiments"],                       0.30),
    ("discussion",  ["Discussion"],                                   0.15),
    ("literature",  ["Introduction", "Related Work", "Background"],   0.10),
    ("conclusion",  ["Conclusion"],                                   0.07),
]

# Build a quick lookup: agent_name → weight
_AGENT_WEIGHT: Dict[str, float] = {name: w for name, _, w in _AGENT_CONFIGS}

# ---------------------------------------------------------------------------
# Intent → keyword mapping
# ---------------------------------------------------------------------------

_INTENT_KEYWORDS: Dict[str, List[str]] = {
    "methodology": [
        "method", "approach", "algorithm", "technique", "architecture",
        "model", "proposed", "framework", "pipeline", "how does", "design",
        "implementation", "training", "loss", "objective", "formula",
        "equation", "module", "layer", "encoder", "decoder",
    ],
    "results": [
        "result", "performance", "accuracy", "benchmark", "evaluation",
        "experiment", "dataset", "compare", "outperform", "score",
        "metric", "bleu", "rouge", "f1", "precision", "recall",
        "ablation", "state-of-the-art", "sota", "table", "figure",
        "improvement", "gain", "error rate",
    ],
    "discussion": [
        "limitation", "why does", "insight", "analysis", "implication",
        "trade-off", "challenge", "issue", "future work", "weakness",
        "strength", "advantage", "disadvantage",
    ],
    "literature": [
        "background", "related work", "prior", "existing", "survey",
        "literature", "previous", "history", "origin", "compared to",
        "versus", "earlier work", "foundation",
    ],
    "conclusion": [
        "conclusion", "finding", "summary", "takeaway", "contribution",
        "demonstrate", "show that", "we conclude", "overall",
    ],
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _chunk_key(chunk: Dict) -> str:
    """Return a stable unique key for a chunk dict."""
    cid = chunk.get("id")
    if not cid:
        meta = chunk.get("metadata", {})
        cid = f"{meta.get('paper_id', 'x')}_{meta.get('chunk_index', 0)}"
    return str(cid)


def _section_weighted_merge(
    agent_results: List[Tuple[List[Dict], float]],
) -> List[Dict]:
    """
    Merge results from multiple section agents using weighted position scoring.

    score(chunk) = Σ (agent_weight / rank_in_agent)

    Chunks appearing in multiple agents accumulate scores, naturally
    surfacing cross-section evidence for multi-faceted queries.
    """
    scores: Dict[str, float] = {}
    chunk_store: Dict[str, Dict] = {}

    for chunks, weight in agent_results:
        for rank, chunk in enumerate(chunks, start=1):
            key = _chunk_key(chunk)
            scores[key] = scores.get(key, 0.0) + weight / rank
            if key not in chunk_store:
                chunk_store[key] = chunk

    sorted_keys = sorted(scores, key=scores.__getitem__, reverse=True)
    return [chunk_store[k] for k in sorted_keys]


# ---------------------------------------------------------------------------
# 1. Query Intent Classifier
# ---------------------------------------------------------------------------

class QueryIntentClassifier:
    """
    Maps a query to a list of section-agent names using keyword heuristics.

    Returns [] for broad/general queries (→ orchestrator falls back to
    hybrid retrieval, which covers all chunks without section filtering).
    """

    def classify(self, query: str) -> List[str]:
        """
        Return the list of agent names relevant to this query.

        A single query can activate multiple agents (e.g. a question about
        "methodology and results" activates both).
        """
        q_lower = query.lower()
        matched = [
            intent
            for intent, keywords in _INTENT_KEYWORDS.items()
            if any(kw in q_lower for kw in keywords)
        ]
        if matched:
            logger.info(
                "QueryIntentClassifier: query matched intents %s.", matched
            )
        else:
            logger.info(
                "QueryIntentClassifier: no specific intent — broad query, "
                "will use hybrid fallback."
            )
        return matched


# ---------------------------------------------------------------------------
# 2. Section Agent
# ---------------------------------------------------------------------------

class SectionAgent:
    """
    Retrieves chunks that belong to a specific set of paper sections.

    Uses the `section` metadata field set by vector_store.index_paper()
    on section-boosted chunks.  If the filtered search returns nothing
    (e.g. no papers have been section-indexed yet), the agent returns [].
    The orchestrator supplements with unfiltered hybrid retrieval.
    """

    def __init__(self, name: str, sections: List[str], weight: float):
        self.name = name
        self.sections = sections
        self.weight = weight

    def search(self, query: str, n: int = 10) -> List[Dict]:
        """Search ChromaDB filtered to this agent's sections."""
        from .vector_store import get_collection

        collection = get_collection()
        if collection is None:
            return []

        total = collection.count()
        if total == 0:
            return []

        n_query = min(n, total)

        try:
            results = collection.query(
                query_texts=[query],
                n_results=n_query,
                where={"section": {"$in": self.sections}},
            )
            docs = []
            if results.get("documents") and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    meta = (
                        results["metadatas"][0][i]
                        if results.get("metadatas") and results["metadatas"][0]
                        else {}
                    )
                    doc_id = (
                        results["ids"][0][i]
                        if results.get("ids") and results["ids"][0]
                        else None
                    )
                    docs.append({"id": doc_id, "content": doc, "metadata": meta})

            logger.info("SectionAgent[%s]: %d chunks retrieved.", self.name, len(docs))
            return docs

        except Exception as exc:
            # Most likely: no documents match the section filter yet.
            logger.debug(
                "SectionAgent[%s]: filtered search failed (%s); returning [].",
                self.name, exc,
            )
            return []


# ---------------------------------------------------------------------------
# 3. Multi-Agent Orchestrator
# ---------------------------------------------------------------------------

class MultiAgentOrchestrator:
    """
    Coordinates section agents and merges their results.

    Retrieval strategy
    ------------------
    Specific query (intent detected)
        → Run only the matched section agents in parallel
        → Section-weighted merge
        → Supplement with hybrid retrieval if result count < threshold

    Broad query (no intent detected)
        → Skip section agents entirely
        → Fall through to hybrid retrieval (covers all chunks uniformly)
    """

    # Build the agent pool once at class level
    _AGENT_POOL: Dict[str, "SectionAgent"] = {
        name: SectionAgent(name, sections, weight)
        for name, sections, weight in _AGENT_CONFIGS
    }

    def search(self, query: str, n_results: int = 10) -> List[Dict]:
        """
        Route query through relevant section agents and return merged results.
        """
        intents = QueryIntentClassifier().classify(query)

        # Broad query — no specialization, use hybrid retrieval directly
        if not intents:
            return self._hybrid_fallback(query, n_results)

        # Run matched agents in parallel
        active_agents = [
            self._AGENT_POOL[intent]
            for intent in intents
            if intent in self._AGENT_POOL
        ]

        agent_results: List[Tuple[List[Dict], float]] = []
        with ThreadPoolExecutor(max_workers=len(active_agents)) as pool:
            future_to_agent = {
                pool.submit(agent.search, query, n_results + 5): agent
                for agent in active_agents
            }
            for future in as_completed(future_to_agent):
                agent = future_to_agent[future]
                try:
                    chunks = future.result()
                    agent_results.append((chunks, agent.weight))
                except Exception as exc:
                    logger.warning(
                        "MultiAgentOrchestrator: agent '%s' raised: %s", agent.name, exc
                    )

        merged = _section_weighted_merge(agent_results)

        # Supplement with hybrid if section-indexed chunks are sparse
        if len(merged) < n_results:
            logger.info(
                "MultiAgentOrchestrator: only %d section chunks — supplementing "
                "with hybrid retrieval.",
                len(merged),
            )
            hybrid = self._hybrid_fallback(query, n_results)
            seen_ids = {_chunk_key(c) for c in merged}
            for chunk in hybrid:
                if _chunk_key(chunk) not in seen_ids:
                    merged.append(chunk)
                    seen_ids.add(_chunk_key(chunk))

        logger.info(
            "MultiAgentOrchestrator: returning %d chunks for intents=%s.",
            len(merged[:n_results]), intents,
        )
        return merged[:n_results]

    @staticmethod
    def _hybrid_fallback(query: str, n_results: int) -> List[Dict]:
        """Standard hybrid (BM25 + dense + RRF) retrieval as fallback."""
        from .hybrid_retrieval import get_hybrid_retriever
        return get_hybrid_retriever().search(query, n_results=n_results)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_orchestrator: Optional[MultiAgentOrchestrator] = None


def get_orchestrator() -> MultiAgentOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MultiAgentOrchestrator()
    return _orchestrator
