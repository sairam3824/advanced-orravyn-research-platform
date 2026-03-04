"""
Multi-Agent Research Orchestration System (Option 5 — Full Implementation).

Eight specialised agents orchestrated by ResearchOrchestrator:

  ┌─────────────────────────────────────────────────────────────────────┐
  │                     ResearchOrchestrator                            │
  │                                                                     │
  │  MemoryAgent ──► PlannerAgent ──► [PARALLEL RETRIEVAL] ──────────  │
  │                                    │  WebSearchAgent  (SerpAPI)    │
  │                                    │  ArXivAgent      (arXiv API)  │
  │                                    │  PlatformAgent   (SR-MAR)     │
  │                                    │  CitationAgent   (Semantic Scholar) │
  │                                    └─────────────────────────────  │
  │                                         ▼                          │
  │                                    CriticAgent                     │
  │                                         ▼                          │
  │                                    SynthesizerAgent                │
  │                                         ▼                          │
  │                                    MemoryAgent (save turn)         │
  └─────────────────────────────────────────────────────────────────────┘

Usage
-----
    from apps.ml_engine.research_agents import get_research_orchestrator

    result = get_research_orchestrator().research(
        query="What are the recent advances in protein folding?",
        user_id=42,
        session_id="abc123",
    )
    # → {
    #     "response": str,       structured Background/Findings/Gaps/Future Work
    #     "sources":  list,      platform + web + arXiv sources
    #     "plan":     dict,      research plan used
    #     "agent_log": list,     per-agent timing/status
    #   }
"""
import logging
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SERPAPI_KEY = os.environ.get(
    "SERPAPI_KEY",
    "c5da407ce5fcaece9383c741d577c8c0cf49523ed7204124b12b0b58fb14b1b4",
)
SERPAPI_URL = "https://serpapi.com/search.json"

SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
ARXIV_API_URL        = "http://export.arxiv.org/api/query"

MAX_WORKERS   = 4    # parallel retrieval threads
WEB_RESULTS   = 8    # SerpAPI results to fetch
ARXIV_RESULTS = 8    # arXiv results to fetch
CITATION_EXPAND = 5  # how many papers to expand via Semantic Scholar
CRITIC_THRESHOLD = 0.50   # minimum composite score for a chunk to survive
SOURCE_RELEVANCE_FLOOR = 0.35  # hard minimum raw relevance — chunks below this are never shown as sources


# ---------------------------------------------------------------------------
# Agent 1 — MemoryAgent
# ---------------------------------------------------------------------------

class MemoryAgent:
    """
    Persists multi-turn research sessions in the database.

    Each session is a JSON list of {"role": "user"|"assistant", "content": str} turns.
    The last N turns are injected into the Planner's context window.
    """

    MAX_CONTEXT_TURNS = 6

    def load_context(self, session_id: Optional[str]) -> List[Dict]:
        """Load prior turns for the given session_id. Returns [] if new session."""
        if not session_id:
            return []
        try:
            from apps.chat.models import ResearchSession
            obj = ResearchSession.objects.filter(session_id=session_id).first()
            if obj:
                return (obj.turns or [])[-self.MAX_CONTEXT_TURNS * 2:]
        except Exception as exc:
            logger.warning("MemoryAgent.load_context failed: %s", exc)
        return []

    def save_turn(self, session_id: str, query: str, response: str) -> None:
        """Append a user/assistant turn pair to the session."""
        try:
            from apps.chat.models import ResearchSession
            obj, _ = ResearchSession.objects.get_or_create(session_id=session_id)
            turns = list(obj.turns or [])
            turns.append({"role": "user",      "content": query})
            turns.append({"role": "assistant",  "content": response[:2000]})
            obj.turns = turns[-40:]  # keep last 20 turn-pairs
            obj.save(update_fields=["turns", "updated_at"])
        except Exception as exc:
            logger.warning("MemoryAgent.save_turn failed: %s", exc)


# ---------------------------------------------------------------------------
# Agent 2 — PlannerAgent
# ---------------------------------------------------------------------------

