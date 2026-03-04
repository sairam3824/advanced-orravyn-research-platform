"""
Explainable Multi-Agent Decision Visualization.

Tracks and explains agent decisions, retrieval provenance, and confidence
for transparency and debugging.

Components:
1. DecisionTracker — logs all agent decisions with reasoning
2. ProvenanceGraph — tracks where each piece of evidence came from
3. ConfidenceMapper — maps confidence scores across pipeline stages
4. CounterfactualExplainer — shows what would change if agents were removed

Usage:
    from apps.ml_engine.explainability import get_decision_tracker
    
    tracker = get_decision_tracker()
    tracker.start_tracking(query_id="q123")
    
    # During agent execution
    tracker.log_decision(
        agent="PlannerAgent",
        decision="decompose_query",
        reasoning="Query is complex with multiple sub-questions",
        confidence=0.85
    )
    
    # After execution
    explanation = tracker.get_explanation(query_id="q123")
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Decision Tracker
# ---------------------------------------------------------------------------

class DecisionTracker:
    """
    Tracks all agent decisions during query processing for explainability.
    """
    
    def __init__(self):
        self._active_sessions: Dict[str, Dict] = {}
        self._completed_sessions: Dict[str, Dict] = {}
        
    def start_tracking(
        self,
        query_id: str,
        query: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """Start tracking a new query session."""
        self._active_sessions[query_id] = {
            "query_id": query_id,
            "query": query,
            "metadata": metadata or {},
            "start_time": datetime.utcnow().isoformat(),
            "decisions": [],
            "agent_contributions": defaultdict(list),
            "timeline": []
        }
        logger.info("DecisionTracker: started tracking query_id='%s'", query_id)
    
    def log_decision(
        self,
        query_id: str,
        agent: str,
        decision: str,
        reasoning: str,
        confidence: float,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Log a single agent decision.
        
        Args:
            query_id: Query session ID
            agent: Agent name (e.g., "PlannerAgent")
            decision: Decision made (e.g., "decompose_query")
            reasoning: Why this decision was made
            confidence: Confidence score (0-1)
            metadata: Additional context
        """
        if query_id not in self._active_sessions:
            logger.warning(
                "DecisionTracker: query_id='%s' not found, skipping log.",
                query_id
            )
            return
        
        decision_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent": agent,
            "decision": decision,
            "reasoning": reasoning,
            "confidence": confidence,
            "metadata": metadata or {}
        }
        
        session = self._active_sessions[query_id]
        session["decisions"].append(decision_entry)
        session["agent_contributions"][agent].append(decision_entry)
        session["timeline"].append({
            "time": decision_entry["timestamp"],
            "event": f"{agent}: {decision}",
            "confidence": confidence
        })
        
        logger.debug(
            "DecisionTracker: logged decision for agent='%s', decision='%s'",
            agent, decision
        )
    
    def log_retrieval(
        self,
        query_id: str,
        agent: str,
        source: str,
        chunks_retrieved: int,
        top_chunk_ids: List[str],
        metadata: Optional[Dict] = None
    ) -> None:
        """Log retrieval action by an agent."""
        self.log_decision(
            query_id=query_id,
            agent=agent,
            decision="retrieve",
            reasoning=f"Retrieved {chunks_retrieved} chunks from {source}",
            confidence=1.0,
            metadata={
                "source": source,
                "chunks_retrieved": chunks_retrieved,
                "top_chunk_ids": top_chunk_ids,
                **(metadata or {})
            }
        )
    
    def end_tracking(
        self,
        query_id: str,
        final_response: str,
        sources: List[Dict]
    ) -> Dict:
        """
        End tracking and generate explanation.
        
        Returns:
            Complete explanation dict with decision tree, provenance, etc.
        """
        if query_id not in self._active_sessions:
            logger.warning(
                "DecisionTracker: query_id='%s' not found for end_tracking.",
                query_id
            )
            return {}
        
        session = self._active_sessions.pop(query_id)
        session["end_time"] = datetime.utcnow().isoformat()
        session["final_response"] = final_response
        session["sources"] = sources
        
        # Generate explanation
        explanation = self._generate_explanation(session)
        
        # Store completed session
        self._completed_sessions[query_id] = {
            "session": session,
            "explanation": explanation
        }
        
        logger.info(
            "DecisionTracker: ended tracking for query_id='%s', %d decisions logged.",
            query_id, len(session["decisions"])
        )
        
        return explanation
    
    def get_explanation(self, query_id: str) -> Optional[Dict]:
        """Retrieve explanation for a completed query."""
        if query_id in self._completed_sessions:
            return self._completed_sessions[query_id]["explanation"]
        return None
    
    def _generate_explanation(self, session: Dict) -> Dict:
        """Generate structured explanation from session data."""
        decisions = session["decisions"]
        agent_contributions = session["agent_contributions"]
        
        # Build decision tree
        decision_tree = self._build_decision_tree(decisions)
        
        # Agent contribution summary
        agent_summary = {}
        for agent, agent_decisions in agent_contributions.items():
            agent_summary[agent] = {
                "total_decisions": len(agent_decisions),
                "avg_confidence": sum(d["confidence"] for d in agent_decisions) / len(agent_decisions),
                "key_decisions": [d["decision"] for d in agent_decisions[:3]]
            }
        
        # Timeline summary
        timeline = session["timeline"]
        
        return {
            "query": session["query"],
            "decision_tree": decision_tree,
            "agent_summary": agent_summary,
            "timeline": timeline,
            "total_decisions": len(decisions),
            "duration_seconds": self._calculate_duration(
                session["start_time"],
                session.get("end_time")
            )
        }
    
    def _build_decision_tree(self, decisions: List[Dict]) -> List[Dict]:
        """Build hierarchical decision tree."""
        # Simplified: return flat list grouped by agent
        tree = []
        by_agent = defaultdict(list)
        
        for decision in decisions:
            by_agent[decision["agent"]].append({
                "decision": decision["decision"],
                "reasoning": decision["reasoning"],
                "confidence": decision["confidence"]
            })
        
        for agent, agent_decisions in by_agent.items():
            tree.append({
                "agent": agent,
                "decisions": agent_decisions
            })
        
        return tree
    
    @staticmethod
    def _calculate_duration(start: str, end: Optional[str]) -> float:
        """Calculate duration in seconds."""
        if not end:
            return 0.0
        try:
            start_dt = datetime.fromisoformat(start)
            end_dt = datetime.fromisoformat(end)
            return (end_dt - start_dt).total_seconds()
        except Exception:
            return 0.0


