"""Local CPU embeddings via fastembed (ONNX build of all-MiniLM-L6-v2, no torch needed)."""

from __future__ import annotations

import logging

import numpy as np

log = logging.getLogger(__name__)


class FastEmbedEmbedder:
    """Implements interfaces.ml.Embedder. The model (~90 MB) is downloaded once and cached."""

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        cache_dir: str | None = None,
        batch_size: int = 64,
    ):
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.batch_size = batch_size
        self._model = None

    def _load(self):
        if self._model is None:
            from fastembed import TextEmbedding

            log.info("loading embedding model %s", self.model_name)
            self._model = TextEmbedding(model_name=self.model_name, cache_dir=self.cache_dir)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = np.asarray(list(self._load().embed(texts, batch_size=self.batch_size)), dtype=np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return (vectors / norms).tolist()
