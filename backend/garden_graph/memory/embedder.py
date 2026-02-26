"""Local embedding engine for semantic memory retrieval (Phase 2 — Roots).

Wraps sentence-transformers to produce 384-dim vectors entirely on-device.
The model is lazy-loaded on first use so it doesn't slow down server startup.

Configuration:
    EMBEDDING_MODEL  env var — defaults to 'all-MiniLM-L6-v2' (~80 MB).
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Optional

import numpy as np

log = logging.getLogger("garden.memory.embedder")

_DEFAULT_MODEL = "all-MiniLM-L6-v2"

# ---------------------------------------------------------------------------
# Singleton state
# ---------------------------------------------------------------------------
_instance: Optional[Embedder] = None
_instance_lock = threading.Lock()


class Embedder:
    """Thin wrapper around a SentenceTransformer model.

    The underlying model is loaded lazily on the first call to ``encode``
    or ``encode_batch`` so that importing this module is essentially free.
    """

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name or os.getenv("EMBEDDING_MODEL", _DEFAULT_MODEL)
        self._model = None  # loaded lazily
        self._load_lock = threading.Lock()

    # -- lazy loader --------------------------------------------------------

    def _ensure_model(self):
        """Load the SentenceTransformer model if it hasn't been loaded yet."""
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:  # double-check after acquiring lock
                return
            from sentence_transformers import SentenceTransformer

            log.info("Loading embedding model '%s' ...", self._model_name)
            self._model = SentenceTransformer(self._model_name)
            log.info("Embedding model ready (dim=%d).", self._model.get_sentence_embedding_dimension())

    # -- public API ---------------------------------------------------------

    def encode(self, text: str) -> np.ndarray:
        """Encode a single string into a 384-dim float32 vector."""
        self._ensure_model()
        return self._model.encode(text, convert_to_numpy=True)

    def encode_batch(self, texts: list[str]) -> np.ndarray:
        """Encode a list of strings. Returns an (N, 384) float32 array."""
        self._ensure_model()
        return self._model.encode(texts, convert_to_numpy=True)

    @staticmethod
    def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        """Cosine similarity between two vectors. Returns a value in [-1, 1]."""
        denom = np.linalg.norm(vec_a) * np.linalg.norm(vec_b)
        if denom == 0.0:
            return 0.0
        return float(np.dot(vec_a, vec_b) / denom)

    @staticmethod
    def search(
        query_vec: np.ndarray,
        corpus_vecs: np.ndarray,
        top_k: int = 5,
    ) -> list[tuple[int, float]]:
        """Find the *top_k* most similar vectors in *corpus_vecs*.

        Parameters
        ----------
        query_vec:    1-D array (384,)
        corpus_vecs:  2-D array (N, 384)
        top_k:        how many results to return

        Returns
        -------
        List of ``(index, similarity_score)`` sorted by score descending.
        """
        if corpus_vecs.size == 0:
            return []

        # normalise once
        query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
        corpus_norms = np.linalg.norm(corpus_vecs, axis=1, keepdims=True) + 1e-10
        normed_corpus = corpus_vecs / corpus_norms

        scores = normed_corpus @ query_norm  # (N,)
        k = min(top_k, len(scores))
        # argpartition is O(N) which is nicer than full sort for large corpora
        top_indices = np.argpartition(scores, -k)[-k:]
        top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]

        return [(int(i), float(scores[i])) for i in top_indices]


# ---------------------------------------------------------------------------
# Module-level accessor
# ---------------------------------------------------------------------------

def get_embedder() -> Optional[Embedder]:
    """Return the global ``Embedder`` singleton.

    Returns ``None`` (and logs a warning) if ``sentence-transformers`` is not
    installed, so callers can degrade gracefully.
    """
    global _instance  # noqa: PLW0603
    if _instance is not None:
        return _instance

    with _instance_lock:
        if _instance is not None:
            return _instance

        try:
            import sentence_transformers  # noqa: F401 — availability check
        except ImportError:
            log.warning(
                "sentence-transformers is not installed — embedding-based "
                "memory retrieval will be disabled.  Install it with: "
                "pip install sentence-transformers"
            )
            return None

        _instance = Embedder()
        return _instance
