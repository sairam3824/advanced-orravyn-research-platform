"""
Efficiency Tracker — QPS and API cost analysis for the Orravyn RAG pipeline.

Records:
  - Queries per second (QPS) over rolling windows
  - LLM API token consumption (prompt + completion tokens)
  - Per-stage latency breakdown
  - Estimated API cost ($) based on gpt-4o-mini pricing

Usage — Decorator
-----------------
    from apps.ml_engine.efficiency_tracker import track_query

    @track_query("rag_pipeline")
    def query_rag(user_query: str) -> dict:
        ...

Usage — Manual
--------------
    from apps.ml_engine.efficiency_tracker import get_tracker

    tracker = get_tracker()
    with tracker.measure("hybrid_retrieve"):
        chunks = retriever.search(query)

    tracker.record_tokens(prompt_tokens=320, completion_tokens=180, model="gpt-4o-mini")

Usage — Report
--------------
    from apps.ml_engine.efficiency_tracker import get_tracker
    print(get_tracker().report())

    # → {
    #     "total_queries": 142,
    #     "qps_1min": 0.37,
    #     "qps_5min": 0.28,
    #     "avg_latency_ms": 1240.5,
    #     "total_tokens": {"prompt": 45000, "completion": 18000},
    #     "estimated_cost_usd": 0.038,
    #     "stage_latencies_ms": {"hybrid_retrieve": 320.1, "rerank": 145.3, ...},
    #   }
"""
import functools
import logging
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GPT-4o-mini pricing (per 1M tokens, as of 2025)
# ---------------------------------------------------------------------------
_PRICING: Dict[str, Dict[str, float]] = {
    "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},   # $ per 1M tokens
    "gpt-4o":      {"prompt": 5.00, "completion": 15.00},
    "default":     {"prompt": 0.15, "completion": 0.60},
}


