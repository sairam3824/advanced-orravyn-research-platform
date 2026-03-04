"""
Hybrid Retriever: dense (ChromaDB) + sparse (BM25) + Reciprocal Rank Fusion.

Dense retrieval uses the existing sentence-transformer embeddings in ChromaDB.
Sparse retrieval uses rank_bm25.BM25Okapi over all indexed paper chunks.
RRF merges the ranked lists and returns a unified top-N result.
"""
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    Combines dense (semantic) and sparse (BM25) retrieval with RRF fusion.

    The BM25 index is built lazily on first use from all chunks currently
    in the ChromaDB collection, and is rebuilt whenever `rebuild_index()`
    is called explicitly (e.g. after new papers are approved).
    """

    def __init__(self):
        self._bm25 = None          # rank_bm25.BM25Okapi instance
        self._bm25_chunks: List[Dict] = []  # parallel list of chunk dicts

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def build_bm25_index(self) -> None:
        """(Re-)build the in-memory BM25 index from all ChromaDB chunks."""
        from .vector_store import get_collection
        from rank_bm25 import BM25Okapi

        collection = get_collection()
        if collection is None:
            logger.warning("HybridRetriever: ChromaDB not available; BM25 index not built.")
            return

        total = collection.count()
        if total == 0:
            logger.info("HybridRetriever: no chunks in collection; BM25 index empty.")
            self._bm25 = None
            self._bm25_chunks = []
            return

        # Fetch all chunks (ChromaDB .get() without filters returns everything)
        try:
            result = collection.get(include=["documents", "metadatas"])
        except Exception as exc:
            logger.error("HybridRetriever: failed to fetch chunks for BM25: %s", exc)
            return

        docs = result.get("documents") or []
        metas = result.get("metadatas") or []
        ids = result.get("ids") or []

        if not docs:
            self._bm25 = None
            self._bm25_chunks = []
            return

        self._bm25_chunks = [
            {"id": ids[i], "content": docs[i], "metadata": metas[i] if i < len(metas) else {}}
            for i in range(len(docs))
        ]

        tokenized = [chunk["content"].lower().split() for chunk in self._bm25_chunks]
        self._bm25 = BM25Okapi(tokenized)
        logger.info("HybridRetriever: BM25 index built with %d chunks.", len(self._bm25_chunks))

    def rebuild_index(self) -> None:
        """Public alias for build_bm25_index."""
        self.build_bm25_index()

    # ------------------------------------------------------------------
    # Retrieval methods
    # ------------------------------------------------------------------

    def dense_search(self, query: str, n: int = 50) -> List[Dict]:
        """Dense semantic search via ChromaDB."""
        from .vector_store import search_papers
        return search_papers(query, n_results=n)

    def bm25_search(self, query: str, n: int = 50) -> List[Dict]:
        """Sparse BM25 keyword search over all indexed chunks."""
        if self._bm25 is None:
            self.build_bm25_index()
        if self._bm25 is None or not self._bm25_chunks:
            return []

        tokenized_query = query.lower().split()
        if not tokenized_query:
            return []
        scores = self._bm25.get_scores(tokenized_query)

        # Pair each chunk with its score and sort descending
        scored = sorted(
            zip(scores, self._bm25_chunks),
            key=lambda x: x[0],
            reverse=True,
        )
        return [chunk for _, chunk in scored[:n]]

    def reciprocal_rank_fusion(
        self,
        dense_results: List[Dict],
        bm25_results: List[Dict],
        k: int = 60,
    ) -> List[Dict]:
        """
        Merge two ranked lists using Reciprocal Rank Fusion.

        RRF score = Σ 1/(k + rank_i)  (ranks are 1-indexed)
        """
        rrf_scores: Dict[str, float] = {}
        chunk_store: Dict[str, Dict] = {}

        def _chunk_key(chunk: Dict) -> str:
            # Both BM25 chunks (built from collection.get()) and dense chunks
            # (from search_papers()) now carry the ChromaDB document ID in chunk["id"].
            # Fall back to paper_id+chunk_index for any chunk that lacks an ID.
            cid = chunk.get("id")
            if not cid:
                meta = chunk.get("metadata", {})
                cid = f"{meta.get('paper_id', 'x')}_{meta.get('chunk_index', 0)}"
            return str(cid)

        for rank, chunk in enumerate(dense_results, start=1):
            key = _chunk_key(chunk)
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank)
            chunk_store[key] = chunk

        for rank, chunk in enumerate(bm25_results, start=1):
            key = _chunk_key(chunk)
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank)
            if key not in chunk_store:
                chunk_store[key] = chunk

        sorted_keys = sorted(rrf_scores, key=rrf_scores.get, reverse=True)
        return [chunk_store[k] for k in sorted_keys]

    def search(self, query: str, n_results: int = 10) -> List[Dict]:
        """
        Full hybrid pipeline: dense + BM25 → RRF → top n_results.
        """
        dense = self.dense_search(query, n=50)
        sparse = self.bm25_search(query, n=50)
        merged = self.reciprocal_rank_fusion(dense, sparse)
        return merged[:n_results]


# ---------------------------------------------------------------------------
# Module-level singleton (lazy init)
# ---------------------------------------------------------------------------

_hybrid_retriever: Optional[HybridRetriever] = None


def get_hybrid_retriever() -> HybridRetriever:
    global _hybrid_retriever
    if _hybrid_retriever is None:
        _hybrid_retriever = HybridRetriever()
    return _hybrid_retriever
