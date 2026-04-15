"""Embedding engine for semantic memory retrieval (Phase 2 — Roots).

Supports multiple backends:
  - "local"    — sentence-transformers on-device (default, ~80MB)
  - "lmstudio" — LM Studio API (e.g. via Tailscale to home server)
  - "openai"   — OpenAI embeddings API
  - "openrouter" — any OpenAI-compatible endpoint

Configuration (env vars):
    EMBEDDING_BACKEND    — "local" | "lmstudio" | "openai" | "openrouter"
    EMBEDDING_MODEL      — model name (backend-specific default if unset)
    EMBEDDING_API_URL    — API base URL for lmstudio/openrouter
    EMBEDDING_API_KEY    — API key for openai/openrouter
    EMBEDDING_DIM        — expected dimension (auto-detected when possible)
"""
from __future__ import annotations

import logging
import os
import threading
from abc import ABC, abstractmethod
from typing import Optional

import numpy as np

log = logging.getLogger("garden.memory.embedder")

# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class EmbedderBackend(ABC):
    """Common interface for all embedding backends."""

    @abstractmethod
    def encode(self, text: str) -> np.ndarray:
        """Encode a single text into a float32 vector."""

    @abstractmethod
    def encode_batch(self, texts: list[str]) -> np.ndarray:
        """Encode multiple texts. Returns (N, dim) float32 array."""

    @property
    @abstractmethod
    def dim(self) -> int:
        """Embedding dimensionality."""


# ---------------------------------------------------------------------------
# Backend: local sentence-transformers
# ---------------------------------------------------------------------------