class EfficiencyTracker:
    """
    Thread-safe efficiency tracker for the Orravyn pipeline.

    Uses deques with maxlen for rolling QPS windows (no memory leak).
    """

    def __init__(self):
        self._query_timestamps: deque = deque(maxlen=10_000)  # UNIX timestamps
        self._query_latencies:  deque = deque(maxlen=10_000)  # ms per query
        self._stage_latencies:  Dict[str, deque] = defaultdict(lambda: deque(maxlen=1_000))
        self._token_log: deque = deque(maxlen=10_000)  # {model, prompt, completion}
        self._lock = __import__("threading").Lock()

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_query(self, latency_ms: float) -> None:
        """Call once per completed query."""
        with self._lock:
            self._query_timestamps.append(time.time())
            self._query_latencies.append(latency_ms)

    def record_stage(self, stage: str, latency_ms: float) -> None:
        """Record per-stage latency."""
        with self._lock:
            self._stage_latencies[stage].append(latency_ms)

    def record_tokens(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model: str = "gpt-4o-mini",
    ) -> None:
        """Record LLM token usage for cost estimation."""
        with self._lock:
            self._token_log.append({
                "model":       model,
                "prompt":      prompt_tokens,
                "completion":  completion_tokens,
                "ts":          time.time(),
            })

    # ------------------------------------------------------------------
    # Measurement helpers
    # ------------------------------------------------------------------

    @contextmanager
    def measure(self, stage: str):
        """Context manager for timing a code block."""
        t0 = time.perf_counter()
        try:
            yield
        finally:
            elapsed = (time.perf_counter() - t0) * 1000
            self.record_stage(stage, elapsed)

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def _qps(self, window_seconds: int) -> float:
        """Queries per second over the last `window_seconds`."""
        cutoff = time.time() - window_seconds
        with self._lock:
            recent = sum(1 for ts in self._query_timestamps if ts >= cutoff)
        return round(recent / window_seconds, 4)

    def _avg(self, dq: deque) -> float:
        lst = list(dq)
        return round(sum(lst) / len(lst), 2) if lst else 0.0

    def _total_tokens(self):
        prompt_total = completion_total = 0
        with self._lock:
            for entry in self._token_log:
                prompt_total     += entry["prompt"]
                completion_total += entry["completion"]
        return prompt_total, completion_total

    def _estimated_cost(self) -> float:
        cost = 0.0
        with self._lock:
            for entry in self._token_log:
                pricing   = _PRICING.get(entry["model"], _PRICING["default"])
                cost     += entry["prompt"]     / 1_000_000 * pricing["prompt"]
                cost     += entry["completion"] / 1_000_000 * pricing["completion"]
        return round(cost, 6)

    def report(self) -> Dict:
        prompt_total, completion_total = self._total_tokens()
        stage_avgs = {}
        with self._lock:
            for stage, dq in self._stage_latencies.items():
                stage_avgs[stage] = self._avg(dq)

        return {
            "total_queries":        len(self._query_timestamps),
            "qps_1min":             self._qps(60),
            "qps_5min":             self._qps(300),
            "qps_15min":            self._qps(900),
            "avg_latency_ms":       self._avg(self._query_latencies),
            "p95_latency_ms":       self._percentile(self._query_latencies, 95),
            "total_tokens": {
                "prompt":      prompt_total,
                "completion":  completion_total,
                "total":       prompt_total + completion_total,
            },
            "estimated_cost_usd":   self._estimated_cost(),
            "stage_latencies_ms":   stage_avgs,
        }

    @staticmethod
    def _percentile(dq: deque, pct: int) -> float:
        lst = sorted(dq)
        if not lst:
            return 0.0
        idx = int(len(lst) * pct / 100)
        return round(lst[min(idx, len(lst) - 1)], 2)

    def print_report(self) -> None:
        r = self.report()
        print("\n" + "=" * 55)
        print("ORRAVYN EFFICIENCY REPORT")
        print("=" * 55)
        print(f"  Total queries        : {r['total_queries']}")
        print(f"  QPS  (1 min)         : {r['qps_1min']}")
        print(f"  QPS  (5 min)         : {r['qps_5min']}")
        print(f"  QPS  (15 min)        : {r['qps_15min']}")
        print(f"  Avg latency          : {r['avg_latency_ms']} ms")
        print(f"  P95 latency          : {r['p95_latency_ms']} ms")
        print(f"  Total prompt tokens  : {r['total_tokens']['prompt']:,}")
        print(f"  Total completion tks : {r['total_tokens']['completion']:,}")
        print(f"  Estimated cost (USD) : ${r['estimated_cost_usd']:.4f}")
        if r["stage_latencies_ms"]:
            print("\n  Stage latencies (avg):")
            for stage, ms in sorted(r["stage_latencies_ms"].items(), key=lambda x: -x[1]):
                print(f"    {stage:<30} {ms:>8.1f} ms")
        print("=" * 55)


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------

def track_query(stage_name: str = "pipeline"):
    """
    Decorator that records total query latency and hooks into OpenAI callbacks
    to capture token usage automatically.

    Usage:
        @track_query("rag_pipeline")
        def query_rag(user_query: str) -> dict:
            ...
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            tracker = get_tracker()
            t0      = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
                # If result dict contains token usage, record it
                if isinstance(result, dict) and "usage" in result:
                    usage = result["usage"]
                    tracker.record_tokens(
                        prompt_tokens=usage.get("prompt_tokens", 0),
                        completion_tokens=usage.get("completion_tokens", 0),
                    )
                return result
            finally:
                elapsed = (time.perf_counter() - t0) * 1000
                tracker.record_query(elapsed)
                tracker.record_stage(stage_name, elapsed)
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Django management command support — expose as endpoint
# ---------------------------------------------------------------------------

def get_efficiency_report_json() -> dict:
    """Callable from views or management commands."""
    return get_tracker().report()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_tracker: Optional[EfficiencyTracker] = None


def get_tracker() -> EfficiencyTracker:
    """Return the process-level EfficiencyTracker singleton."""
    global _tracker
    if _tracker is None:
        _tracker = EfficiencyTracker()
    return _tracker
