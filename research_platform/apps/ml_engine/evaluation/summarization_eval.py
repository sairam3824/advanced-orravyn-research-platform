"""
Summarization evaluation metrics for Section-Aware Hierarchical Summarization.

Metrics
-------
  ROUGE-1, ROUGE-2, ROUGE-L   — standard n-gram overlap (rouge-score)
  BERTScore F1                 — semantic similarity via BERT embeddings
  METEOR                       — paraphrase-aware overlap (nltk)
  Section Coverage Score       — custom: % of key IMRaD sections covered

Install dependencies:
    pip install rouge-score bert-score nltk
"""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Sections considered "key" for coverage scoring
_KEY_SECTIONS = {"Methodology", "Methods", "Results", "Experiments", "Discussion"}


# ---------------------------------------------------------------------------
# Individual metrics
# ---------------------------------------------------------------------------

def compute_rouge(
    predictions: List[str],
    references: List[str],
) -> Dict[str, float]:
    """Compute ROUGE-1, ROUGE-2, ROUGE-L (F1) averaged over all pairs."""
    try:
        from rouge_score import rouge_scorer

        scorer = rouge_scorer.RougeScorer(
            ["rouge1", "rouge2", "rougeL"], use_stemmer=True
        )
        agg: Dict[str, List[float]] = {"rouge1": [], "rouge2": [], "rougeL": []}
        for pred, ref in zip(predictions, references):
            result = scorer.score(ref, pred)
            for k in agg:
                agg[k].append(result[k].fmeasure)

        return {k: sum(v) / len(v) for k, v in agg.items() if v}

    except ImportError:
        logger.error("rouge-score not installed. Run: pip install rouge-score")
        return {}


def compute_bertscore(
    predictions: List[str],
    references: List[str],
    lang: str = "en",
) -> Dict[str, float]:
    """Compute BERTScore Precision, Recall, F1 averaged over all pairs."""
    try:
        from bert_score import score as _bert_score

        P, R, F1 = _bert_score(predictions, references, lang=lang, verbose=False)
        return {
            "bertscore_precision": float(P.mean()),
            "bertscore_recall":    float(R.mean()),
            "bertscore_f1":        float(F1.mean()),
        }
    except ImportError:
        logger.error("bert-score not installed. Run: pip install bert-score")
        return {}


def compute_meteor(
    predictions: List[str],
    references: List[str],
) -> Dict[str, float]:
    """Compute METEOR score averaged over all pairs."""
    try:
        import nltk
        from nltk.translate.meteor_score import meteor_score

        for resource in ("wordnet", "omw-1.4"):
            try:
                nltk.data.find(f"corpora/{resource}")
            except LookupError:
                nltk.download(resource, quiet=True)

        scores = [
            meteor_score([ref.split()], pred.split())
            for pred, ref in zip(predictions, references)
        ]
        return {"meteor": sum(scores) / len(scores) if scores else 0.0}

    except ImportError:
        logger.error("nltk not installed. Run: pip install nltk")
        return {}


def compute_section_coverage(
    section_summaries_list: List[Dict[str, str]],
) -> Dict[str, float]:
    """
    Compute what fraction of key IMRaD sections are covered per paper.

    Args:
        section_summaries_list: List of {section_name: summary} dicts,
                                one per paper.

    Returns:
        {"section_coverage": float}  — averaged over all papers.
    """
    if not section_summaries_list:
        return {"section_coverage": 0.0}

    coverages = []
    for sec_summaries in section_summaries_list:
        found = _KEY_SECTIONS & set(sec_summaries.keys())
        coverages.append(len(found) / len(_KEY_SECTIONS))

    return {"section_coverage": sum(coverages) / len(coverages)}


# ---------------------------------------------------------------------------
# Combined evaluator
# ---------------------------------------------------------------------------

def evaluate_summarization(
    predictions: List[str],
    references: List[str],
    section_summaries_list: Optional[List[Dict[str, str]]] = None,
    skip_bertscore: bool = False,
) -> Dict[str, float]:
    """
    Run all summarization metrics and return combined results.

    Args:
        predictions:            List of generated summaries.
        references:             List of reference summaries (gold standard).
        section_summaries_list: Optional per-paper section summary dicts
                                for section coverage scoring.
        skip_bertscore:         Skip BERTScore if compute budget is tight
                                (BERTScore loads a BERT model).

    Returns:
        Flat dict of metric_name → float.
    """
    if not predictions or not references:
        logger.warning("evaluate_summarization: empty inputs.")
        return {}

    results: Dict[str, float] = {}
    results.update(compute_rouge(predictions, references))
    results.update(compute_meteor(predictions, references))

    if not skip_bertscore:
        results.update(compute_bertscore(predictions, references))

    if section_summaries_list:
        results.update(compute_section_coverage(section_summaries_list))

    logger.info(
        "Summarization eval: ROUGE-L=%.4f  BERTScore-F1=%.4f  METEOR=%.4f",
        results.get("rougeL", 0),
        results.get("bertscore_f1", 0),
        results.get("meteor", 0),
    )
    return results