class LocalEmbedder(EmbedderBackend):
    """On-device embeddings via sentence-transformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._model = None
        self._load_lock = threading.Lock()
        self._dim: int | None = None

    def _ensure_model(self):
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            from sentence_transformers import SentenceTransformer
            log.info("Loading local embedding model '%s' ...", self._model_name)
            self._model = SentenceTransformer(self._model_name)
            self._dim = self._model.get_sentence_embedding_dimension()
            log.info("Local embedding model ready (dim=%d).", self._dim)

    def encode(self, text: str) -> np.ndarray:
        self._ensure_model()
        return self._model.encode(text, convert_to_numpy=True)

    def encode_batch(self, texts: list[str]) -> np.ndarray:
        self._ensure_model()
        return self._model.encode(texts, convert_to_numpy=True)

    @property
    def dim(self) -> int:
        self._ensure_model()
        return self._dim


# ---------------------------------------------------------------------------
# Backend: OpenAI-compatible API (LM Studio, OpenRouter, OpenAI)
# ---------------------------------------------------------------------------

class APIEmbedder(EmbedderBackend):
    """Embeddings via any OpenAI-compatible /v1/embeddings endpoint.

    Works with:
      - LM Studio (local or via Tailscale)
      - OpenAI API
      - OpenRouter
      - Any other compatible server
    """

    def __init__(self, base_url: str, api_key: str = "", model: str = "text-embedding-ada-002",
                 dim: int | None = None):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._dim_override = dim
        self._detected_dim: int | None = None

    def _call_api(self, texts: list[str]) -> list[list[float]]:
        import httpx

        url = f"{self._base_url}/v1/embeddings"
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        payload = {"input": texts, "model": self._model}

        response = httpx.post(url, json=payload, headers=headers, timeout=30.0)
        response.raise_for_status()
        data = response.json()

        # Sort by index to guarantee order
        embeddings = sorted(data["data"], key=lambda x: x["index"])
        return [e["embedding"] for e in embeddings]

    def encode(self, text: str) -> np.ndarray:
        vecs = self._call_api([text])
        result = np.array(vecs[0], dtype=np.float32)
        if self._detected_dim is None:
            self._detected_dim = len(result)
            log.info("API embedder dim auto-detected: %d", self._detected_dim)
        return result

    def encode_batch(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.array([], dtype=np.float32).reshape(0, self.dim)
        vecs = self._call_api(texts)
        result = np.array(vecs, dtype=np.float32)
        if self._detected_dim is None:
            self._detected_dim = result.shape[1]
            log.info("API embedder dim auto-detected: %d", self._detected_dim)
        return result

    @property
    def dim(self) -> int:
        if self._dim_override:
            return self._dim_override
        if self._detected_dim:
            return self._detected_dim
        # Probe with a dummy call
        self.encode("dim probe")
        return self._detected_dim


# ---------------------------------------------------------------------------
# Unified Embedder facade
# ---------------------------------------------------------------------------

class Embedder:
    """Unified embedding interface. Delegates to the configured backend.

    The backend is selected via the EMBEDDING_BACKEND env var:
      - "local" (default): sentence-transformers on-device
      - "lmstudio": LM Studio API (set EMBEDDING_API_URL)
      - "openai": OpenAI API (set EMBEDDING_API_KEY)
      - "openrouter": any OpenAI-compatible (set EMBEDDING_API_URL + EMBEDDING_API_KEY)
    """

    def __init__(self):
        backend_name = os.getenv("EMBEDDING_BACKEND", "local").lower()
        model = os.getenv("EMBEDDING_MODEL", "")
        api_url = os.getenv("EMBEDDING_API_URL", "")
        api_key = os.getenv("EMBEDDING_API_KEY", "")
        dim = int(os.getenv("EMBEDDING_DIM", "0")) or None

        if backend_name == "local":
            self._backend = LocalEmbedder(model_name=model or "all-MiniLM-L6-v2")
        elif backend_name == "lmstudio":
            url = api_url or "http://localhost:1234"
            self._backend = APIEmbedder(
                base_url=url, api_key=api_key or "lm-studio",
                model=model or "loaded-model", dim=dim,
            )
        elif backend_name == "openai":
            self._backend = APIEmbedder(
                base_url=api_url or "https://api.openai.com",
                api_key=api_key or os.getenv("OPENAI_API_KEY", ""),
                model=model or "text-embedding-3-small", dim=dim,
            )
        elif backend_name == "openrouter":
            self._backend = APIEmbedder(
                base_url=api_url, api_key=api_key,
                model=model or "text-embedding-3-small", dim=dim,
            )
        else:
            raise ValueError(f"Unknown EMBEDDING_BACKEND: {backend_name!r}")

        log.info("Embedding backend: %s (model=%s)", backend_name,
                 model or "(default)")

    def encode(self, text: str) -> np.ndarray:
        """Encode a single string into a float32 vector."""
        return self._backend.encode(text)

    def encode_batch(self, texts: list[str]) -> np.ndarray:
        """Encode multiple strings. Returns (N, dim) float32 array."""
        return self._backend.encode_batch(texts)

    @property
    def dim(self) -> int:
        """Embedding dimensionality."""
        return self._backend.dim

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

        Returns list of (index, similarity_score) sorted by score descending.
        """
        if corpus_vecs.size == 0:
            return []

        query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
        corpus_norms = np.linalg.norm(corpus_vecs, axis=1, keepdims=True) + 1e-10
        normed_corpus = corpus_vecs / corpus_norms

        scores = normed_corpus @ query_norm
        k = min(top_k, len(scores))
        top_indices = np.argpartition(scores, -k)[-k:]
        top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]

        return [(int(i), float(scores[i])) for i in top_indices]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[Embedder] = None
_instance_lock = threading.Lock()


def get_embedder() -> Optional[Embedder]:
    """Return the global Embedder singleton.

    Returns None if the configured backend can't be initialized
    (e.g. sentence-transformers not installed for local backend).
    """
    global _instance
    if _instance is not None:
        return _instance

    with _instance_lock:
        if _instance is not None:
            return _instance

        backend = os.getenv("EMBEDDING_BACKEND", "local").lower()

        # For local backend, check dependency
        if backend == "local":
            try:
                import sentence_transformers  # noqa: F401
            except ImportError:
                log.warning(
                    "sentence-transformers not installed — embedding disabled. "
                    "Install it (pip install sentence-transformers) or set "
                    "EMBEDDING_BACKEND=lmstudio/openai/openrouter to use an API."
                )
                return None

        try:
            _instance = Embedder()
        except Exception as e:
            log.error("Failed to initialize embedder: %s", e)
            return None

        return _instance
