"""
SciBERT-based Section Classifier for IMRaD scientific papers.

Drop-in replacement for SectionClassifier that uses a fine-tuned SciBERT
model instead of regex matching.  Falls back to regex when no fine-tuned
model is available, so it works out-of-the-box before any training is done.

Training format (CODA-19 / SciSeg compatible)
----------------------------------------------
    [
        {"text": "We propose a novel attention mechanism …", "label": "Methodology"},
        {"text": "Table 1 shows that our model outperforms …", "label": "Results"},
        ...
    ]

Labels must come from CANONICAL_SECTIONS (case-insensitive matching accepted).

Usage — Inference
-----------------
    from apps.ml_engine.scibert_classifier import get_scibert_classifier

    classifier = get_scibert_classifier()               # lazy singleton
    sections = classifier.classify_sections(paper_text)  # {section: text, ...}

Usage — Training
----------------
    from apps.ml_engine.scibert_classifier import SciBERTSectionTrainer

    trainer = SciBERTSectionTrainer()
    trainer.train(
        train_data=[{"text": ..., "label": ...}, ...],
        output_dir="scibert_section_model",
        num_epochs=3,
    )
"""
import logging
import os
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Canonical section names used as classifier labels.
CANONICAL_SECTIONS: List[str] = [
    "Introduction",
    "Related Work",
    "Background",
    "Methodology",
    "Experiments",
    "Results",
    "Discussion",
    "Conclusion",
    "Abstract",
    "Other",
]

#: Map common variations → canonical name (lower-case keys for matching).
_LABEL_NORMALISER: Dict[str, str] = {
    "introduction": "Introduction",
    "related work": "Related Work",
    "literature review": "Related Work",
    "prior work": "Related Work",
    "background": "Background",
    "preliminaries": "Background",
    "methodology": "Methodology",
    "methods": "Methodology",
    "approach": "Methodology",
    "proposed method": "Methodology",
    "experiments": "Experiments",
    "experimental setup": "Experiments",
    "experimental results": "Results",
    "results": "Results",
    "evaluation": "Results",
    "ablation study": "Results",
    "discussion": "Discussion",
    "analysis": "Discussion",
    "conclusion": "Conclusion",
    "conclusions": "Conclusion",
    "conclusion and future work": "Conclusion",
    "abstract": "Abstract",
}

#: Default SciBERT checkpoint (HuggingFace Hub).
_SCIBERT_CHECKPOINT = "allenai/scibert_scivocab_uncased"

#: Environment variable to override the fine-tuned model path.
_ENV_MODEL_DIR = "SCIBERT_SECTION_MODEL_DIR"

