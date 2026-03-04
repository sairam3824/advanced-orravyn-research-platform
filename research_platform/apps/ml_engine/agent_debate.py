"""
Cross-Agent Consensus & Debate Mechanism.

When multiple agents retrieve conflicting evidence, this module orchestrates
a structured debate to reach consensus before synthesis.

Components:
1. ContradictionDetector — identifies conflicting claims across agent outputs
2. DebateOrchestrator — manages multi-round debate protocol
3. ConsensusBuilder — confidence-weighted voting for final decision
4. EvidenceTriangulator — requires 2+ agents to agree before accepting claims

Usage:
    from apps.ml_engine.agent_debate import get_debate_orchestrator
    
    orchestrator = get_debate_orchestrator()
    result = orchestrator.debate(
        query="What is the best approach for protein folding?",
        agent_outputs={
            "web": [...],
            "arxiv": [...],
            "platform": [...],
        }
    )
    # Returns: consensus evidence + debate transcript
"""
import logging
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Contradiction Detector
# ---------------------------------------------------------------------------

class ContradictionDetector:
    """
    Identifies conflicting claims across agent outputs using semantic similarity
    and claim extraction.
    """
    
    def __init__(self):
        self._similarity_threshold = 0.85  # High similarity = potential contradiction
        
    def detect_conflicts(
        self,
        agent_outputs: Dict[str, List[Dict]]
    ) -> List[Dict]:
        """
        Detect contradictions across agent outputs.
        
        Args:
            agent_outputs: {agent_name: [chunks], ...}
            
        Returns:
            List of conflict dicts with structure:
            {
                "claim_a": str,
                "claim_b": str,
                "agent_a": str,
                "agent_b": str,
                "confidence_a": float,
                "confidence_b": float,
                "conflict_type": "direct_contradiction" | "partial_overlap"
            }
        """
        conflicts = []
        
        # Extract claims from each agent
        agent_claims = {}
        for agent_name, chunks in agent_outputs.items():
            agent_claims[agent_name] = self._extract_claims(chunks)
        
        # Compare claims pairwise across agents
        agent_names = list(agent_claims.keys())
        for i, agent_a in enumerate(agent_names):
            for agent_b in agent_names[i+1:]:
                conflicts.extend(
                    self._compare_claims(
                        agent_a, agent_claims[agent_a],
                        agent_b, agent_claims[agent_b]
                    )
                )
        
        logger.info(
            "ContradictionDetector: found %d conflicts across %d agents.",
            len(conflicts), len(agent_names)
        )
        return conflicts
    
    def _extract_claims(self, chunks: List[Dict]) -> List[Dict]:
        """Extract key claims from chunks (simplified: use first 3 chunks)."""
        claims = []
        for chunk in chunks[:3]:  # Top 3 chunks per agent
            content = chunk.get("content", "")
            if len(content) > 50:  # Skip very short chunks
                claims.append({
                    "text": content[:500],  # First 500 chars
                    "confidence": chunk.get("relevance_score", 0.5),
                    "source": chunk.get("metadata", {})
                })
        return claims
    
    def _compare_claims(
        self,
        agent_a: str, claims_a: List[Dict],
        agent_b: str, claims_b: List[Dict]
    ) -> List[Dict]:
        """Compare claims between two agents using keyword overlap heuristic."""
        conflicts = []
        
        for claim_a in claims_a:
            for claim_b in claims_b:
                # Simple keyword-based contradiction detection
                text_a = claim_a["text"].lower()
                text_b = claim_b["text"].lower()
                
                # Check for negation patterns
                if self._has_negation_conflict(text_a, text_b):
                    conflicts.append({
                        "claim_a": claim_a["text"][:200],
                        "claim_b": claim_b["text"][:200],
                        "agent_a": agent_a,
                        "agent_b": agent_b,
                        "confidence_a": claim_a["confidence"],
                        "confidence_b": claim_b["confidence"],
                        "conflict_type": "direct_contradiction"
                    })
        
        return conflicts
    
    def _has_negation_conflict(self, text_a: str, text_b: str) -> bool:
        """Detect negation patterns indicating contradiction."""
        negation_pairs = [
            ("effective", "ineffective"),
            ("superior", "inferior"),
            ("outperforms", "underperforms"),
            ("accurate", "inaccurate"),
            ("successful", "unsuccessful"),
            ("improves", "degrades"),
            ("increases", "decreases"),
            ("better", "worse"),
        ]
        
        for pos, neg in negation_pairs:
            if (pos in text_a and neg in text_b) or (neg in text_a and pos in text_b):
                return True
        
        return False


