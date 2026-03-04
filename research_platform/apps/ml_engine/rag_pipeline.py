"""
LangGraph RAG pipeline for Yggdrasil AI chatbot.

Pipeline (HA-RAG + Self-RAG + SR-MAR):

  decide_retrieval
        │
        ├─ needs_retrieval=False ──────────────────► generate ► verify_citations ► END
        │
        └─ needs_retrieval=True
               │
               ▼
        decompose_query          ← HA-RAG: splits complex queries into sub-queries
               │
               ▼
        hybrid_retrieve          ← SR-MAR: routes each sub-query to section agents
               │                   (MethodologyAgent / ResultsAgent / LiteratureAgent …)
               │                   parallel execution → section-weighted merge
               │                   → hybrid fallback if section chunks sparse
               ▼
            rerank               ← HA-RAG: cross-encoder reranking
               │
               ▼
         score_chunks            ← Self-RAG: relevance filtering
               │
               ▼
           generate
               │
               ▼
       verify_citations          ← Self-RAG: faithfulness score
               │
               ▼
             END
"""
import logging
from typing import List, TypedDict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------

class RAGState(TypedDict):
    # Core fields
    query: str
    response: str
    sources: List[dict]

    # HA-RAG (Option 4)
    sub_queries: List[str]
    retrieved_docs: List[dict]
    reranked_docs: List[dict]

    # Self-RAG (Option 6)
    needs_retrieval: bool
    relevance_scores: List[float]
    faithfulness_score: float


# ---------------------------------------------------------------------------
# Helper: build deduplicated sources list
# ---------------------------------------------------------------------------

def _build_sources(docs: List[dict]) -> List[dict]:
    seen_ids: set = set()
    sources: List[dict] = []
    for doc in docs:
        pid = doc.get("metadata", {}).get("paper_id")
        if pid and pid not in seen_ids:
            seen_ids.add(pid)
            sources.append({
                "paper_id": pid,
                "title": doc["metadata"].get("title", "Unknown Paper"),
                "authors": doc["metadata"].get("authors", ""),
            })
    return sources


# ---------------------------------------------------------------------------
# Node: decide_retrieval  (Self-RAG — Option 6)
# ---------------------------------------------------------------------------

def _decide_retrieval(state: RAGState) -> RAGState:
    from .self_reflective import RetrievalDecisionModule
    needs = RetrievalDecisionModule().needs_retrieval(state["query"])
    return {**state, "needs_retrieval": needs}


# ---------------------------------------------------------------------------
# Node: decompose_query  (HA-RAG — Option 4)
# ---------------------------------------------------------------------------

def _decompose_query(state: RAGState) -> RAGState:
    from .query_decomposer import QueryDecomposer
    decomposer = QueryDecomposer()
    if decomposer.is_complex(state["query"]):
        sub_queries = decomposer.decompose(state["query"])
    else:
        sub_queries = [state["query"]]
    return {**state, "sub_queries": sub_queries}


# ---------------------------------------------------------------------------
# Node: hybrid_retrieve  (HA-RAG — Option 4)
# ---------------------------------------------------------------------------

def _hybrid_retrieve(state: RAGState) -> RAGState:
    from .multi_agent_retrieval import get_orchestrator
    from .query_decomposer import QueryDecomposer

    orchestrator = get_orchestrator()
    sub_queries = state.get("sub_queries") or [state["query"]]

    if len(sub_queries) == 1:
        # SR-MAR: routes to section agents or hybrid based on query intent
        docs = orchestrator.search(sub_queries[0], n_results=10)
    else:
        # Multiple sub-queries from decomposition — each gets section-routed
        results_per_query = [
            orchestrator.search(sq, n_results=10) for sq in sub_queries
        ]
        docs = QueryDecomposer.merge_results(results_per_query)
        docs = docs[:20]

    return {**state, "retrieved_docs": docs}


# ---------------------------------------------------------------------------
# Node: rerank  (HA-RAG — Option 4)
# ---------------------------------------------------------------------------

def _rerank(state: RAGState) -> RAGState:
    from .reranker import get_reranker
    reranker = get_reranker()
    reranked = reranker.rerank(state["query"], state["retrieved_docs"], top_k=8)
    return {**state, "reranked_docs": reranked}


# ---------------------------------------------------------------------------
# Node: score_chunks  (Self-RAG — Option 6)
# ---------------------------------------------------------------------------

def _score_chunks(state: RAGState) -> RAGState:
    from .self_reflective import ChunkRelevanceScorer
    scorer = ChunkRelevanceScorer()
    docs = state.get("reranked_docs") or state.get("retrieved_docs") or []
    scored = scorer.score_chunks(state["query"], docs)
    scores = [d.get("relevance_score", 0.0) for d in scored]
    return {**state, "reranked_docs": scored, "relevance_scores": scores}


# ---------------------------------------------------------------------------
# Node: generate
# ---------------------------------------------------------------------------

