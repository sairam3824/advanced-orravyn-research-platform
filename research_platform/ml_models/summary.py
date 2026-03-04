"""
ml_models/summary.py
====================
Central summarization module for the Orravyn research platform.

Underlying model: facebook/bart-large-cnn (HuggingFace transformers)
  - Standard, reproducible, open-source summarization baseline
  - Loaded lazily as a singleton; runs on CPU / MPS / CUDA automatically
  - No external API calls — fully local inference

This matters for the conference paper: the research contribution is the
Section-Aware Hierarchical Summarization pipeline (section detection +
adaptive weighting + retrieval boosting), not the underlying model.
Using a well-known open baseline (BART-large-CNN) makes that contribution
clear and reproducible.

Public API
----------
  summarize_text(text)               -> str | None
  summarize_text_from_pdf(pdf_file)  -> str
  hierarchical_summarize(text)       -> str
  BARTSummarizer                     -> class (drop-in replacement)
"""

import logging
import re
from typing import List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL_NAME = "facebook/bart-large-cnn"

# BART-large-CNN input limit is 1024 tokens (~700–800 words in practice).
# We cap at 600 words to stay safely within the tokenizer limit.
MAX_INPUT_WORDS_PER_CALL = 600

MAX_WORDS_PER_CHUNK = 500   # chunk size fed to the model
MAX_CHUNKS = 30             # safety cap for very long papers

# BART generation parameters — tuned for academic text
BART_MIN_LENGTH = 80
BART_MAX_LENGTH = 250
BART_NUM_BEAMS = 4
BART_LENGTH_PENALTY = 2.0


# ---------------------------------------------------------------------------
# Model singleton — loaded once, reused across all calls
# ---------------------------------------------------------------------------

_pipeline = None


def _get_pipeline():
    """Lazily load the BART summarization pipeline (singleton)."""
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    try:
        from transformers import pipeline
        import torch

        # Pick best available device
        if torch.cuda.is_available():
            device = 0          # first CUDA GPU
        elif torch.backends.mps.is_available():
            device = "mps"      # Apple Silicon
        else:
            device = -1         # CPU

        logger.info("Loading %s on device=%s …", MODEL_NAME, device)
        _pipeline = pipeline(
            "summarization",
            model=MODEL_NAME,
            device=device,
        )
        logger.info("%s loaded successfully.", MODEL_NAME)
        return _pipeline

    except Exception as exc:
        logger.error("Failed to load %s: %s", MODEL_NAME, exc)
        return None


# ---------------------------------------------------------------------------
# Text chunking helpers
# ---------------------------------------------------------------------------

def split_into_sentences(text: str) -> List[str]:
    """Split text into sentences on sentence-ending punctuation."""
    text = text.strip()
    if not text:
        return []
    return re.split(r'(?<=[.!?])\s+', text)


def chunk_sentences_by_wordcount(
    sentences: List[str],
    max_words: int = MAX_WORDS_PER_CHUNK,
) -> List[str]:
    """
    Group sentences into chunks that do not exceed max_words.
    Sentences longer than max_words are split on word boundaries.
    """
    chunks: List[str] = []
    current: List[str] = []
    current_words = 0

    for sentence in sentences:
        word_count = len(sentence.split())

        if word_count > max_words:
            if current:
                chunks.append(" ".join(current))
                current, current_words = [], 0
            words = sentence.split()
            for i in range(0, len(words), max_words):
                chunks.append(" ".join(words[i : i + max_words]))
            continue

        if current_words + word_count <= max_words:
            current.append(sentence)
            current_words += word_count
        else:
            chunks.append(" ".join(current))
            current, current_words = [sentence], word_count

    if current:
        chunks.append(" ".join(current))

    return chunks


# ---------------------------------------------------------------------------
# Core BART inference call
# ---------------------------------------------------------------------------

