"""
Dynamic Query-Conditioned Section Weights (DQSW).

Replaces the hardcoded ``SECTION_WEIGHTS`` dict in ``section_summarizer.py``
with a cross-attention layer that learns per-query, per-section importance
scores from retrieval-feedback signal.

Architecture
------------
    query_emb   : [B, D]
    section_embs: [B, S, D]   (one embedding per section)
    ──────────────────────────────────────────────────
    scores = softmax(query_emb @ section_embs.T / sqrt(D))   # [B, S]

The module is trained with a simple click/recall proxy loss:
  - Positive sample: section whose chunk appears in the top-K retrieved docs.
  - Negative sample: section whose chunk is NOT in top-K.

In practice this means:
  1. Run the HA-RAG pipeline on a set of training queries.
  2. Record which sections were retrieved.
  3. Call ``SectionWeightLearner.train()`` with the signal.

After training, ``get_weights(query_embedding, section_names)`` returns a
``{section_name: float}`` dict that replaces the hardcoded table.

Usage — Inference (drop-in)
---------------------------
    from apps.ml_engine.section_weight_learner import get_weight_learner

    learner = get_weight_learner()          # lazy singleton
    weights = learner.get_weights(
        query_embedding=q_emb,              # numpy array [D] or list[float]
        section_names=["Methodology", "Results", "Introduction"],
    )
    # → {"Methodology": 0.42, "Results": 0.38, "Introduction": 0.20}

Usage — Training
----------------
    from apps.ml_engine.section_weight_learner import SectionWeightLearner

    learner = SectionWeightLearner()
    learner.train(
        training_samples=[
            {
                "query_embedding": [0.1, 0.2, ...],
                "section_embeddings": {"Methodology": [...], "Results": [...]},
                "positive_sections": ["Methodology"],
            },
            ...
        ],
        model_path="section_weight_model.pt",
        num_epochs=10,
    )
"""
import logging
import os
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Path written/read by save() / load()
_DEFAULT_MODEL_PATH = os.path.join(
    os.path.dirname(__file__), "section_weight_model.pt"
)
_ENV_MODEL_PATH = "DQSW_MODEL_PATH"

# Embedding dimension of all-MiniLM-L6-v2
_DEFAULT_DIM = 384