# ---------------------------------------------------------------------------
# 2. Debate Orchestrator
# ---------------------------------------------------------------------------

class DebateOrchestrator:
    """
    Manages multi-round debate protocol when conflicts are detected.
    
    Protocol:
    1. Present conflicting evidence to LLM
    2. Request analysis and counter-evidence
    3. Repeat for max_rounds or until consensus
    4. Return debate transcript + consensus
    """
    
    def __init__(self, max_rounds: int = 2):
        self.max_rounds = max_rounds
        self.detector = ContradictionDetector()
        
    def debate(
        self,
        query: str,
        agent_outputs: Dict[str, List[Dict]]
    ) -> Dict:
        """
        Orchestrate debate when conflicts detected.
        
        Args:
            query: Original user query
            agent_outputs: {agent_name: [chunks], ...}
            
        Returns:
            {
                "has_conflicts": bool,
                "conflicts": List[Dict],
                "debate_transcript": List[Dict],
                "consensus": Dict,
                "final_evidence": List[Dict]
            }
        """
        # Detect conflicts
        conflicts = self.detector.detect_conflicts(agent_outputs)
        
        if not conflicts:
            logger.info("DebateOrchestrator: no conflicts detected, skipping debate.")
            return {
                "has_conflicts": False,
                "conflicts": [],
                "debate_transcript": [],
                "consensus": {"status": "no_debate_needed"},
                "final_evidence": self._merge_all_evidence(agent_outputs)
            }
        
        logger.info(
            "DebateOrchestrator: %d conflicts detected, starting debate.",
            len(conflicts)
        )
        
        # Run debate rounds
        transcript = []
        for round_num in range(1, self.max_rounds + 1):
            round_result = self._run_debate_round(
                query, conflicts, agent_outputs, round_num
            )
            transcript.append(round_result)
            
            # Check if consensus reached
            if round_result.get("consensus_reached"):
                logger.info(
                    "DebateOrchestrator: consensus reached in round %d.",
                    round_num
                )
                break
        
        # Build consensus
        consensus = self._build_consensus(conflicts, transcript)
        final_evidence = self._filter_evidence_by_consensus(
            agent_outputs, consensus
        )
        
        return {
            "has_conflicts": True,
            "conflicts": conflicts,
            "debate_transcript": transcript,
            "consensus": consensus,
            "final_evidence": final_evidence
        }
    
    def _run_debate_round(
        self,
        query: str,
        conflicts: List[Dict],
        agent_outputs: Dict[str, List[Dict]],
        round_num: int
    ) -> Dict:
        """Run a single debate round using LLM."""
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import HumanMessage, SystemMessage
            
            # Build debate prompt
            conflict_summary = self._format_conflicts(conflicts)
            
            system_prompt = (
                "You are a research debate moderator. Multiple AI agents have retrieved "
                "conflicting evidence for a research question. Your task is to:\n"
                "1. Analyze the conflicting claims\n"
                "2. Identify which claim has stronger evidence\n"
                "3. Explain your reasoning\n"
                "4. Indicate if consensus can be reached or if both views are valid\n\n"
                "Be objective and evidence-based."
            )
            
            user_prompt = (
                f"Research Question: {query}\n\n"
                f"Conflicting Evidence:\n{conflict_summary}\n\n"
                f"Debate Round {round_num}: Analyze these conflicts and provide your assessment."
            )
            
            llm = ChatOpenAI(model="gpt-4o-mini", max_tokens=512, temperature=0.3)
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = llm.invoke(messages)
            analysis = response.content.strip()
            
            # Check if consensus indicated
            consensus_keywords = ["consensus", "agree", "both valid", "no clear winner"]
            consensus_reached = any(kw in analysis.lower() for kw in consensus_keywords)
            
            return {
                "round": round_num,
                "analysis": analysis,
                "consensus_reached": consensus_reached,
                "timestamp": self._get_timestamp()
            }
            
        except Exception as exc:
            logger.error("DebateOrchestrator: debate round failed: %s", exc)
            return {
                "round": round_num,
                "analysis": "Debate round failed due to error.",
                "consensus_reached": False,
                "error": str(exc)
            }
    
    def _format_conflicts(self, conflicts: List[Dict]) -> str:
        """Format conflicts for LLM prompt."""
        lines = []
        for i, conflict in enumerate(conflicts[:3], 1):  # Max 3 conflicts
            lines.append(
                f"Conflict {i}:\n"
                f"  Agent {conflict['agent_a']} (confidence {conflict['confidence_a']:.2f}):\n"
                f"    {conflict['claim_a']}\n"
                f"  Agent {conflict['agent_b']} (confidence {conflict['confidence_b']:.2f}):\n"
                f"    {conflict['claim_b']}\n"
            )
        return "\n".join(lines)
    
    def _build_consensus(
        self,
        conflicts: List[Dict],
        transcript: List[Dict]
    ) -> Dict:
        """Build consensus from debate transcript."""
        if not transcript:
            return {"status": "no_debate", "decision": "accept_all"}
        
        last_round = transcript[-1]
        
        if last_round.get("consensus_reached"):
            return {
                "status": "consensus_reached",
                "decision": "synthesize_both_views",
                "reasoning": last_round.get("analysis", ""),
                "rounds": len(transcript)
            }
        else:
            return {
                "status": "no_consensus",
                "decision": "flag_uncertainty",
                "reasoning": "Conflicting evidence remains after debate.",
                "rounds": len(transcript)
            }
    
    def _merge_all_evidence(
        self,
        agent_outputs: Dict[str, List[Dict]]
    ) -> List[Dict]:
        """Merge all evidence from all agents."""
        merged = []
        for agent_name, chunks in agent_outputs.items():
            for chunk in chunks:
                chunk_copy = dict(chunk)
                chunk_copy["source_agent"] = agent_name
                merged.append(chunk_copy)
        return merged
    
    def _filter_evidence_by_consensus(
        self,
        agent_outputs: Dict[str, List[Dict]],
        consensus: Dict
    ) -> List[Dict]:
        """Filter evidence based on consensus decision."""
        decision = consensus.get("decision", "accept_all")
        
        if decision == "accept_all" or decision == "synthesize_both_views":
            return self._merge_all_evidence(agent_outputs)
        elif decision == "flag_uncertainty":
            # Return all but mark as uncertain
            merged = self._merge_all_evidence(agent_outputs)
            for chunk in merged:
                chunk["uncertainty_flagged"] = True
            return merged
        else:
            return self._merge_all_evidence(agent_outputs)
    
    @staticmethod
    def _get_timestamp() -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.utcnow().isoformat()


