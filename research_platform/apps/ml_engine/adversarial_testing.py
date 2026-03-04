"""
Adversarial Query Generation & Robustness Testing.

Generates challenging queries to test system robustness and measures
how well the system handles edge cases.

Components:
1. AdversarialQueryGenerator — creates ambiguous, contradictory, unanswerable queries
2. RobustnessEvaluator — measures system performance on adversarial queries
3. ConfidenceCalibrator — checks if confidence scores match actual accuracy
4. FailureModeAnalyzer — categorizes and analyzes failure patterns

Usage:
    from apps.ml_engine.adversarial_testing import get_adversarial_generator
    
    generator = get_adversarial_generator()
    adversarial_queries = generator.generate_adversarial_queries(
        base_query="What is the best method for protein folding?",
        num_variants=5
    )
"""
import logging
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import random

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Adversarial Query Generator
# ---------------------------------------------------------------------------

class AdversarialQueryGenerator:
    """
    Generates adversarial queries to test system robustness.
    
    Query types:
    - Ambiguous: Multiple valid interpretations
    - Contradictory: Contains conflicting requirements
    - Unanswerable: Asks for information that doesn't exist
    - Overly broad: Too general to answer meaningfully
    - Overly specific: Requires very niche knowledge
    """
    
    def __init__(self):
        self.query_types = [
            "ambiguous",
            "contradictory",
            "unanswerable",
            "overly_broad",
            "overly_specific"
        ]
    
    def generate_adversarial_queries(
        self,
        base_query: str,
        num_variants: int = 5,
        query_types: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Generate adversarial variants of a base query.
        
        Args:
            base_query: Original query
            num_variants: Number of variants to generate
            query_types: Specific types to generate (default: all)
            
        Returns:
            List of adversarial query dicts with structure:
            {
                "query": str,
                "type": str,
                "difficulty": float,
                "expected_behavior": str
            }
        """
        if query_types is None:
            query_types = self.query_types
        
        adversarial_queries = []
        
        # Generate using LLM
        for query_type in query_types[:num_variants]:
            variant = self._generate_variant_llm(base_query, query_type)
            if variant:
                adversarial_queries.append(variant)
        
        logger.info(
            "AdversarialQueryGenerator: generated %d adversarial queries.",
            len(adversarial_queries)
        )
        
        return adversarial_queries
    
    def _generate_variant_llm(
        self,
        base_query: str,
        query_type: str
    ) -> Optional[Dict]:
        """Generate adversarial variant using LLM."""
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import HumanMessage, SystemMessage
            
            prompts = {
                "ambiguous": (
                    "Rewrite this research question to be ambiguous with multiple "
                    "valid interpretations:\n{query}\n\n"
                    "Return only the ambiguous question."
                ),
                "contradictory": (
                    "Rewrite this research question to contain contradictory requirements "
                    "that cannot be satisfied simultaneously:\n{query}\n\n"
                    "Return only the contradictory question."
                ),
                "unanswerable": (
                    "Rewrite this research question to ask for information that likely "
                    "doesn't exist or cannot be known:\n{query}\n\n"
                    "Return only the unanswerable question."
                ),
                "overly_broad": (
                    "Rewrite this research question to be extremely broad and general, "
                    "making it difficult to answer meaningfully:\n{query}\n\n"
                    "Return only the broad question."
                ),
                "overly_specific": (
                    "Rewrite this research question to be extremely specific and niche, "
                    "requiring very specialized knowledge:\n{query}\n\n"
                    "Return only the specific question."
                )
            }
            
            prompt_template = prompts.get(query_type)
            if not prompt_template:
                return None
            
            llm = ChatOpenAI(model="gpt-4o-mini", max_tokens=256, temperature=0.7)
            prompt = prompt_template.format(query=base_query)
            
            response = llm.invoke([HumanMessage(content=prompt)])
            adversarial_query = response.content.strip()
            
            # Determine expected behavior
            expected_behaviors = {
                "ambiguous": "System should request clarification or provide multiple interpretations",
                "contradictory": "System should identify the contradiction and explain why it cannot be answered",
                "unanswerable": "System should admit uncertainty and explain why the question cannot be answered",
                "overly_broad": "System should narrow the scope or provide a structured overview",
                "overly_specific": "System should admit if information is not available"
            }
            
            # Difficulty scoring
            difficulty_scores = {
                "ambiguous": 0.6,
                "contradictory": 0.8,
                "unanswerable": 0.9,
                "overly_broad": 0.5,
                "overly_specific": 0.7
            }
            
            return {
                "query": adversarial_query,
                "type": query_type,
                "difficulty": difficulty_scores.get(query_type, 0.5),
                "expected_behavior": expected_behaviors.get(query_type, "Unknown"),
                "base_query": base_query
            }
            
        except Exception as exc:
            logger.error(
                "AdversarialQueryGenerator: failed to generate %s variant: %s",
                query_type, exc
            )
            return None
    
    def generate_batch(
        self,
        base_queries: List[str],
        variants_per_query: int = 3
    ) -> List[Dict]:
        """Generate adversarial variants for multiple base queries."""
        all_adversarial = []
        
        for base_query in base_queries:
            variants = self.generate_adversarial_queries(
                base_query,
                num_variants=variants_per_query
            )
            all_adversarial.extend(variants)
        
        return all_adversarial


# ---------------------------------------------------------------------------
# 2. Robustness Evaluator
# ---------------------------------------------------------------------------

class RobustnessEvaluator:
    """
    Evaluates system robustness on adversarial queries.
    
    Metrics:
    - Uncertainty admission rate (does system say "I don't know" when appropriate?)
    - Hallucination rate (does system make up answers?)
    - Confidence calibration (do confidence scores match accuracy?)
    - Failure mode distribution
    """
    
    def __init__(self):
        self.results: List[Dict] = []
    
    def evaluate_query(
        self,
        adversarial_query: Dict,
        system_response: str,
        system_confidence: float,
        ground_truth: Optional[str] = None
    ) -> Dict:
        """
        Evaluate system response to an adversarial query.
        
        Args:
            adversarial_query: Query dict from AdversarialQueryGenerator
            system_response: System's generated response
            system_confidence: System's confidence score (0-1)
            ground_truth: Optional ground truth answer for accuracy
            
        Returns:
            Evaluation result dict
        """
        query_type = adversarial_query["type"]
        expected_behavior = adversarial_query["expected_behavior"]
        
        # Check if system admitted uncertainty
        admitted_uncertainty = self._check_uncertainty_admission(system_response)
        
        # Check for hallucination indicators
        hallucination_score = self._detect_hallucination(
            system_response,
            system_confidence
        )
        
        # Check if behavior matches expectation
        behavior_match = self._check_behavior_match(
            query_type,
            system_response,
            admitted_uncertainty
        )
        
        result = {
            "query": adversarial_query["query"],
            "query_type": query_type,
            "expected_behavior": expected_behavior,
            "system_response": system_response[:500],  # Truncate
            "system_confidence": system_confidence,
            "admitted_uncertainty": admitted_uncertainty,
            "hallucination_score": hallucination_score,
            "behavior_match": behavior_match,
            "passed": behavior_match and (hallucination_score < 0.5)
        }
        
        self.results.append(result)
        
        return result
    
    def _check_uncertainty_admission(self, response: str) -> bool:
        """Check if response admits uncertainty."""
        uncertainty_phrases = [
            "i don't know",
            "i'm not sure",
            "i cannot answer",
            "insufficient information",
            "not enough evidence",
            "unclear",
            "ambiguous",
            "cannot determine",
            "unable to answer",
            "no clear answer"
        ]
        
        response_lower = response.lower()
        return any(phrase in response_lower for phrase in uncertainty_phrases)
    
    def _detect_hallucination(
        self,
        response: str,
        confidence: float
    ) -> float:
        """
        Detect potential hallucination.
        
        Heuristic: High confidence + no uncertainty admission = potential hallucination
        
        Returns:
            Hallucination score (0-1, higher = more likely hallucination)
        """
        admitted_uncertainty = self._check_uncertainty_admission(response)
        
        if confidence > 0.8 and not admitted_uncertainty:
            # High confidence without uncertainty on adversarial query = suspicious
            return 0.8
        elif confidence > 0.6 and not admitted_uncertainty:
            return 0.5
        elif admitted_uncertainty:
            return 0.1
        else:
            return 0.3
    
    def _check_behavior_match(
        self,
        query_type: str,
        response: str,
        admitted_uncertainty: bool
    ) -> bool:
        """Check if system behavior matches expected behavior for query type."""
        if query_type in ["unanswerable", "contradictory"]:
            # Should admit uncertainty
            return admitted_uncertainty
        elif query_type == "ambiguous":
            # Should request clarification or provide multiple interpretations
            clarification_phrases = [
                "could you clarify",
                "multiple interpretations",
                "could mean",
                "depending on",
                "ambiguous"
            ]
            response_lower = response.lower()
            return any(phrase in response_lower for phrase in clarification_phrases)
        elif query_type == "overly_broad":
            # Should narrow scope or provide structured overview
            structure_phrases = [
                "several aspects",
                "can be divided",
                "multiple areas",
                "broad question"
            ]
            response_lower = response.lower()
            return any(phrase in response_lower for phrase in structure_phrases)
        else:
            # Default: any reasonable response is acceptable
            return len(response) > 50
    
    def get_summary(self) -> Dict:
        """Get summary statistics of robustness evaluation."""
        if not self.results:
            return {
                "total_queries": 0,
                "pass_rate": 0.0,
                "uncertainty_admission_rate": 0.0,
                "avg_hallucination_score": 0.0,
                "by_query_type": {}
            }
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        admitted_uncertainty = sum(1 for r in self.results if r["admitted_uncertainty"])
        avg_hallucination = sum(r["hallucination_score"] for r in self.results) / total
        
        # Group by query type
        by_type = defaultdict(list)
        for result in self.results:
            by_type[result["query_type"]].append(result)
        
        type_summary = {}
        for query_type, type_results in by_type.items():
            type_summary[query_type] = {
                "count": len(type_results),
                "pass_rate": sum(1 for r in type_results if r["passed"]) / len(type_results),
                "uncertainty_rate": sum(1 for r in type_results if r["admitted_uncertainty"]) / len(type_results)
            }
        
        return {
            "total_queries": total,
            "pass_rate": passed / total,
            "uncertainty_admission_rate": admitted_uncertainty / total,
            "avg_hallucination_score": avg_hallucination,
            "by_query_type": type_summary
        }


# ---------------------------------------------------------------------------
# 3. Confidence Calibrator
# ---------------------------------------------------------------------------

class ConfidenceCalibrator:
    """
    Checks if confidence scores are well-calibrated (match actual accuracy).
    """
    
    def __init__(self):
        self.calibration_data: List[Tuple[float, bool]] = []
    
    def record(
        self,
        predicted_confidence: float,
        is_correct: bool
    ) -> None:
        """Record a prediction with its confidence and correctness."""
        self.calibration_data.append((predicted_confidence, is_correct))
    
    def calculate_calibration(
        self,
        num_bins: int = 10
    ) -> Dict:
        """
        Calculate calibration metrics.
        
        Returns:
            {
                "calibration_error": float,  # Expected Calibration Error (ECE)
                "bins": [
                    {
                        "confidence_range": (low, high),
                        "avg_confidence": float,
                        "accuracy": float,
                        "count": int
                    },
                    ...
                ]
            }
        """
        if not self.calibration_data:
            return {
                "calibration_error": 0.0,
                "bins": []
            }
        
        # Create bins
        bins = [[] for _ in range(num_bins)]
        bin_size = 1.0 / num_bins
        
        for confidence, is_correct in self.calibration_data:
            bin_idx = min(int(confidence / bin_size), num_bins - 1)
            bins[bin_idx].append((confidence, is_correct))
        
        # Calculate metrics per bin
        bin_results = []
        total_ece = 0.0
        total_count = len(self.calibration_data)
        
        for i, bin_data in enumerate(bins):
            if not bin_data:
                continue
            
            confidences = [c for c, _ in bin_data]
            correctness = [c for _, c in bin_data]
            
            avg_confidence = sum(confidences) / len(confidences)
            accuracy = sum(correctness) / len(correctness)
            count = len(bin_data)
            
            # Contribution to ECE
            ece_contribution = abs(avg_confidence - accuracy) * (count / total_count)
            total_ece += ece_contribution
            
            bin_results.append({
                "confidence_range": (i * bin_size, (i + 1) * bin_size),
                "avg_confidence": avg_confidence,
                "accuracy": accuracy,
                "count": count,
                "calibration_gap": abs(avg_confidence - accuracy)
            })
        
        return {
            "calibration_error": total_ece,
            "bins": bin_results,
            "total_samples": total_count
        }


# ---------------------------------------------------------------------------
# 4. Failure Mode Analyzer
# ---------------------------------------------------------------------------

class FailureModeAnalyzer:
    """
    Categorizes and analyzes failure patterns.
    """
    
    def __init__(self):
        self.failures: List[Dict] = []
    
    def record_failure(
        self,
        query: str,
        query_type: str,
        system_response: str,
        failure_reason: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """Record a system failure."""
        self.failures.append({
            "query": query,
            "query_type": query_type,
            "system_response": system_response[:500],
            "failure_reason": failure_reason,
            "metadata": metadata or {},
            "timestamp": self._get_timestamp()
        })
    
    def analyze_failures(self) -> Dict:
        """
        Analyze failure patterns.
        
        Returns:
            {
                "total_failures": int,
                "by_query_type": Dict[str, int],
                "by_failure_reason": Dict[str, int],
                "common_patterns": List[str]
            }
        """
        if not self.failures:
            return {
                "total_failures": 0,
                "by_query_type": {},
                "by_failure_reason": {},
                "common_patterns": []
            }
        
        # Count by query type
        by_type = defaultdict(int)
        for failure in self.failures:
            by_type[failure["query_type"]] += 1
        
        # Count by failure reason
        by_reason = defaultdict(int)
        for failure in self.failures:
            by_reason[failure["failure_reason"]] += 1
        
        # Identify common patterns (simplified)
        common_patterns = [
            f"{reason}: {count} occurrences"
            for reason, count in sorted(
                by_reason.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
        ]
        
        return {
            "total_failures": len(self.failures),
            "by_query_type": dict(by_type),
            "by_failure_reason": dict(by_reason),
            "common_patterns": common_patterns
        }
    
    @staticmethod
    def _get_timestamp() -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.utcnow().isoformat()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_adversarial_generator: Optional[AdversarialQueryGenerator] = None


def get_adversarial_generator() -> AdversarialQueryGenerator:
    """Return the module-level adversarial generator singleton."""
    global _adversarial_generator
    if _adversarial_generator is None:
        _adversarial_generator = AdversarialQueryGenerator()
    return _adversarial_generator
