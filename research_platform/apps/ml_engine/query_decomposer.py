"""
Query Decomposer for HA-RAG.

Detects whether a user query is "complex" (multi-faceted, comparative,
or relational) and decomposes it into 2–4 atomic sub-questions using
gpt-4o-mini. Results from sub-queries are later merged by deduplication.
"""
import logging
import re
from typing import List, Dict

logger = logging.getLogger(__name__)

# Keywords that signal a complex, multi-part query
_COMPLEX_KEYWORDS = [
    "compare", "comparison", "difference", "versus", "vs",
    "relationship", "how does", "impact of", "effect of",
    "trade-off", "tradeoff", "pros and cons", "advantages and disadvantages",
    "what are the", "in contrast", "relative to",
]

_DECOMPOSE_PROMPT = (
    "You are a research query analyst. Break the following research question "
    "into 2 to 4 short, atomic sub-questions that together cover the full scope "
    "of the original question. Return only the sub-questions, one per line, "
    "without numbering or bullet points.\n\nQuestion: {query}"
)


class QueryDecomposer:
    """Decomposes complex queries into atomic sub-questions."""

    # ------------------------------------------------------------------
    # Complexity detection
    # ------------------------------------------------------------------

    def is_complex(self, query: str) -> bool:
        """
        Heuristic check: a query is complex if it is long OR contains
        comparative/relational keywords.
        """
        if len(query) > 80:
            return True
        q_lower = query.lower()
        return any(kw in q_lower for kw in _COMPLEX_KEYWORDS)

    # ------------------------------------------------------------------
    # Decomposition
    # ------------------------------------------------------------------

    def decompose(self, query: str) -> List[str]:
        """
        Call gpt-4o-mini to split the query into sub-questions.

        Falls back to [query] if the API call fails.
        """
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import HumanMessage

            llm = ChatOpenAI(model="gpt-4o-mini", max_tokens=256, temperature=0)
            prompt = _DECOMPOSE_PROMPT.format(query=query)
            reply = llm.invoke([HumanMessage(content=prompt)])
            raw = reply.content.strip()

            # Parse lines; filter blank / very short lines
            sub_queries = [
                line.strip()
                for line in raw.splitlines()
                if line.strip() and len(line.strip()) > 5
            ]

            # Remove leading numbering: "1.", "1)", "(1)", "a.", "a)", "-", "*"
            cleaned = []
            for sq in sub_queries:
                sq = re.sub(
                    r"^\s*(?:\(\d+\)|\d+[\.\)]|[a-zA-Z][\.\)]|[-\*])\s*",
                    "", sq,
                ).strip()
                if sq:
                    cleaned.append(sq)

            if cleaned:
                logger.info("QueryDecomposer: decomposed into %d sub-queries.", len(cleaned))
                return cleaned[:4]  # cap at 4
        except Exception as exc:
            logger.warning("QueryDecomposer: decomposition failed: %s", exc)

        return [query]

    # ------------------------------------------------------------------
    # Result merging
    # ------------------------------------------------------------------

    @staticmethod
    def merge_results(results_per_query: List[List[Dict]]) -> List[Dict]:
        """
        Merge retrieval results from multiple sub-queries.

        Deduplicates by chunk id, then re-ranks by frequency of appearance
        (chunks retrieved for more sub-queries rank higher).
        """
        frequency: Dict[str, int] = {}
        chunk_store: Dict[str, Dict] = {}

        for results in results_per_query:
            seen_in_this_query: set = set()
            for chunk in results:
                meta = chunk.get("metadata", {})
                key = str(
                    meta.get("id")
                    or chunk.get("id")
                    or f"{meta.get('paper_id', 'x')}_{meta.get('chunk_index', 0)}"
                )
                if key not in seen_in_this_query:
                    frequency[key] = frequency.get(key, 0) + 1
                    seen_in_this_query.add(key)
                if key not in chunk_store:
                    chunk_store[key] = chunk

        sorted_keys = sorted(frequency, key=frequency.get, reverse=True)
        return [chunk_store[k] for k in sorted_keys]