class PlannerAgent:
    """
    Decomposes a research question into a structured plan using chain-of-thought.

    Returns a ResearchPlan dict:
        {
            "sub_questions":    [str, ...],    # 2-4 atomic questions
            "search_targets":   [str, ...],    # keyword queries for retrieval agents
            "approach":         str,            # 1-sentence synthesis strategy
        }
    """

    _PROMPT = """You are a senior research planning assistant.

Given the researcher's question and any prior conversation context, produce a structured research plan.

Respond ONLY as JSON with this exact structure:
{{
  "sub_questions": ["<sub-question 1>", "<sub-question 2>", "..."],
  "search_targets": ["<keyword query 1>", "<keyword query 2>", "..."],
  "approach": "<one sentence describing how to synthesise the retrieved evidence>"
}}

Rules:
- sub_questions: 2 to 4 atomic research questions derived from the main question
- search_targets: 2 to 4 short keyword-style queries optimised for database/web search
- approach: how a researcher would combine findings to answer the original question
- No markdown fences, no extra keys, valid JSON only
"""

    def plan(self, query: str, context: List[Dict]) -> Dict:
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import HumanMessage, SystemMessage
            import json, re

            context_str = ""
            if context:
                context_str = "\n\nPrior conversation context:\n" + "\n".join(
                    f"  [{t['role']}]: {t['content'][:200]}" for t in context[-4:]
                )

            llm = ChatOpenAI(model="gpt-4o-mini", max_tokens=512)
            reply = llm.invoke([
                SystemMessage(content=self._PROMPT),
                HumanMessage(content=f"Research question: {query}{context_str}"),
            ])
            raw = reply.content.strip()
            raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw).rstrip("`").strip()
            plan = json.loads(raw)
            logger.info("PlannerAgent: %d sub-questions, %d search targets",
                        len(plan.get("sub_questions", [])), len(plan.get("search_targets", [])))
            return plan
        except Exception as exc:
            logger.warning("PlannerAgent failed (%s); falling back to single query.", exc)
            return {
                "sub_questions":  [query],
                "search_targets": [query],
                "approach": "Directly retrieve and summarise evidence for the query.",
            }


# ---------------------------------------------------------------------------
# Agent 3 — WebSearchAgent  (SerpAPI — Google Scholar engine)
# ---------------------------------------------------------------------------

