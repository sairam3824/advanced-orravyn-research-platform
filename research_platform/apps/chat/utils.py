"""
Chat moderation utilities.

The Keras hate-speech model and tokenizer artefacts are stored under
  apps/ml_engine/ml_models/hate_speech_detection.keras
  apps/ml_engine/ml_models/tokenizer.pkl

Moderation is enabled automatically when the model files are present on disk.
If the files are absent or dependencies are missing the module falls back to a
no-op stub so the rest of the application is unaffected.
"""
import os
import logging
import re
import pickle
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────────
_BASE = Path(__file__).resolve().parent.parent  # apps/
_MODEL_PATH = _BASE / 'ml_engine' / 'ml_models' / 'hate_speech_detection.keras'
_TOKENIZER_PATH = _BASE / 'ml_engine' / 'ml_models' / 'tokenizer.pkl'

MAX_LEN = 100
LABELS = ['hate', 'offensive', 'neutral']

# ── Lazy-loaded singletons ─────────────────────────────────────────────────────
_model = None
_tokenizer = None
_moderation_available = None   # tri-state: None = unchecked


def _load_resources():
    """Try to load the Keras model and tokenizer once; cache the result."""
    global _model, _tokenizer, _moderation_available

    if _moderation_available is not None:
        return _moderation_available

    if not _MODEL_PATH.exists() or not _TOKENIZER_PATH.exists():
        logger.info("Hate-speech model files not found — moderation disabled.")
        _moderation_available = False
        return False

    try:
        import numpy as np  # noqa: F401 — verify numpy is present
        import tensorflow as tf  # noqa: F401
        from tensorflow import keras

        _model = keras.models.load_model(str(_MODEL_PATH))
        with open(_TOKENIZER_PATH, 'rb') as fh:
            _tokenizer = pickle.load(fh)
        _moderation_available = True
        logger.info("Hate-speech moderation model loaded successfully.")
        return True
    except Exception as exc:
        logger.warning(f"Could not load moderation model: {exc}")
        _moderation_available = False
        return False


# ── Pre-processing ─────────────────────────────────────────────────────────────
_ESSENTIAL_WORDS = {"i", "you", "love", "hate", "he", "she", "they", "we", "it"}
_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "up", "about", "into", "through",
    "during", "before", "after", "above", "below", "between", "out",
    "off", "over", "under", "then", "once", "here", "there", "when",
    "where", "why", "how", "all", "both", "each", "few", "more", "most",
    "other", "some", "such", "than", "too", "very", "just", "but", "or",
    "and", "so", "if",
} - _ESSENTIAL_WORDS


def _preprocess(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    tokens = [w for w in text.split() if w not in _STOPWORDS]
    # Basic lemmatisation: strip common suffixes
    lemmatized = []
    for token in tokens:
        if token.endswith('ing') and len(token) > 5:
            token = token[:-3]
        elif token.endswith('ed') and len(token) > 4:
            token = token[:-2]
        elif token.endswith('ly') and len(token) > 4:
            token = token[:-2]
        lemmatized.append(token)
    return " ".join(lemmatized)


def _tokenize_and_pad(texts):
    from tensorflow.keras.preprocessing.sequence import pad_sequences  # type: ignore
    sequences = _tokenizer.texts_to_sequences(texts)
    return pad_sequences(sequences, maxlen=MAX_LEN, padding='post', truncating='post')


# ── Public API ─────────────────────────────────────────────────────────────────

def predict_batch(messages: list, threshold: float = 0.5) -> list:
    """
    Classify a list of messages.

    Returns a list of label strings ('hate', 'offensive', 'neutral', or
    'uncertain' when max confidence is below *threshold*).
    Falls back to 'neutral' for every message if the model is unavailable.
    """
    if not _load_resources():
        return ['neutral'] * len(messages)

    try:
        import numpy as np
        processed = [_preprocess(m) for m in messages]
        padded = _tokenize_and_pad(processed)
        probs = _model.predict(padded, verbose=0)
        results = []
        for prob in probs:
            idx = int(np.argmax(prob))
            if prob[idx] < threshold:
                results.append('uncertain')
            else:
                results.append(LABELS[idx])
        return results
    except Exception as exc:
        logger.error(f"Moderation prediction failed: {exc}")
        return ['neutral'] * len(messages)


def is_offensive(message: str, threshold: float = 0.5) -> bool:
    """Return True if *message* is classified as 'hate' or 'offensive'."""
    if not message or not message.strip():
        return False
    label = predict_batch([message], threshold=threshold)[0]
    return label in ('hate', 'offensive')