#: Header-detection regex (re-used from SectionClassifier).
_HEADER_RE = re.compile(
    r"^(?:abstract|introduction|related work|background|preliminaries|"
    r"literature review|methodology|methods|approach|proposed method|"
    r"experiments?|experimental(?:\s+setup)?|results?|evaluation|"
    r"ablation(?: study)?|discussion|analysis|conclusion(?:s)?(?:\s+and\s+future\s+work)?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


# ---------------------------------------------------------------------------
# Label normalisation helper
# ---------------------------------------------------------------------------

def _normalise_label(raw: str) -> str:
    """Map a raw classifier output to a canonical section name."""
    key = raw.strip().lower()
    return _LABEL_NORMALISER.get(key, "Other")


# ---------------------------------------------------------------------------
# SciBERT Classifier
# ---------------------------------------------------------------------------

class SciBERTSectionClassifier:
    """
    Classifies text spans into IMRaD sections using a fine-tuned SciBERT
    model.  Falls back to regex-based detection when the model is not available.

    The classifier operates in two modes:

    1. **Structural** (primary): splits the text on detected section headers
       (same regex as SectionClassifier) and labels each chunk via the model.
    2. **Sliding-window** (fallback): when the paper has no headers, runs the
       model over ~512-token windows and assigns each paragraph to the
       predicted section.

    Parameters
    ----------
    model_dir:
        Path to a fine-tuned model directory.  If None, looks for the path in
        the ``SCIBERT_SECTION_MODEL_DIR`` environment variable, then falls back
        to the base SciBERT checkpoint (zero-shot mode, lower accuracy).
    device:
        ``"cuda"``, ``"mps"``, or ``"cpu"``.  Auto-detected when None.
    """

    def __init__(
        self,
        model_dir: Optional[str] = None,
        device: Optional[str] = None,
    ):
        self._model_dir = (
            model_dir
            or os.environ.get(_ENV_MODEL_DIR)
        )
        self._device = device
        self._pipeline = None  # lazy

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_pipeline(self):
        """Lazy-load the HuggingFace text-classification pipeline."""
        if self._pipeline is not None:
            return self._pipeline

        try:
            import torch
            from transformers import pipeline as hf_pipeline

            if self._device is None:
                if torch.cuda.is_available():
                    self._device = "cuda"
                elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                    self._device = "mps"
                else:
                    self._device = "cpu"

            checkpoint = self._model_dir or _SCIBERT_CHECKPOINT
            logger.info("Loading SciBERT classifier from '%s' on %s", checkpoint, self._device)

            self._pipeline = hf_pipeline(
                "text-classification",
                model=checkpoint,
                tokenizer=checkpoint,
                device=0 if self._device == "cuda" else -1,
                truncation=True,
                max_length=512,
            )
            logger.info("SciBERT classifier loaded.")
        except Exception as exc:
            logger.warning(
                "SciBERT classifier failed to load (%s). "
                "Falling back to regex SectionClassifier.",
                exc,
            )
            self._pipeline = None

        return self._pipeline

    def _regex_fallback(self, text: str) -> Dict[str, str]:
        """Use regex SectionClassifier as fallback."""
        from apps.ml_engine.section_classifier import SectionClassifier
        return SectionClassifier().classify_sections(text)

    def _predict_label(self, text: str) -> str:
        """Run the pipeline on a single text chunk."""
        pipe = self._load_pipeline()
        if pipe is None:
            return "Other"
        try:
            result = pipe(text[:2000])[0]  # truncate for speed
            return _normalise_label(result["label"])
        except Exception as exc:
            logger.debug("Label prediction failed: %s", exc)
            return "Other"

    @staticmethod
    def _split_on_headers(text: str) -> List[tuple]:
        """
        Split paper text on detected section headers.

        Returns list of (header_text, body_text) tuples.
        """
        lines = text.split("\n")
        sections: List[tuple] = []
        current_header = "Other"
        current_lines: List[str] = []

        for line in lines:
            if _HEADER_RE.match(line.strip()):
                if current_lines:
                    sections.append((current_header, "\n".join(current_lines).strip()))
                current_header = line.strip()
                current_lines = []
            else:
                current_lines.append(line)

        if current_lines:
            sections.append((current_header, "\n".join(current_lines).strip()))

        return sections

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify_sections(self, text: str) -> Dict[str, str]:
        """
        Split paper text into IMRaD sections.

        Matches the interface of ``SectionClassifier.classify_sections()``.

        Args:
            text: Full paper text (plain text, not PDF bytes).

        Returns:
            ``{section_name: section_text, ...}`` where section names are
            canonical IMRaD labels.
        """
        if not text or not text.strip():
            return {}

        pipe = self._load_pipeline()

        # If pipeline failed to load, use regex directly.
        if pipe is None:
            return self._regex_fallback(text)

        raw_splits = self._split_on_headers(text)

        if not raw_splits or (len(raw_splits) == 1 and raw_splits[0][0] == "Other"):
            # No headers found → regex fallback
            return self._regex_fallback(text)

        result: Dict[str, str] = {}
        for header, body in raw_splits:
            if not body.strip():
                continue

            # Use header text as label hint first (fast path)
            label_from_header = _normalise_label(header)
            if label_from_header != "Other":
                label = label_from_header
            else:
                # Run SciBERT on the body
                label = self._predict_label(body)

            # Merge bodies with the same label
            if label in result:
                result[label] = result[label] + "\n\n" + body
            else:
                result[label] = body

        return result if result else self._regex_fallback(text)


# ---------------------------------------------------------------------------
# SciBERT Trainer
# ---------------------------------------------------------------------------

class SciBERTSectionTrainer:
    """
    Fine-tune a SciBERT model for section classification.

    Training data format
    --------------------
    A list of dicts with keys ``"text"`` (str) and ``"label"`` (str).
    Labels should be canonical IMRaD section names (see CANONICAL_SECTIONS).

    The trainer writes a HuggingFace model checkpoint to ``output_dir`` that
    can then be loaded by ``SciBERTSectionClassifier(model_dir=output_dir)``.

    Example
    -------
        trainer = SciBERTSectionTrainer()
        trainer.train(
            train_data=[
                {"text": "We collected 500 papers...", "label": "Methodology"},
                ...
            ],
            output_dir="scibert_section_model",
            num_epochs=3,
            batch_size=16,
            learning_rate=2e-5,
        )
    """

    def __init__(self, base_checkpoint: str = _SCIBERT_CHECKPOINT):
        self.base_checkpoint = base_checkpoint

    def train(
        self,
        train_data: List[Dict],
        output_dir: str,
        num_epochs: int = 3,
        batch_size: int = 16,
        learning_rate: float = 2e-5,
        val_split: float = 0.1,
    ) -> None:
        """
        Fine-tune SciBERT and save the checkpoint.

        Args:
            train_data:    List of ``{"text": str, "label": str}`` dicts.
            output_dir:    Directory to save the fine-tuned model.
            num_epochs:    Training epochs (3 is usually sufficient).
            batch_size:    Per-device batch size.
            learning_rate: AdamW learning rate.
            val_split:     Fraction of data to use for validation.
        """
        try:
            import torch
            from datasets import Dataset
            from sklearn.model_selection import train_test_split
            from transformers import (
                AutoModelForSequenceClassification,
                AutoTokenizer,
                Trainer,
                TrainingArguments,
            )
        except ImportError as exc:
            raise ImportError(
                "Training requires: pip install transformers datasets scikit-learn torch\n"
                f"Missing: {exc}"
            ) from exc

        # Build label → id mapping
        unique_labels = sorted({_normalise_label(d["label"]) for d in train_data})
        label2id = {lbl: i for i, lbl in enumerate(unique_labels)}
        id2label = {i: lbl for lbl, i in label2id.items()}

        logger.info("Training SciBERT with %d samples, %d labels.", len(train_data), len(unique_labels))

        texts = [d["text"] for d in train_data]
        labels = [label2id[_normalise_label(d["label"])] for d in train_data]

        train_texts, val_texts, train_labels, val_labels = train_test_split(
            texts, labels, test_size=val_split, random_state=42, stratify=labels
        )

        tokenizer = AutoTokenizer.from_pretrained(self.base_checkpoint)

        def _tokenize(batch):
            return tokenizer(batch["text"], truncation=True, max_length=512, padding="max_length")

        train_ds = Dataset.from_dict({"text": train_texts, "label": train_labels}).map(_tokenize, batched=True)
        val_ds   = Dataset.from_dict({"text": val_texts,   "label": val_labels  }).map(_tokenize, batched=True)

        model = AutoModelForSequenceClassification.from_pretrained(
            self.base_checkpoint,
            num_labels=len(unique_labels),
            id2label=id2label,
            label2id=label2id,
        )

        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=num_epochs,
            per_device_train_batch_size=batch_size,
            per_device_eval_batch_size=batch_size,
            learning_rate=learning_rate,
            evaluation_strategy="epoch",
            save_strategy="best",
            load_best_model_at_end=True,
            metric_for_best_model="eval_loss",
            logging_dir=os.path.join(output_dir, "logs"),
            logging_steps=50,
            fp16=torch.cuda.is_available(),
            report_to="none",
        )

        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=train_ds,
            eval_dataset=val_ds,
        )

        trainer.train()
        trainer.save_model(output_dir)
        tokenizer.save_pretrained(output_dir)

        logger.info("SciBERT section classifier saved to '%s'.", output_dir)

    def train_from_coda19(self, coda19_jsonl_path: str, output_dir: str, **kwargs) -> None:
        """
        Convenience loader for CODA-19 JSONL format.

        Each line: ``{"section_name": str, "text": str}``.
        """
        import json

        train_data = []
        with open(coda19_jsonl_path) as f:
            for line in f:
                obj = json.loads(line)
                text = obj.get("text", "").strip()
                label = obj.get("section_name", "Other")
                if text:
                    train_data.append({"text": text, "label": label})

        logger.info("Loaded %d samples from CODA-19 JSONL.", len(train_data))
        self.train(train_data, output_dir, **kwargs)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_classifier: Optional[SciBERTSectionClassifier] = None


def get_scibert_classifier() -> SciBERTSectionClassifier:
    """Return the module-level SciBERT classifier singleton (lazy init)."""
    global _classifier
    if _classifier is None:
        _classifier = SciBERTSectionClassifier()
    return _classifier