class WebSearchAgent:
    """
    Searches the web via SerpAPI (Google Scholar engine) for recent papers
    and articles related to the query.
    """

    def search(self, queries: List[str], n_per_query: int = WEB_RESULTS) -> List[Dict]:
        results = []
        for query in queries[:2]:   # limit API calls
            try:
                params = {
                    "engine":  "google_scholar",
                    "q":       query,
                    "api_key": SERPAPI_KEY,
                    "num":     n_per_query,
                }
                resp = requests.get(SERPAPI_URL, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                for item in data.get("organic_results", [])[:n_per_query]:
                    results.append({
                        "content":  (item.get("snippet") or item.get("title", ""))[:800],
                        "title":    item.get("title", ""),
                        "url":      item.get("link", ""),
                        "source":   "web_search",
                        "metadata": {
                            "title":  item.get("title", ""),
                            "source": "Google Scholar (SerpAPI)",
                            "url":    item.get("link", ""),
                        },
                    })
            except Exception as exc:
                logger.warning("WebSearchAgent: query '%s' failed: %s", query[:40], exc)
        logger.info("WebSearchAgent: retrieved %d results", len(results))
        return results


# ---------------------------------------------------------------------------
# Agent 4 — ArXivAgent
# ---------------------------------------------------------------------------

class ArXivAgent:
    """
    Searches the arXiv preprint server for recent scientific papers.
    Uses the arXiv Atom API (no key required).
    """

    def search(self, queries: List[str], n_per_query: int = ARXIV_RESULTS) -> List[Dict]:
        results = []
        for query in queries[:2]:
            try:
                params = {
                    "search_query": f"all:{query}",
                    "start":        0,
                    "max_results":  n_per_query,
                    "sortBy":       "relevance",
                    "sortOrder":    "descending",
                }
                resp = requests.get(ARXIV_API_URL, params=params, timeout=12)
                resp.raise_for_status()
                self._parse_atom(resp.text, results)
            except Exception as exc:
                logger.warning("ArXivAgent: query '%s' failed: %s", query[:40], exc)
        logger.info("ArXivAgent: retrieved %d results", len(results))
        return results

    @staticmethod
    def _parse_atom(xml_text: str, out: List[Dict]) -> None:
        import xml.etree.ElementTree as ET
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        try:
            root = ET.fromstring(xml_text)
            for entry in root.findall("atom:entry", ns):
                title   = (entry.findtext("atom:title",   "", ns) or "").strip()
                summary = (entry.findtext("atom:summary", "", ns) or "").strip()
                link_el = entry.find("atom:id", ns)
                url     = link_el.text.strip() if link_el is not None else ""
                authors = [
                    a.findtext("atom:name", "", ns)
                    for a in entry.findall("atom:author", ns)
                ]
                out.append({
                    "content":  f"{title}. {summary[:600]}",
                    "title":    title,
                    "url":      url,
                    "source":   "arxiv",
                    "metadata": {
                        "title":   title,
                        "authors": ", ".join(authors[:3]),
                        "source":  "arXiv",
                        "url":     url,
                    },
                })
        except Exception as exc:
            logger.warning("ArXivAgent._parse_atom: %s", exc)


# ---------------------------------------------------------------------------
# Agent 5 — PlatformAgent  (wraps existing SR-MAR)
# ---------------------------------------------------------------------------

class PlatformAgent:
    """
    Retrieves from the platform's own paper database using the existing
    SR-MAR (Section-Routed Multi-Agent Retrieval) pipeline.
    """

    def search(self, queries: List[str], n_per_query: int = 10) -> List[Dict]:
        try:
            from apps.ml_engine.multi_agent_retrieval import get_orchestrator
            orchestrator = get_orchestrator()
            results = []
            for query in queries:
                chunks = orchestrator.search(query, n_results=n_per_query)
                for c in chunks:
                    c["source"] = "platform"
                results.extend(chunks)
            # Deduplicate by content hash
            seen, deduped = set(), []
            for r in results:
                key = r.get("content", "")[:80]
                if key not in seen:
                    seen.add(key)
                    deduped.append(r)
            logger.info("PlatformAgent: retrieved %d unique chunks", len(deduped))
            return deduped
        except Exception as exc:
            logger.warning("PlatformAgent failed: %s", exc)
            return []


# ---------------------------------------------------------------------------
# Agent 6 — CitationAgent  (Semantic Scholar free API)
# ---------------------------------------------------------------------------

class CitationAgent:
    """
    Given the titles of top retrieved papers, fetches their highly-cited
    references and citing papers via the Semantic Scholar free API.
    Expands the evidence pool with closely related foundational work.
    """

    def expand(self, chunks: List[Dict], n_expand: int = CITATION_EXPAND) -> List[Dict]:
        titles = [
            c["metadata"].get("title", "")
            for c in chunks
            if c.get("metadata", {}).get("title")
        ][:n_expand]

        expanded = []
        for title in titles:
            try:
                resp = requests.get(
                    SEMANTIC_SCHOLAR_URL,
                    params={
                        "query":  title,
                        "fields": "title,abstract,authors,year,citationCount",
                        "limit":  3,
                    },
                    timeout=8,
                )
                resp.raise_for_status()
                for paper in resp.json().get("data", []):
                    abstract = paper.get("abstract") or ""
                    if not abstract:
                        continue
                    expanded.append({
                        "content": f"{paper.get('title','')}. {abstract[:600]}",
                        "source":  "semantic_scholar",
                        "metadata": {
                            "title":   paper.get("title", ""),
                            "authors": ", ".join(
                                a.get("name", "") for a in (paper.get("authors") or [])[:3]
                            ),
                            "year":    paper.get("year"),
                            "citations": paper.get("citationCount", 0),
                            "source":  "Semantic Scholar",
                        },
                    })
            except Exception as exc:
                logger.debug("CitationAgent expand failed for '%s': %s", title[:40], exc)

        logger.info("CitationAgent: expanded with %d papers", len(expanded))
        return expanded


# ---------------------------------------------------------------------------
# Agent 7 — CriticAgent
# ---------------------------------------------------------------------------

class CriticAgent:
    """
    Evaluates all retrieved evidence chunks for relevance, recency, and
    credibility. Filters out low-quality chunks and scores survivors.

    Scoring (0.0–1.0 per chunk):
      - Relevance:  cross-encoder similarity to query
      - Recency:    1.0 for arXiv/web (assume recent), 0.8 for platform
      - Credibility: 1.0 for platform/arXiv, 0.9 for Semantic Scholar,
                     0.7 for web_search

    Final score = 0.6×relevance + 0.2×recency + 0.2×credibility
    Chunks below CRITIC_THRESHOLD are flagged and excluded from synthesis.
    """

    _CREDIBILITY = {
        "platform":         1.0,
        "arxiv":            1.0,
        "semantic_scholar": 0.9,
        "web_search":       0.7,
    }
    _RECENCY = {
        "platform":         0.8,
        "arxiv":            1.0,
        "semantic_scholar": 0.9,
        "web_search":       1.0,
    }

    def evaluate(self, query: str, chunks: List[Dict]) -> List[Dict]:
        if not chunks:
            return []
        try:
            from apps.ml_engine.reranker import get_reranker
            reranker = get_reranker()
            texts = [c.get("content", "") for c in chunks]
            scores = reranker._get_model().predict(
                [(query, t[:512]) for t in texts]
            )
            import numpy as np
            from scipy.special import expit as sigmoid
            rel_scores = sigmoid(scores).tolist()
        except Exception:
            rel_scores = [0.5] * len(chunks)

        evaluated = []
        for chunk, rel in zip(chunks, rel_scores):
            source = chunk.get("source", "platform")
            cred   = self._CREDIBILITY.get(source, 0.7)
            rec    = self._RECENCY.get(source, 0.8)
            # Relevance weight raised to 0.75 so recency/credibility cannot
            # prop up topically irrelevant chunks above the threshold.
            final  = 0.75 * rel + 0.15 * rec + 0.10 * cred
            chunk  = dict(chunk)
            chunk["critic_score"]    = round(float(final), 4)
            chunk["relevance_score"] = round(float(rel), 4)
            if final >= CRITIC_THRESHOLD:
                evaluated.append(chunk)
            else:
                logger.debug("CriticAgent: dropped chunk (score=%.3f): %s", final, chunk.get("content","")[:60])

        evaluated.sort(key=lambda c: c["critic_score"], reverse=True)
        logger.info("CriticAgent: %d/%d chunks passed quality filter", len(evaluated), len(chunks))
        return evaluated


# ---------------------------------------------------------------------------
# Agent 8 — SynthesizerAgent
# ---------------------------------------------------------------------------

class SynthesizerAgent:
    """
    Generates a structured research summary from evaluated evidence.

    Output sections (IMRaD-inspired):
      Background       — what is known / prior work
      Key Findings     — what the evidence reveals about the query
      Research Gaps    — what remains unanswered
      Future Directions — suggested next research steps

    Each claim is inline-cited to a source chunk.
    """

    _SYSTEM = """You are Yggdrasil, a senior research synthesis assistant for the Orravyn platform.

You have been given evidence chunks retrieved from multiple sources:
  - Platform papers (peer-reviewed)
  - arXiv preprints
  - Google Scholar results
  - Semantic Scholar citations

Your task: write a structured research synthesis with the following sections:

## Background
## Key Findings
## Research Gaps
## Future Directions

Rules:
- Be precise, academic, and concise (total ~400 words)
- Cite sources inline as [Platform: <title>], [arXiv: <title>], [Web: <title>]
- If evidence is insufficient for a section, explicitly say so — do not fabricate
- Do NOT invent paper titles, authors, or statistics not present in the context
"""

    def synthesize(self, query: str, chunks: List[Dict], context: List[Dict]) -> str:
        if not chunks:
            return (
                "Insufficient evidence was retrieved to answer this research question.\n\n"
                "**Suggestion:** Try rephrasing the query or uploading more papers to the platform."
            )
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import HumanMessage, SystemMessage

            evidence_text = self._format_evidence(chunks[:15])
            context_str   = self._format_context(context)

            llm   = ChatOpenAI(model="gpt-4o-mini", max_tokens=1200)
            reply = llm.invoke([
                SystemMessage(content=self._SYSTEM),
                HumanMessage(content=(
                    f"Research question: {query}\n\n"
                    f"{context_str}"
                    f"Evidence:\n\n{evidence_text}"
                )),
            ])
            return reply.content
        except Exception as exc:
            logger.error("SynthesizerAgent failed: %s", exc)
            return "An error occurred during synthesis. Please try again."

    @staticmethod
    def _format_evidence(chunks: List[Dict]) -> str:
        parts = []
        for i, c in enumerate(chunks, 1):
            src   = c.get("source", "platform")
            title = c.get("metadata", {}).get("title", f"Source {i}")
            label = {"platform": "Platform", "arxiv": "arXiv",
                     "web_search": "Web", "semantic_scholar": "Scholar"}.get(src, src)
            parts.append(f"[{label}: {title}]\n{c.get('content','')[:500]}")
        return "\n\n---\n\n".join(parts)

    @staticmethod
    def _format_context(context: List[Dict]) -> str:
        if not context:
            return ""
        lines = [f"  [{t['role']}]: {t['content'][:150]}" for t in context[-4:]]
        return "Prior conversation:\n" + "\n".join(lines) + "\n\n"


# ---------------------------------------------------------------------------
# ResearchOrchestrator — coordinates all 8 agents
# ---------------------------------------------------------------------------

class ResearchOrchestrator:
    """
    Orchestrates the full 8-agent research pipeline.

    Pipeline:
      MemoryAgent.load → PlannerAgent → [WebSearch ∥ arXiv ∥ Platform ∥ Citation]
                       → CriticAgent → SynthesizerAgent → MemoryAgent.save
    """

    def __init__(self):
        self.memory      = MemoryAgent()
        self.planner     = PlannerAgent()
        self.web_search  = WebSearchAgent()
        self.arxiv       = ArXivAgent()
        self.platform    = PlatformAgent()
        self.citation    = CitationAgent()
        self.critic      = CriticAgent()
        self.synthesizer = SynthesizerAgent()

    def research(
        self,
        query: str,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> Dict:
        """
        Run the full multi-agent research pipeline.

        Args:
            query:      The researcher's question.
            user_id:    Optional user ID for personalisation (future use).
            session_id: Optional session ID for multi-turn memory.

        Returns:
            {
                "response":   str,   structured synthesis
                "sources":    list,  deduplicated source list
                "plan":       dict,  research plan
                "agent_log":  list,  per-agent timing info
            }
        """
        t_start   = time.perf_counter()
        agent_log = []
        auto_session = session_id or str(uuid.uuid4())

        def timed(name, fn, *args, **kwargs):
            t0 = time.perf_counter()
            result = fn(*args, **kwargs)
            elapsed = round((time.perf_counter() - t0) * 1000, 1)
            agent_log.append({"agent": name, "latency_ms": elapsed,
                               "n_results": len(result) if isinstance(result, list) else 1})
            logger.info("%s: done in %.0f ms", name, elapsed)
            return result

        # ── 1. Load session memory ─────────────────────────────────────────
        context = timed("MemoryAgent(load)", self.memory.load_context, session_id)

        # ── 2. Plan ────────────────────────────────────────────────────────
        plan = timed("PlannerAgent", self.planner.plan, query, context)
        search_targets = plan.get("search_targets", [query])

        # ── 3. Parallel retrieval ──────────────────────────────────────────
        all_chunks: List[Dict] = []
        retrieval_tasks = {
            "WebSearchAgent":   lambda: self.web_search.search(search_targets),
            "ArXivAgent":       lambda: self.arxiv.search(search_targets),
            "PlatformAgent":    lambda: self.platform.search(search_targets),
        }
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(fn): name for name, fn in retrieval_tasks.items()}
            for future in as_completed(futures):
                name   = futures[future]
                t0     = time.perf_counter()
                try:
                    chunks = future.result()
                    elapsed = round((time.perf_counter() - t0) * 1000, 1)
                    agent_log.append({"agent": name, "latency_ms": elapsed,
                                      "n_results": len(chunks)})
                    logger.info("%s: %d results in %.0f ms", name, len(chunks), elapsed)
                    all_chunks.extend(chunks)
                except Exception as exc:
                    logger.error("%s raised: %s", name, exc)

        # ── 4. Citation expansion ──────────────────────────────────────────
        citation_chunks = timed("CitationAgent", self.citation.expand, all_chunks)
        all_chunks.extend(citation_chunks)

        # ── 5. Critic filtering ────────────────────────────────────────────
        filtered = timed("CriticAgent", self.critic.evaluate, query, all_chunks)

        # ── 6. Synthesis ───────────────────────────────────────────────────
        response = timed("SynthesizerAgent", self.synthesizer.synthesize,
                         query, filtered, context)

        # ── 7. Save to memory ──────────────────────────────────────────────
        self.memory.save_turn(auto_session, query, response)
        agent_log.append({"agent": "MemoryAgent(save)", "latency_ms": 0, "n_results": 1})

        # ── 8. Build sources list ──────────────────────────────────────────
        sources = self._build_sources(filtered)

        total_ms = round((time.perf_counter() - t_start) * 1000, 1)
        logger.info(
            "ResearchOrchestrator: total=%.0f ms | chunks=%d → filtered=%d | sources=%d",
            total_ms, len(all_chunks), len(filtered), len(sources),
        )

        return {
            "response":   response,
            "sources":    sources,
            "plan":       plan,
            "agent_log":  agent_log,
            "session_id": auto_session,
            "total_ms":   total_ms,
        }

    @staticmethod
    def _build_sources(chunks: List[Dict]) -> List[Dict]:
        seen, sources = set(), []
        # Sort by critic_score descending so the most relevant appear first
        for c in sorted(chunks, key=lambda x: x.get("critic_score", 0), reverse=True):
            # Hard relevance floor: never surface sources that are topically unrelated
            if c.get("relevance_score", 1.0) < SOURCE_RELEVANCE_FLOOR:
                continue
            meta  = c.get("metadata", {})
            title = meta.get("title", "")
            url   = meta.get("url", "")
            key   = title or url
            if key and key not in seen:
                seen.add(key)
                sources.append({
                    "title":   title,
                    "source":  c.get("source", "platform"),
                    "url":     url,
                    "authors": meta.get("authors", ""),
                    "year":    meta.get("year", ""),
                })
        return sources[:12]  # cap at 12; quality over quantity


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_orchestrator: Optional[ResearchOrchestrator] = None


def get_research_orchestrator() -> ResearchOrchestrator:
    """Return the module-level ResearchOrchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ResearchOrchestrator()
    return _orchestrator


# ---------------------------------------------------------------------------
# Enhanced ResearchOrchestrator with New Features
# ---------------------------------------------------------------------------

class EnhancedResearchOrchestrator(ResearchOrchestrator):
    """
    Enhanced orchestrator with:
    1. Cross-Agent Debate
    2. Temporal Evolution Tracking
    3. Explainability
    4. Adversarial Robustness
    """
    
    def __init__(self):
        super().__init__()
        
        # Import new modules
        from apps.ml_engine.agent_debate import get_debate_orchestrator
        from apps.ml_engine.temporal_tracker import get_temporal_analyzer
        from apps.ml_engine.explainability import get_decision_tracker
        
        self.debate_orchestrator = get_debate_orchestrator()
        self.temporal_analyzer = get_temporal_analyzer()
        self.decision_tracker = get_decision_tracker()
    
    def research(
        self,
        query: str,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        enable_debate: bool = True,
        enable_temporal: bool = True,
        enable_explainability: bool = True,
    ) -> Dict:
        """
        Enhanced research with debate, temporal analysis, and explainability.
        
        Args:
            query: Research question
            user_id: Optional user ID
            session_id: Optional session ID for multi-turn
            enable_debate: Enable cross-agent debate on conflicts
            enable_temporal: Enable temporal scoring
            enable_explainability: Enable decision tracking
            
        Returns:
            Enhanced result dict with debate transcript, temporal analysis, explanations
        """
        t_start = time.perf_counter()
        agent_log = []
        auto_session = session_id or str(uuid.uuid4())
        query_id = f"q_{uuid.uuid4().hex[:8]}"
        
        # Start explainability tracking
        if enable_explainability:
            self.decision_tracker.start_tracking(
                query_id=query_id,
                query=query,
                metadata={"session_id": auto_session, "user_id": user_id}
            )
        
        def timed(name, fn, *args, **kwargs):
            t0 = time.perf_counter()
            result = fn(*args, **kwargs)
            elapsed = round((time.perf_counter() - t0) * 1000, 1)
            agent_log.append({
                "agent": name,
                "latency_ms": elapsed,
                "n_results": len(result) if isinstance(result, list) else 1
            })
            logger.info("%s: done in %.0f ms", name, elapsed)
            
            # Log decision
            if enable_explainability:
                self.decision_tracker.log_decision(
                    query_id=query_id,
                    agent=name,
                    decision="execute",
                    reasoning=f"Executed {name}",
                    confidence=0.9,
                    metadata={"latency_ms": elapsed}
                )
            
            return result
        
        # ── 1. Load session memory ─────────────────────────────────────────
        context = timed("MemoryAgent(load)", self.memory.load_context, session_id)
        
        # ── 2. Plan ────────────────────────────────────────────────────────
        plan = timed("PlannerAgent", self.planner.plan, query, context)
        search_targets = plan.get("search_targets", [query])
        
        # ── 3. Parallel retrieval ──────────────────────────────────────────
        agent_outputs = {}  # Track outputs by agent for debate
        
        retrieval_tasks = {
            "WebSearchAgent": lambda: self.web_search.search(search_targets),
            "ArXivAgent": lambda: self.arxiv.search(search_targets),
            "PlatformAgent": lambda: self.platform.search(search_targets),
        }
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(fn): name for name, fn in retrieval_tasks.items()}
            for future in as_completed(futures):
                name = futures[future]
                t0 = time.perf_counter()
                try:
                    chunks = future.result()
                    elapsed = round((time.perf_counter() - t0) * 1000, 1)
                    agent_log.append({
                        "agent": name,
                        "latency_ms": elapsed,
                        "n_results": len(chunks)
                    })
                    logger.info("%s: %d results in %.0f ms", name, len(chunks), elapsed)
                    
                    # Store for debate
                    agent_outputs[name] = chunks
                    
                    # Log retrieval
                    if enable_explainability:
                        self.decision_tracker.log_retrieval(
                            query_id=query_id,
                            agent=name,
                            source=name,
                            chunks_retrieved=len(chunks),
                            top_chunk_ids=[
                                str(c.get("id", "")) for c in chunks[:5]
                            ]
                        )
                    
                except Exception as exc:
                    logger.error("%s raised: %s", name, exc)
                    agent_outputs[name] = []
        
        # ── 4. Cross-Agent Debate (NEW) ────────────────────────────────────
        debate_result = None
        if enable_debate and len(agent_outputs) > 1:
            t0 = time.perf_counter()
            debate_result = self.debate_orchestrator.debate(
                query=query,
                agent_outputs=agent_outputs
            )
            elapsed = round((time.perf_counter() - t0) * 1000, 1)
            agent_log.append({
                "agent": "DebateOrchestrator",
                "latency_ms": elapsed,
                "n_results": 1,
                "has_conflicts": debate_result.get("has_conflicts", False)
            })
            logger.info(
                "DebateOrchestrator: %s in %.0f ms",
                "conflicts detected" if debate_result["has_conflicts"] else "no conflicts",
                elapsed
            )
            
            # Use debate-filtered evidence
            all_chunks = debate_result.get("final_evidence", [])
        else:
            # No debate: merge all
            all_chunks = []
            for chunks in agent_outputs.values():
                all_chunks.extend(chunks)
        
        # ── 5. Citation expansion ──────────────────────────────────────────
        citation_chunks = timed("CitationAgent", self.citation.expand, all_chunks)
        all_chunks.extend(citation_chunks)
        
        # ── 6. Temporal Scoring (NEW) ──────────────────────────────────────
        if enable_temporal:
            t0 = time.perf_counter()
            all_chunks = self.temporal_analyzer.apply_temporal_scoring(
                query=query,
                chunks=all_chunks,
                mode="auto"
            )
            elapsed = round((time.perf_counter() - t0) * 1000, 1)
            agent_log.append({
                "agent": "TemporalAnalyzer",
                "latency_ms": elapsed,
                "n_results": len(all_chunks)
            })
            logger.info("TemporalAnalyzer: scored %d chunks in %.0f ms", len(all_chunks), elapsed)
        
        # ── 7. Critic filtering ────────────────────────────────────────────
        filtered = timed("CriticAgent", self.critic.evaluate, query, all_chunks)
        
        # ── 8. Synthesis ───────────────────────────────────────────────────
        response = timed("SynthesizerAgent", self.synthesizer.synthesize,
                         query, filtered, context)
        
        # ── 9. Save to memory ──────────────────────────────────────────────
        self.memory.save_turn(auto_session, query, response)
        agent_log.append({"agent": "MemoryAgent(save)", "latency_ms": 0, "n_results": 1})
        
        # ── 10. Build sources list ─────────────────────────────────────────
        sources = self._build_sources(filtered)
        
        # ── 11. End explainability tracking (NEW) ──────────────────────────
        explanation = None
        if enable_explainability:
            explanation = self.decision_tracker.end_tracking(
                query_id=query_id,
                final_response=response,
                sources=sources
            )
        
        total_ms = round((time.perf_counter() - t_start) * 1000, 1)
        logger.info(
            "EnhancedResearchOrchestrator: total=%.0f ms | chunks=%d → filtered=%d | sources=%d",
            total_ms, len(all_chunks), len(filtered), len(sources),
        )
        
        # Build enhanced result
        result = {
            "response": response,
            "sources": sources,
            "plan": plan,
            "agent_log": agent_log,
            "session_id": auto_session,
            "total_ms": total_ms,
        }
        
        # Add new features
        if debate_result:
            result["debate"] = {
                "has_conflicts": debate_result.get("has_conflicts", False),
                "conflicts": debate_result.get("conflicts", []),
                "transcript": debate_result.get("debate_transcript", []),
                "consensus": debate_result.get("consensus", {})
            }
        
        if explanation:
            result["explanation"] = explanation
        
        # Add temporal analysis summary
        if enable_temporal and filtered:
            temporal_summary = {
                "avg_age_years": sum(
                    c.get("age_years", 0) for c in filtered if c.get("age_years")
                ) / max(len([c for c in filtered if c.get("age_years")]), 1),
                "year_range": [
                    min(c.get("publication_year", 9999) for c in filtered if c.get("publication_year")),
                    max(c.get("publication_year", 0) for c in filtered if c.get("publication_year"))
                ],
                "temporal_mode": self.temporal_analyzer._detect_temporal_mode(query)
            }
            result["temporal_analysis"] = temporal_summary
        
        return result


# ---------------------------------------------------------------------------
# Enhanced singleton
# ---------------------------------------------------------------------------

_enhanced_orchestrator: Optional[EnhancedResearchOrchestrator] = None


def get_enhanced_research_orchestrator() -> EnhancedResearchOrchestrator:
    """Return the enhanced research orchestrator singleton."""
    global _enhanced_orchestrator
    if _enhanced_orchestrator is None:
        _enhanced_orchestrator = EnhancedResearchOrchestrator()
    return _enhanced_orchestrator