# ---------------------------------------------------------------------------
# 2. Provenance Graph
# ---------------------------------------------------------------------------

class ProvenanceGraph:
    """
    Tracks the provenance of each piece of evidence through the pipeline.
    """
    
    def __init__(self):
        self._graphs: Dict[str, Dict] = {}
    
    def create_graph(self, query_id: str) -> None:
        """Initialize provenance graph for a query."""
        self._graphs[query_id] = {
            "nodes": [],  # Evidence chunks
            "edges": [],  # Transformations
            "sources": defaultdict(list)  # Source -> chunks
        }
    
    def add_evidence(
        self,
        query_id: str,
        chunk_id: str,
        source_agent: str,
        content: str,
        metadata: Dict
    ) -> None:
        """Add evidence node to graph."""
        if query_id not in self._graphs:
            self.create_graph(query_id)
        
        node = {
            "id": chunk_id,
            "source_agent": source_agent,
            "content": content[:200],  # Truncate for storage
            "metadata": metadata,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        graph = self._graphs[query_id]
        graph["nodes"].append(node)
        graph["sources"][source_agent].append(chunk_id)
    
    def add_transformation(
        self,
        query_id: str,
        from_chunk_id: str,
        to_chunk_id: str,
        transformation: str,
        agent: str
    ) -> None:
        """Add transformation edge (e.g., reranking, filtering)."""
        if query_id not in self._graphs:
            return
        
        edge = {
            "from": from_chunk_id,
            "to": to_chunk_id,
            "transformation": transformation,
            "agent": agent,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self._graphs[query_id]["edges"].append(edge)
    
    def get_provenance(
        self,
        query_id: str,
        chunk_id: str
    ) -> Optional[Dict]:
        """Get full provenance chain for a specific chunk."""
        if query_id not in self._graphs:
            return None
        
        graph = self._graphs[query_id]
        
        # Find the chunk node
        chunk_node = None
        for node in graph["nodes"]:
            if node["id"] == chunk_id:
                chunk_node = node
                break
        
        if not chunk_node:
            return None
        
        # Trace back through edges
        chain = [chunk_node]
        current_id = chunk_id
        
        for edge in reversed(graph["edges"]):
            if edge["to"] == current_id:
                # Find the from node
                for node in graph["nodes"]:
                    if node["id"] == edge["from"]:
                        chain.insert(0, {
                            "node": node,
                            "transformation": edge["transformation"],
                            "agent": edge["agent"]
                        })
                        current_id = edge["from"]
                        break
        
        return {
            "chunk_id": chunk_id,
            "provenance_chain": chain,
            "source_agent": chunk_node["source_agent"]
        }
    
    def get_graph_summary(self, query_id: str) -> Optional[Dict]:
        """Get summary of provenance graph."""
        if query_id not in self._graphs:
            return None
        
        graph = self._graphs[query_id]
        
        return {
            "total_nodes": len(graph["nodes"]),
            "total_edges": len(graph["edges"]),
            "sources": {
                agent: len(chunks)
                for agent, chunks in graph["sources"].items()
            },
            "transformations": [e["transformation"] for e in graph["edges"]]
        }


# ---------------------------------------------------------------------------
# 3. Confidence Mapper
# ---------------------------------------------------------------------------

class ConfidenceMapper:
    """
    Maps confidence scores across different pipeline stages.
    """
    
    def __init__(self):
        self._confidence_maps: Dict[str, List[Dict]] = {}
    
    def record_confidence(
        self,
        query_id: str,
        stage: str,
        chunk_id: str,
        confidence: float,
        source: str
    ) -> None:
        """Record confidence score at a pipeline stage."""
        if query_id not in self._confidence_maps:
            self._confidence_maps[query_id] = []
        
        self._confidence_maps[query_id].append({
            "stage": stage,
            "chunk_id": chunk_id,
            "confidence": confidence,
            "source": source,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def get_confidence_heatmap(
        self,
        query_id: str
    ) -> Optional[Dict]:
        """
        Generate confidence heatmap showing how confidence changes across stages.
        
        Returns:
            {
                "chunks": [chunk_id, ...],
                "stages": [stage_name, ...],
                "heatmap": [[confidence, ...], ...]  # 2D array
            }
        """
        if query_id not in self._confidence_maps:
            return None
        
        records = self._confidence_maps[query_id]
        
        # Group by chunk and stage
        by_chunk = defaultdict(dict)
        stages = set()
        
        for record in records:
            chunk_id = record["chunk_id"]
            stage = record["stage"]
            confidence = record["confidence"]
            
            by_chunk[chunk_id][stage] = confidence
            stages.add(stage)
        
        # Build heatmap matrix
        chunk_ids = list(by_chunk.keys())
        stage_list = sorted(stages)
        
        heatmap = []
        for chunk_id in chunk_ids:
            row = []
            for stage in stage_list:
                row.append(by_chunk[chunk_id].get(stage, 0.0))
            heatmap.append(row)
        
        return {
            "chunks": chunk_ids,
            "stages": stage_list,
            "heatmap": heatmap
        }


# ---------------------------------------------------------------------------
# 4. Counterfactual Explainer
# ---------------------------------------------------------------------------

class CounterfactualExplainer:
    """
    Generates counterfactual explanations: "What if we removed agent X?"
    """
    
    def explain_agent_impact(
        self,
        query_id: str,
        agent_name: str,
        full_results: List[Dict],
        agent_contributions: Dict[str, List[Dict]]
    ) -> Dict:
        """
        Explain what would change if an agent was removed.
        
        Args:
            query_id: Query ID
            agent_name: Agent to remove
            full_results: Full result set with all agents
            agent_contributions: Chunks contributed by each agent
            
        Returns:
            {
                "agent": str,
                "chunks_contributed": int,
                "unique_chunks": int,  # Chunks only this agent found
                "impact_score": float,  # 0-1, how critical this agent is
                "counterfactual_results": List[Dict]  # Results without this agent
            }
        """
        agent_chunks = agent_contributions.get(agent_name, [])
        
        # Find unique chunks (only this agent retrieved)
        agent_chunk_ids = set(c.get("id") for c in agent_chunks)
        
        unique_chunks = []
        for chunk in agent_chunks:
            chunk_id = chunk.get("id")
            # Check if any other agent also retrieved this
            is_unique = True
            for other_agent, other_chunks in agent_contributions.items():
                if other_agent != agent_name:
                    other_ids = set(c.get("id") for c in other_chunks)
                    if chunk_id in other_ids:
                        is_unique = False
                        break
            if is_unique:
                unique_chunks.append(chunk)
        
        # Calculate impact score
        total_chunks = len(full_results)
        unique_count = len(unique_chunks)
        impact_score = unique_count / max(total_chunks, 1)
        
        # Generate counterfactual results (remove agent's unique chunks)
        unique_ids = set(c.get("id") for c in unique_chunks)
        counterfactual_results = [
            c for c in full_results
            if c.get("id") not in unique_ids
        ]
        
        return {
            "agent": agent_name,
            "chunks_contributed": len(agent_chunks),
            "unique_chunks": unique_count,
            "impact_score": round(impact_score, 3),
            "counterfactual_results": counterfactual_results,
            "explanation": self._generate_impact_explanation(
                agent_name, unique_count, impact_score
            )
        }
    
    def _generate_impact_explanation(
        self,
        agent_name: str,
        unique_chunks: int,
        impact_score: float
    ) -> str:
        """Generate human-readable explanation of agent impact."""
        if impact_score > 0.3:
            return (
                f"{agent_name} is CRITICAL: contributed {unique_chunks} unique chunks "
                f"that no other agent found (impact: {impact_score:.1%})."
            )
        elif impact_score > 0.1:
            return (
                f"{agent_name} is IMPORTANT: contributed {unique_chunks} unique chunks "
                f"(impact: {impact_score:.1%})."
            )
        else:
            return (
                f"{agent_name} has LOW impact: most of its chunks were also found by "
                f"other agents (impact: {impact_score:.1%})."
            )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_decision_tracker: Optional[DecisionTracker] = None


def get_decision_tracker() -> DecisionTracker:
    """Return the module-level decision tracker singleton."""
    global _decision_tracker
    if _decision_tracker is None:
        _decision_tracker = DecisionTracker()
    return _decision_tracker