# Canonical fallback weights (used when model unavailable)
_FALLBACK_WEIGHTS: Dict[str, float] = {
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


# ---------------------------------------------------------------------------
# Cross-attention weight layer (PyTorch)
# ---------------------------------------------------------------------------

class _CrossAttentionWeightLayer:
    """
    Lightweight cross-attention that produces section weights conditioned on
    a query embedding.

    Implemented in pure NumPy for inference so that PyTorch is only required
    for training.  A single weight matrix W is learned; the forward pass is::

        logits = section_embs @ W @ query_emb          # [S]
        weights = softmax(logits / sqrt(D))

    Attributes
    ----------
    W : ndarray of shape [D, D]
        Learned projection matrix (identity initialisation).
    dim : int
        Embedding dimension.
    """

    def __init__(self, dim: int = _DEFAULT_DIM):
        self.dim = dim
        self.W: np.ndarray = np.eye(dim, dtype=np.float32)  # identity init

    def forward(self, query_emb: np.ndarray, section_embs: np.ndarray) -> np.ndarray:
        """
        Args:
            query_emb:    [D] float32
            section_embs: [S, D] float32

        Returns:
            weights: [S] float32 summing to 1.0
        """
        projected = section_embs @ self.W @ query_emb  # [S]
        projected /= np.sqrt(self.dim)
        # Softmax
        exp_vals = np.exp(projected - projected.max())
        return (exp_vals / exp_vals.sum()).astype(np.float32)

    def save(self, path: str) -> None:
        np.save(path, {"W": self.W, "dim": self.dim})
        logger.info("DQSW model saved to '%s'.", path)

    @classmethod
    def load(cls, path: str) -> "_CrossAttentionWeightLayer":
        data = np.load(path, allow_pickle=True).item()
        obj = cls(dim=data["dim"])
        obj.W = data["W"]
        logger.info("DQSW model loaded from '%s'.", path)
        return obj


# ---------------------------------------------------------------------------
# Section embedding cache
# ---------------------------------------------------------------------------

def _embed(texts: List[str]) -> np.ndarray:
    """Embed a list of strings with the project's sentence-transformer."""
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")
    return model.encode(texts, convert_to_numpy=True, show_progress_bar=False)


# ---------------------------------------------------------------------------
# SectionWeightLearner — public API
# ---------------------------------------------------------------------------

class SectionWeightLearner:
    """
    Trains and serves Dynamic Query-Conditioned Section Weights (DQSW).

    Parameters
    ----------
    model_path:
        Where to save/load the learned weight matrix.  Defaults to
        ``DQSW_MODEL_PATH`` env var or ``section_weight_model.pt`` next to
        this file.
    dim:
        Embedding dimension (must match the sentence-transformer used).
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        dim: int = _DEFAULT_DIM,
    ):
        self._model_path = (
            model_path
            or os.environ.get(_ENV_MODEL_PATH)
            or _DEFAULT_MODEL_PATH
        )
        self._dim = dim
        self._layer: Optional[_CrossAttentionWeightLayer] = None

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        """Load the model from disk if not already in memory."""
        if self._layer is not None:
            return
        if os.path.exists(self._model_path):
            try:
                self._layer = _CrossAttentionWeightLayer.load(self._model_path)
                return
            except Exception as exc:
                logger.warning("DQSW load failed (%s); using identity init.", exc)
        self._layer = _CrossAttentionWeightLayer(dim=self._dim)

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def get_weights(
        self,
        query_embedding,
        section_names: List[str],
        section_embeddings: Optional[Dict[str, List[float]]] = None,
    ) -> Dict[str, float]:
        """
        Return per-section importance weights conditioned on the query.

        Args:
            query_embedding:   Query embedding as list/array of shape [D].
            section_names:     List of section names to score.
            section_embeddings: Optional pre-computed embeddings per section name.
                                If None, section names themselves are embedded.

        Returns:
            ``{section_name: weight_float}`` — weights sum to 1.0.
        """
        if not section_names:
            return {}

        self._ensure_loaded()

        q_emb = np.array(query_embedding, dtype=np.float32)
        if q_emb.ndim != 1 or q_emb.shape[0] != self._dim:
            logger.warning(
                "DQSW: query_embedding shape %s does not match dim=%d; "
                "falling back to hardcoded weights.",
                q_emb.shape,
                self._dim,
            )
            return self._fallback_weights(section_names)

        # Build section embedding matrix
        if section_embeddings:
            try:
                sec_emb_matrix = np.array(
                    [section_embeddings[s] for s in section_names], dtype=np.float32
                )
            except KeyError:
                sec_emb_matrix = _embed(section_names)
        else:
            sec_emb_matrix = _embed(section_names)

        raw_weights = self._layer.forward(q_emb, sec_emb_matrix)  # [S]
        return {name: float(raw_weights[i]) for i, name in enumerate(section_names)}

    @staticmethod
    def _fallback_weights(section_names: List[str]) -> Dict[str, float]:
        """Return normalised hardcoded weights for the given sections."""
        raw = {s: _FALLBACK_WEIGHTS.get(s, 0.10) for s in section_names}
        total = sum(raw.values()) or 1.0
        return {s: v / total for s, v in raw.items()}

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(
        self,
        training_samples: List[Dict],
        model_path: Optional[str] = None,
        num_epochs: int = 20,
        learning_rate: float = 1e-3,
    ) -> None:
        """
        Fine-tune the cross-attention weight matrix from retrieval signal.

        Each training sample must contain:
        - ``"query_embedding"``      : list[float] of shape [D]
        - ``"section_embeddings"``   : dict[section_name → list[float] of shape [D]]
        - ``"positive_sections"``    : list[str] — sections retrieved in top-K

        Args:
            training_samples: List of labelled retrieval outcomes.
            model_path:       Override save path.
            num_epochs:       Training epochs.
            learning_rate:    SGD step size.
        """
        try:
            import torch
            import torch.nn as nn
        except ImportError as exc:
            raise ImportError("Training requires PyTorch: pip install torch") from exc

        save_path = model_path or self._model_path
        logger.info("Training DQSW on %d samples for %d epochs.", len(training_samples), num_epochs)

        # Initialise a learnable matrix
        W = nn.Parameter(torch.eye(self._dim, dtype=torch.float32))
        optimiser = torch.optim.Adam([W], lr=learning_rate)
        loss_fn = nn.BCEWithLogitsLoss()

        for epoch in range(num_epochs):
            epoch_loss = 0.0
            for sample in training_samples:
                q = torch.tensor(sample["query_embedding"], dtype=torch.float32)  # [D]
                sec_embs = sample["section_embeddings"]
                positives = set(sample["positive_sections"])

                sections = list(sec_embs.keys())
                s_matrix = torch.tensor(
                    [sec_embs[s] for s in sections], dtype=torch.float32
                )  # [S, D]

                # Labels: 1.0 for positive sections, 0.0 for others
                labels = torch.tensor(
                    [1.0 if s in positives else 0.0 for s in sections],
                    dtype=torch.float32,
                )

                # Forward: logits = s_matrix @ W @ q / sqrt(D)
                logits = (s_matrix @ W @ q) / (self._dim ** 0.5)

                loss = loss_fn(logits, labels)
                optimiser.zero_grad()
                loss.backward()
                optimiser.step()
                epoch_loss += loss.item()

            if (epoch + 1) % 5 == 0 or epoch == 0:
                logger.info(
                    "Epoch %d/%d — loss=%.6f", epoch + 1, num_epochs,
                    epoch_loss / max(len(training_samples), 1),
                )

        # Save
        learned_W = W.detach().numpy().astype(np.float32)
        self._layer = _CrossAttentionWeightLayer(dim=self._dim)
        self._layer.W = learned_W
        self._layer.save(save_path)

    def collect_training_signal(
        self,
        queries: List[str],
        k: int = 10,
    ) -> List[Dict]:
        """
        Automatically collect DQSW training signal by running the live
        HA-RAG pipeline and recording which sections were retrieved.

        Args:
            queries: List of query strings.
            k:       Top-K retrieval cutoff.

        Returns:
            List of training samples ready for ``train()``.
        """
        from sentence_transformers import SentenceTransformer

        encoder = SentenceTransformer("all-MiniLM-L6-v2")
        from apps.ml_engine.multi_agent_retrieval import get_orchestrator
        orchestrator = get_orchestrator()

        training_samples = []
        for query in queries:
            try:
                q_emb = encoder.encode(query, convert_to_numpy=True)
                chunks = orchestrator.search(query, n_results=k)

                # Determine which sections appeared in retrieved chunks
                positive_sections: List[str] = list({
                    c.get("metadata", {}).get("section", "Other")
                    for c in chunks
                    if c.get("metadata", {}).get("section")
                })

                # Collect all unique sections seen
                all_sections = list(_FALLBACK_WEIGHTS.keys())
                sec_embs = {s: encoder.encode(s, convert_to_numpy=True).tolist() for s in all_sections}

                training_samples.append({
                    "query_embedding": q_emb.tolist(),
                    "section_embeddings": sec_embs,
                    "positive_sections": positive_sections,
                })
            except Exception as exc:
                logger.warning("Signal collection failed for query '%s': %s", query[:50], exc)

        logger.info("Collected %d training samples.", len(training_samples))
        return training_samples


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_learner: Optional[SectionWeightLearner] = None


def get_weight_learner() -> SectionWeightLearner:
    """Return the module-level DQSW singleton (lazy init)."""
    global _learner
    if _learner is None:
        _learner = SectionWeightLearner()
    return _learner
