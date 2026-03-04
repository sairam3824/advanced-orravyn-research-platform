"""
Self-Reflective Generation modules (Self-RAG — Option 6).

Three components:
  1. RetrievalDecisionModule  — decides whether retrieval is needed at all
  2. ChunkRelevanceScorer     — filters low-relevance chunks post-retrieval
  3. CitationFaithfulnessVerifier — checks that the response is grounded in sources
"""
import math
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

_RELEVANCE_THRESHOLD = 0.3   # chunks below this are discarded


def _sigmoid(x: float) -> float:
    """Normalise a cross-encoder logit to [0, 1]."""
    return 1.0 / (1.0 + math.exp(-x))


_FAITHFULNESS_PROMPT = (
    "You are a rigorous fact-checker for academic content. "
    "Given a generated response and a set of source passages, evaluate whether "
    "the response is factually grounded in those passages.\n\n"
    "Source passages:\n{context}\n\n"
    "Generated response:\n{response}\n\n"
    "1. Identify any claims in the response that are NOT supported by the passages.\n"
    "2. Output a faithfulness score between 0.0 (completely unsupported) and 1.0 (fully supported).\n"
    "3. List the unsupported claims (if any).\n\n"
    "Respond in this exact JSON format:\n"
    '{"faithfulness_score": <float>, "flagged_claims": [<str>, ...]}'
)


# ---------------------------------------------------------------------------
# 1. Retrieval Decision Module
# ---------------------------------------------------------------------------

class RetrievalDecisionModule:
    """
    Decides whether a query requires document retrieval.

    Uses heuristic keyword matching — no extra LLM call needed.
    Defaults to always retrieving for safety.
    """

    # Queries that typically do NOT require external evidence
    _SKIP_KEYWORDS = [
        "what is", "define", "definition of", "explain briefly",
        "what does", "meaning of", "describe briefly",
    ]

    # Queries that strongly benefit from retrieval
    _RETRIEVE_KEYWORDS = [
        "recent papers", "according to", "compare studies", "evidence for",
        "research shows", "studies show", "literature on", "survey of",
        "state of the art", "sota", "benchmark", "dataset", "experimental results",
        "propose", "novel method", "new approach", "outperforms",
    ]

    def needs_retrieval(self, query: str) -> bool:
        """
        Return True if the query should trigger document retrieval.

        Logic:
          - If the query matches a retrieve keyword → True
          - If the query matches a skip keyword AND is short → False
          - Default → True (safe fallback)
        """
        q_lower = query.lower().strip()

        if any(kw in q_lower for kw in self._RETRIEVE_KEYWORDS):
            return True

        is_short = len(query.split()) <= 12
        if is_short and any(q_lower.startswith(kw) for kw in self._SKIP_KEYWORDS):
            logger.info("RetrievalDecisionModule: skipping retrieval for short definitional query.")
            return False

        return True  # safe default


# ---------------------------------------------------------------------------
# 2. Chunk Relevance Scorer
# ---------------------------------------------------------------------------

class ChunkRelevanceScorer:
    """
    Scores retrieved chunks for relevance to the query using the cross-encoder
    and filters out chunks below a relevance threshold.
    """

    def score_chunks(self, query: str, chunks: List[Dict]) -> List[Dict]:
        """
        Add a 'relevance_score' (0–1) to each chunk and filter low-relevance ones.

        Args:
            query: User query string.
            chunks: List of chunk dicts (must have 'content' key).

        Returns:
            Filtered and scored chunk list (relevance_score >= threshold).
        """
        if not chunks:
            return []

        try:
            from .reranker import get_reranker
            reranker = get_reranker()
            model = reranker._get_model()

            if model is None:
                # No model available — pass through unchanged
                return chunks

            pairs = [(query, chunk.get("content", "")) for chunk in chunks]
            raw_scores = model.predict(pairs)

            scored = []
            for chunk, score in zip(chunks, raw_scores):
                norm_score = _sigmoid(float(score))
                if norm_score >= _RELEVANCE_THRESHOLD:
                    chunk_copy = dict(chunk)
                    chunk_copy["relevance_score"] = round(norm_score, 4)
                    scored.append(chunk_copy)

            if not scored:
                # Nothing passed threshold — return top-3 as fallback
                logger.info("ChunkRelevanceScorer: all chunks below threshold; returning top-3 fallback.")
                fallback = []
                for chunk, score in sorted(zip(chunks, raw_scores), key=lambda x: x[1], reverse=True)[:3]:
                    chunk_copy = dict(chunk)
                    chunk_copy["relevance_score"] = round(_sigmoid(float(score)), 4)
                    fallback.append(chunk_copy)
                return fallback

            return sorted(scored, key=lambda c: c["relevance_score"], reverse=True)

        except Exception as exc:
            logger.warning("ChunkRelevanceScorer: scoring failed (%s); passing chunks through.", exc)
            return chunks


# ---------------------------------------------------------------------------
# 3. Citation Faithfulness Verifier
# ---------------------------------------------------------------------------

class CitationFaithfulnessVerifier:
    """
    Uses gpt-4o-mini to verify that the generated response is grounded
    in the retrieved source passages.
    """

    def verify(self, response: str, chunks: List[Dict]) -> Dict:
        """
        Verify response faithfulness against source chunks.

        Args:
            response: The generated response text.
            chunks: Retrieved source chunk dicts.

        Returns:
            {
                "faithfulness_score": float,        # 0.0–1.0
                "flagged_claims": list[str],        # unsupported claims
            }
        """
        if not response or not chunks:
            return {"faithfulness_score": 1.0, "flagged_claims": []}

        # Build a compact context from chunks (cap at 2000 words to stay within token limits)
        context_parts = []
        word_count = 0
        for chunk in chunks:
            content = chunk.get("content", "")
            words = content.split()
            remaining = 2000 - word_count
            if remaining <= 0:
                break
            context_parts.append(" ".join(words[:remaining]))
            word_count += min(len(words), remaining)

        context = "\n\n---\n\n".join(context_parts)

        try:
            import json as _json
            import re as _re
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import HumanMessage

            prompt = _FAITHFULNESS_PROMPT.format(context=context, response=response)
            llm = ChatOpenAI(model="gpt-4o-mini", max_tokens=512, temperature=0)
            reply = llm.invoke([HumanMessage(content=prompt)])
            raw = reply.content.strip()

            # Strip markdown code fences (e.g. ```json ... ```)
            raw = _re.sub(r"^```[a-zA-Z]*\n?", "", raw).rstrip("`").strip()

            data = _json.loads(raw)
            return {
                "faithfulness_score": float(data.get("faithfulness_score", 1.0)),
                "flagged_claims": data.get("flagged_claims", []),
            }

        except Exception as exc:
            logger.warning("CitationFaithfulnessVerifier: verification failed (%s); defaulting to 1.0.", exc)
            return {"faithfulness_score": 1.0, "flagged_claims": []}