# ---------------------------------------------------------------------------
# 3. Consensus Builder
# ---------------------------------------------------------------------------

class ConsensusBuilder:
    """
    Confidence-weighted voting system for reaching consensus across agents.
    """
    
    def vote(
        self,
        agent_outputs: Dict[str, List[Dict]],
        min_agreement: float = 0.6
    ) -> Dict:
        """
        Perform confidence-weighted voting.
        
        Args:
            agent_outputs: {agent_name: [chunks], ...}
            min_agreement: Minimum agreement threshold (0-1)
            
        Returns:
            {
                "consensus_reached": bool,
                "agreement_score": float,
                "winning_evidence": List[Dict],
                "vote_breakdown": Dict
            }
        """
        # Count evidence support by paper_id
        paper_votes = defaultdict(lambda: {"count": 0, "total_confidence": 0.0, "agents": []})
        
        for agent_name, chunks in agent_outputs.items():
            for chunk in chunks[:5]:  # Top 5 per agent
                paper_id = chunk.get("metadata", {}).get("paper_id")
                if paper_id:
                    confidence = chunk.get("relevance_score", 0.5)
                    paper_votes[paper_id]["count"] += 1
                    paper_votes[paper_id]["total_confidence"] += confidence
                    paper_votes[paper_id]["agents"].append(agent_name)
        
        # Calculate agreement score
        total_agents = len(agent_outputs)
        if total_agents == 0:
            return {
                "consensus_reached": False,
                "agreement_score": 0.0,
                "winning_evidence": [],
                "vote_breakdown": {}
            }
        
        # Find papers with highest agreement
        sorted_papers = sorted(
            paper_votes.items(),
            key=lambda x: (x[1]["count"], x[1]["total_confidence"]),
            reverse=True
        )
        
        if sorted_papers:
            top_paper_id, top_votes = sorted_papers[0]
            agreement_score = top_votes["count"] / total_agents
            consensus_reached = agreement_score >= min_agreement
        else:
            agreement_score = 0.0
            consensus_reached = False
        
        return {
            "consensus_reached": consensus_reached,
            "agreement_score": agreement_score,
            "vote_breakdown": dict(paper_votes),
            "top_papers": [pid for pid, _ in sorted_papers[:5]]
        }


