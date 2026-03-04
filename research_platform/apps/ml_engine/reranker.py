"""
Cross-Encoder Reranker for RAG pipelines.

Uses sentence-transformers cross-encoder/ms-marco-MiniLM-L-6-v2 to
score (query, passage) pairs and reorder retrieved chunks.
"""
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class CrossEncoderReranker:
    """Reranks a list of retrieved chunks using a cross-encoder model."""

    def __init__(self):
        self._model = None

    def _get_model(self):
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(_MODEL_NAME)
            logger.info("CrossEncoderReranker: loaded model '%s'.", _MODEL_NAME)
        except Exception as exc:
            logger.error("CrossEncoderReranker: failed to load model: %s", exc)
            self._model = None
        return self._model

    def rerank(
        self,
        query: str,
        documents: List[Dict],
        top_k: int = 5,
    ) -> List[Dict]:
        """
        Score each (query, doc_text) pair and return top_k by cross-encoder score.

        Args:
            query: The user's search query.
            documents: List of chunk dicts with a 'content' key.
            top_k: Number of top documents to return.

        Returns:
            Top-k documents sorted by descending cross-encoder score,
            each augmented with a 'cross_encoder_score' key.
        """
        if not documents:
            return []

        model = self._get_model()
        if model is None:
            # Graceful fallback: return first top_k as-is
            logger.warning("CrossEncoderReranker: model unavailable; skipping rerank.")
            return documents[:top_k]

        pairs = [(query, doc.get("content", "")) for doc in documents]
        try:
            scores = model.predict(pairs)
        except Exception as exc:
            logger.error("CrossEncoderReranker.rerank failed: %s", exc)
            return documents[:top_k]

        scored_docs = sorted(
            zip(scores, documents),
            key=lambda x: x[0],
            reverse=True,
        )
        result = []
        for score, doc in scored_docs[:top_k]:
            doc_copy = dict(doc)
            doc_copy["cross_encoder_score"] = float(score)
            result.append(doc_copy)
        return result


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_reranker: Optional[CrossEncoderReranker] = None


def get_reranker() -> CrossEncoderReranker:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoderReranker()
    return _reranker