def _run_bart(text: str) -> Optional[str]:
    """
    Run BART-large-CNN on a single text passage.

    Truncates input to MAX_INPUT_WORDS_PER_CALL words before inference
    to stay within the model's 1024-token limit.

    Returns the summary string, or None on failure.
    """
    if not text or not text.strip():
        return ""

    words = text.split()
    if len(words) > MAX_INPUT_WORDS_PER_CALL:
        logger.debug(
            "_run_bart: truncating input %d → %d words.", len(words), MAX_INPUT_WORDS_PER_CALL
        )
        text = " ".join(words[:MAX_INPUT_WORDS_PER_CALL])

    pipe = _get_pipeline()
    if pipe is None:
        logger.error("_run_bart: pipeline not available.")
        return None

    try:
        result = pipe(
            text,
            min_length=BART_MIN_LENGTH,
            max_length=BART_MAX_LENGTH,
            num_beams=BART_NUM_BEAMS,
            length_penalty=BART_LENGTH_PENALTY,
            truncation=True,
        )
        summary = result[0]["summary_text"].strip()
        logger.debug("_run_bart: produced %d-word summary.", len(summary.split()))
        return summary
    except Exception as exc:
        logger.error("_run_bart inference failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def summarize_text(text: str, max_words_per_chunk: int = 400) -> Optional[str]:  # noqa: ARG001
    """
    Summarize a plain-text passage using BART-large-CNN.

    Args:
        text:                Raw text to summarize.
        max_words_per_chunk: Kept for API backward-compatibility.

    Returns:
        Summary string, or None on failure.
    """
    return _run_bart(text)


def summarize_text_from_pdf(pdf_file, max_words_per_chunk: int = 400) -> str:
    """
    Extract text from a PDF FieldFile / file-like object and summarize it.

    Fallback used by signals.process_summary() when section-aware
    summarization cannot run (e.g. scanned PDFs with < 100 extractable words).

    Returns:
        Summary string. Never returns None.
    """
    try:
        from apps.ml_engine.pdf_text_extractor import extract_pdf_text_from_file

        text = extract_pdf_text_from_file(pdf_file)
        if not text or not text.strip():
            logger.warning("summarize_text_from_pdf: no extractable text in PDF.")
            return "Could not extract text from the PDF file."

        result = summarize_text(text, max_words_per_chunk=max_words_per_chunk)
        return result if result else "Summary generation failed."

    except Exception as exc:
        logger.error("summarize_text_from_pdf failed: %s", exc)
        return "Error processing PDF file."


def hierarchical_summarize(text: str, max_words_per_chunk: int = MAX_WORDS_PER_CHUNK) -> str:
    """
    Two-pass hierarchical summarization using BART-large-CNN:
      Pass 1 — chunk the text and summarize each chunk independently.
      Pass 2 — summarize the combined chunk summaries.

    Args:
        text:                Full input text.
        max_words_per_chunk: Max words per chunk before summarizing.

    Returns:
        Final summary string.
    """
    sentences = split_into_sentences(text)
    chunks = chunk_sentences_by_wordcount(sentences, max_words=max_words_per_chunk)

    if not chunks:
        return "No content to summarize."

    if len(chunks) > MAX_CHUNKS:
        logger.warning(
            "hierarchical_summarize: %d chunks exceeds MAX_CHUNKS=%d; truncating.",
            len(chunks), MAX_CHUNKS,
        )
        chunks = chunks[:MAX_CHUNKS]

    logger.info("hierarchical_summarize: pass 1 — %d chunks.", len(chunks))

    chunk_summaries: List[str] = []
    for i, chunk in enumerate(chunks, start=1):
        summary = _run_bart(chunk)
        if summary:
            chunk_summaries.append(summary)
        else:
            logger.warning(
                "hierarchical_summarize: chunk %d/%d failed; skipping.", i, len(chunks)
            )

    if not chunk_summaries:
        return "Summary generation failed for all chunks."

    combined = " ".join(chunk_summaries)

    # Final pass if combined summaries are still long
    if len(combined.split()) > max_words_per_chunk:
        logger.info("hierarchical_summarize: pass 2 — final summarization.")
        final = _run_bart(combined)
        return final if final else combined

    return combined


# ---------------------------------------------------------------------------
# BARTSummarizer class  (drop-in replacement — same interface as before)
# ---------------------------------------------------------------------------

class BARTSummarizer:
    """
    Class interface for BART-large-CNN summarization.

    Constructor arguments (model_path, base_model) are accepted for
    backward-compatibility but ignored — the model is always loaded
    from HuggingFace as facebook/bart-large-cnn.
    """

    def __init__(self, model_path: str = None, base_model: str = MODEL_NAME):  # noqa: ARG001
        self.model_name = MODEL_NAME
        # Eagerly load the pipeline so first inference isn't slow
        _get_pipeline()
        logger.info("BARTSummarizer ready (%s).", MODEL_NAME)

    def summarize_text(self, text: str, max_length: int = 256, min_length: int = 50, **kwargs) -> str:  # noqa: ARG001
        result = _run_bart(text)
        return result if result else "Summary not available."

    def summarize_chunks(self, text_chunks: List[str], **kwargs) -> List[str]:
        return [self.summarize_text(chunk, **kwargs) for chunk in text_chunks]

    def hierarchical_summarize(
        self,
        text_chunks: List[str],
        chunk_max_length: int = 128,  # noqa: ARG001
        final_max_length: int = 256,  # noqa: ARG001
    ) -> str:
        if not text_chunks:
            return "No content to summarize."
        if len(text_chunks) == 1:
            return self.summarize_text(text_chunks[0])
        chunk_summaries = self.summarize_chunks(text_chunks)
        combined = " ".join(chunk_summaries)
        return self.summarize_text(combined)


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 2:
        print("Usage: python summary.py '<text to summarise>'")
        sys.exit(1)

    result = hierarchical_summarize(" ".join(sys.argv[1:]))
    print("\n--- SUMMARY ---")
    print(result)
