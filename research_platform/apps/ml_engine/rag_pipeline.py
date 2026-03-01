"""
LangGraph RAG pipeline for Yggdrasil AI chatbot.

Graph:  retrieve  →  generate  →  END

- retrieve : semantic search over ChromaDB paper chunks
- generate : call Claude Haiku with retrieved context
"""
import logging
from typing import List, TypedDict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------

class RAGState(TypedDict):
    query: str
    retrieved_docs: List[dict]
    response: str
    sources: List[dict]


# ---------------------------------------------------------------------------
# Node: retrieve
# ---------------------------------------------------------------------------

def _retrieve(state: RAGState) -> RAGState:
    from .vector_store import search_papers

    docs = search_papers(state["query"], n_results=5)
    return {**state, "retrieved_docs": docs}


# ---------------------------------------------------------------------------
# Node: generate
# ---------------------------------------------------------------------------

def _generate(state: RAGState) -> RAGState:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage

    docs = state["retrieved_docs"]
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

    # Build context and deduplicated sources list
    context = "\n\n---\n\n".join(doc["content"] for doc in docs)
    seen_ids: set = set()
    sources: List[dict] = []
    for doc in docs:
        pid = doc["metadata"].get("paper_id")
        if pid and pid not in seen_ids:
            seen_ids.add(pid)
            sources.append(
                {
                    "paper_id": pid,
                    "title": doc["metadata"].get("title", "Unknown Paper"),
                    "authors": doc["metadata"].get("authors", ""),
                }
            )

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
        return {**state, "response": reply.content, "sources": sources}
    except Exception as exc:
        logger.error("LLM generation failed: %s", exc)
        return {
            **state,
            "response": "I encountered an error generating a response. Please try again shortly.",
            "sources": [],
        }


# ---------------------------------------------------------------------------
# Graph construction (lazy singleton)
# ---------------------------------------------------------------------------

_rag_graph = None


def _build_graph():
    from langgraph.graph import END, StateGraph

    graph = StateGraph(RAGState)
    graph.add_node("retrieve", _retrieve)
    graph.add_node("generate", _generate)
    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)
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
    Run the RAG pipeline for a user query.

    Returns:
        {
            "response": str,
            "sources": [{"paper_id": int, "title": str, "authors": str}, ...]
        }
    """
    graph = _get_graph()
    result = graph.invoke(
        {
            "query": user_query,
            "retrieved_docs": [],
            "response": "",
            "sources": [],
        }
    )
    return {"response": result["response"], "sources": result["sources"]}
