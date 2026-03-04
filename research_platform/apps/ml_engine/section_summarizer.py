"""
Section-Aware Hierarchical Summarizer.

Classifies paper text into sections, summarises each section via the
existing BART summarizer, then weights the section summaries by their
research importance to produce a final composite summary.

When a query embedding is supplied the weights are produced dynamically
by the DQSW cross-attention layer (``section_weight_learner``).  Without
a query the hardcoded fallback table is used, preserving backward
compatibility.
"""
import logging
from typing import Dict, List, Optional

from .section_classifier import SectionClassifier

logger = logging.getLogger(__name__)

# Static fallback weights — used when no query is provided or DQSW unavailable.
SECTION_WEIGHTS: Dict[str, float] = {
    "Methodology": 0.35,
    "Methods":     0.35,
    "Experiments": 0.30,
    "Results":     0.30,
    "Discussion":  0.15,
    "Introduction": 0.10,
    "Related Work": 0.08,
    "Background":  0.08,
    "Conclusion":  0.07,
    "Abstract":    0.05,
}

# Default weight for unrecognised sections (e.g. "Part 1" fallback)
_DEFAULT_WEIGHT = 0.10

# GAP-3: sections shorter than this word count are passed through as-is
# rather than sent to the summarizer (avoids BART nonsense on tiny inputs).
_MIN_SECTION_WORDS = 40


def _get_dqsw_weights(
    query_embedding,
    section_names: List[str],
) -> Dict[str, float]:
    """
    Fetch dynamic weights from the DQSW learner.

    Falls back to normalised SECTION_WEIGHTS on any failure so the caller
    never has to handle exceptions.
    """
    try:
        from .section_weight_learner import get_weight_learner
        return get_weight_learner().get_weights(query_embedding, section_names)
    except Exception as exc:
        logger.debug("DQSW weight fetch failed (%s); using static weights.", exc)
        raw = {s: SECTION_WEIGHTS.get(s, _DEFAULT_WEIGHT) for s in section_names}
        total = sum(raw.values()) or 1.0
        return {s: v / total for s, v in raw.items()}


class SectionAwareSummarizer:
    """
    Produces a weighted composite summary from per-section summaries.

    Parameters
    ----------
    use_scibert:
        When True, use ``SciBERTSectionClassifier`` instead of the regex
        ``SectionClassifier``.  Falls back to regex automatically if SciBERT
        is unavailable.
    """

    def __init__(self, use_scibert: bool = False):
        if use_scibert:
            try:
                from .scibert_classifier import get_scibert_classifier
                self._classifier = get_scibert_classifier()
            except Exception:
                self._classifier = SectionClassifier()
        else:
            self._classifier = SectionClassifier()

    def summarize_paper(
        self,
        paper_text: str,
        query_embedding=None,
    ) -> Dict:
        """
        Summarise a full research paper text in a section-aware manner.

        Args:
            paper_text:       Raw extracted text of the paper.
            query_embedding:  Optional query embedding for DQSW dynamic
                              weighting.  Pass the sentence-transformer
                              embedding of the retrieval query to activate
                              query-conditioned weights.

        Returns:
            {
                "final_summary": str,
                "section_summaries": {section_name: summary_str, ...}
            }
        """
        from ml_models.summary import summarize_text

        sections = self._classifier.classify_sections(paper_text)
        if not sections:
            logger.warning("SectionAwareSummarizer: no sections found; falling back to full-text summary.")
            fallback = summarize_text(paper_text) or ""
            return {"final_summary": fallback, "section_summaries": {}}

        section_summaries: Dict[str, str] = {}
        for name, content in sections.items():
            if not content.strip():
                continue
            words = content.split()
            # GAP-3: too short for the summarizer — use the text directly
            if len(words) < _MIN_SECTION_WORDS:
                section_summaries[name] = content.strip()
                continue
            try:
                summary = summarize_text(content)
                if summary:
                    section_summaries[name] = summary
            except Exception as exc:
                logger.warning("Failed to summarise section '%s': %s", name, exc)

        if not section_summaries:
            logger.warning("SectionAwareSummarizer: all section summaries failed.")
            return {"final_summary": "", "section_summaries": {}}

        final_summary = self._combine(section_summaries, query_embedding)
        return {
            "final_summary": final_summary,
            "section_summaries": section_summaries,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _combine(
        self,
        section_summaries: Dict[str, str],
        query_embedding=None,
    ) -> str:
        """
        Combine per-section summaries into a weighted final summary.

        When ``query_embedding`` is provided the DQSW layer computes
        dynamic per-section weights.  Otherwise the static SECTION_WEIGHTS
        table is used.

        Higher-weight sections appear first and contribute more tokens
        proportional to their normalised weight × 300.
        """
        section_names = list(section_summaries.keys())

        if query_embedding is not None:
            weights = _get_dqsw_weights(query_embedding, section_names)
        else:
            raw = {s: SECTION_WEIGHTS.get(s, _DEFAULT_WEIGHT) for s in section_names}
            total = sum(raw.values()) or 1.0
            weights = {s: v / total for s, v in raw.items()}

        ordered = sorted(section_names, key=lambda s: weights.get(s, 0.0), reverse=True)

        parts = []
        for name in ordered:
            weight = weights.get(name, _DEFAULT_WEIGHT)
            max_words = max(int(weight * 300), 30)
            words = section_summaries[name].split()
            truncated = " ".join(words[:max_words])
            if truncated:
                parts.append(f"[{name}] {truncated}")

        return " ".join(parts)