# ---------------------------------------------------------------------------
# 4. Evidence Triangulator
# ---------------------------------------------------------------------------

class EvidenceTriangulator:
    """
    Requires 2+ agents to agree before accepting claims (triangulation).
    """
    
    def triangulate(
        self,
        agent_outputs: Dict[str, List[Dict]],
        min_sources: int = 2
    ) -> List[Dict]:
        """
        Filter evidence to only include claims supported by multiple agents.
        
        Args:
            agent_outputs: {agent_name: [chunks], ...}
            min_sources: Minimum number of agents that must agree
            
        Returns:
            Filtered list of chunks with triangulation metadata
        """
        # Group chunks by paper_id
        paper_chunks = defaultdict(list)
        
        for agent_name, chunks in agent_outputs.items():
            for chunk in chunks:
                paper_id = chunk.get("metadata", {}).get("paper_id")
                if paper_id:
                    chunk_copy = dict(chunk)
                    chunk_copy["source_agent"] = agent_name
                    paper_chunks[paper_id].append(chunk_copy)
        
        # Filter papers with min_sources support
        triangulated = []
        for paper_id, chunks in paper_chunks.items():
            unique_agents = set(c["source_agent"] for c in chunks)
            if len(unique_agents) >= min_sources:
                # Add triangulation metadata
                for chunk in chunks:
                    chunk["triangulated"] = True
                    chunk["supporting_agents"] = list(unique_agents)
                    chunk["triangulation_score"] = len(unique_agents)
                triangulated.extend(chunks)
        
        logger.info(
            "EvidenceTriangulator: %d/%d chunks passed triangulation (min_sources=%d).",
            len(triangulated),
            sum(len(chunks) for chunks in agent_outputs.values()),
            min_sources
        )
        
        return sorted(
            triangulated,
            key=lambda x: x.get("triangulation_score", 0),
            reverse=True
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_debate_orchestrator: Optional[DebateOrchestrator] = None


def get_debate_orchestrator() -> DebateOrchestrator:
    """Return the module-level debate orchestrator singleton."""
    global _debate_orchestrator
    if _debate_orchestrator is None:
        _debate_orchestrator = DebateOrchestrator()
    return _debate_orchestrator