def _generate(state: RAGState) -> RAGState:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage

    # Use reranked docs if available, else fall back to retrieved
    docs = state.get("reranked_docs") or state.get("retrieved_docs") or []
    query = state["query"]

    if not docs:
        return {
            **state,
            "response": (
                "I couldn't find relevant research papers on that topic in the platform. "
                "Try rephrasing your question, or more papers may need to be uploaded and approved."
            ),
            "sources": [],
        }

    # Retrieval Confidence Gate — warn when average chunk relevance is low
    relevance_scores = state.get("relevance_scores") or []
    avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 1.0
    _LOW_CONFIDENCE_THRESHOLD = 0.35
    low_confidence = avg_relevance < _LOW_CONFIDENCE_THRESHOLD

    context = "\n\n---\n\n".join(doc.get("content", "") for doc in docs if doc.get("content"))
    sources = _build_sources(docs)

    system_prompt = (
        "You are Yggdrasil, an AI research assistant for the Orravyn research platform. "
        "Answer the researcher's question using only the provided context excerpts from "
        "research papers stored on the platform. "
        "Be precise and academic. Cite specific claims when the context supports it. "
        "If the context does not contain enough information to answer fully, say so clearly "
        "rather than speculating. Do not fabricate facts or references."
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=f"Context from research papers:\n\n{context}\n\nResearcher's question: {query}"
        ),
    ]

    try:
        llm = ChatOpenAI(model="gpt-4o-mini", max_tokens=1024)
        reply = llm.invoke(messages)
        response_text = reply.content
        if low_confidence:
            response_text = (
                f"⚠️ **Limited evidence** (avg. chunk relevance {avg_relevance:.2f} < {_LOW_CONFIDENCE_THRESHOLD}): "
                "The retrieved context may not be closely related to your query. "
                "The following answer should be treated with caution.\n\n"
            ) + response_text
        return {**state, "response": response_text, "sources": sources}
    except Exception as exc:
        logger.error("LLM generation failed: %s", exc)
        return {
            **state,
            "response": "I encountered an error generating a response. Please try again shortly.",
            "sources": [],
        }


# ---------------------------------------------------------------------------
# Node: verify_citations  (Self-RAG — Option 6)
# ---------------------------------------------------------------------------

def _verify_citations(state: RAGState) -> RAGState:
    from .self_reflective import CitationFaithfulnessVerifier
    docs = state.get("reranked_docs") or state.get("retrieved_docs") or []
    if not docs or not state.get("response"):
        return {**state, "faithfulness_score": 1.0}
    verifier = CitationFaithfulnessVerifier()
    result = verifier.verify(state["response"], docs)
    return {**state, "faithfulness_score": result.get("faithfulness_score", 1.0)}


# ---------------------------------------------------------------------------
# Conditional routing
# ---------------------------------------------------------------------------

def _route_retrieval(state: RAGState) -> str:
    """If retrieval is not needed, skip directly to generation."""
    if state.get("needs_retrieval", True):
        return "decompose_query"
    return "generate"


# ---------------------------------------------------------------------------
# Graph construction (lazy singleton)
# ---------------------------------------------------------------------------

_rag_graph = None


def _build_graph():
    from langgraph.graph import END, StateGraph

    graph = StateGraph(RAGState)

    # Register nodes
    graph.add_node("decide_retrieval", _decide_retrieval)
    graph.add_node("decompose_query", _decompose_query)
    graph.add_node("hybrid_retrieve", _hybrid_retrieve)
    graph.add_node("rerank", _rerank)
    graph.add_node("score_chunks", _score_chunks)
    graph.add_node("generate", _generate)
    graph.add_node("verify_citations", _verify_citations)

    # Entry point
    graph.set_entry_point("decide_retrieval")

    # Conditional branch: retrieve or skip
    graph.add_conditional_edges(
        "decide_retrieval",
        _route_retrieval,
        {
            "decompose_query": "decompose_query",
            "generate": "generate",
        },
    )

    # Retrieval path
    graph.add_edge("decompose_query", "hybrid_retrieve")
    graph.add_edge("hybrid_retrieve", "rerank")
    graph.add_edge("rerank", "score_chunks")
    graph.add_edge("score_chunks", "generate")

    # Final path
    graph.add_edge("generate", "verify_citations")
    graph.add_edge("verify_citations", END)

    return graph.compile()


def _get_graph():
    global _rag_graph
    if _rag_graph is None:
        _rag_graph = _build_graph()
    return _rag_graph


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def query_rag(user_query: str) -> dict:
    """
    Run the HA-RAG + Self-RAG pipeline for a user query.

    Returns:
        {
            "response": str,
            "sources": [{"paper_id": int, "title": str, "authors": str}, ...],
            "faithfulness_score": float,   # 0.0–1.0
        }
    """
    from .efficiency_tracker import get_tracker
    import time
    _t0 = time.perf_counter()

    graph = _get_graph()
    result = graph.invoke(
        {
            "query": user_query,
            "response": "",
            "sources": [],
            "sub_queries": [],
            "retrieved_docs": [],
            "reranked_docs": [],
            "needs_retrieval": True,
            "relevance_scores": [],
            "faithfulness_score": 1.0,
        }
    )
    elapsed_ms = (time.perf_counter() - _t0) * 1000
    get_tracker().record_query(elapsed_ms)
    get_tracker().record_stage("rag_pipeline", elapsed_ms)

    return {
        "response": result["response"],
        "sources": result["sources"],
        "faithfulness_score": result.get("faithfulness_score", 1.0),
    }
