"""Text embedders. Every vector is L2-normalised, so a dot product is cosine similarity."""

from typing import Protocol

import numpy as np

EMBEDDERS = {
    "bge-small": "BAAI/bge-small-en-v1.5",  # 384-d, default
    "minilm": "sentence-transformers/all-MiniLM-L6-v2",  # 384-d, FARE's choice
}


class Embedder(Protocol):
    name: str

    def passages(self, texts: list[str]) -> np.ndarray: ...
    def query(self, text: str) -> np.ndarray: ...


def _normalise(x: np.ndarray) -> np.ndarray:
    x = x.astype(np.float32)
    return x / np.maximum(np.linalg.norm(x, axis=-1, keepdims=True), 1e-12)


class FastEmbedder:
    """Local ONNX embeddings (fastembed): no GPU, no API calls, deterministic."""

    def __init__(self, name: str = "bge-small", batch_size: int = 64):
        from fastembed import TextEmbedding

        self.name = name
        self._model = TextEmbedding(EMBEDDERS[name])
        self._batch = batch_size

    def passages(self, texts: list[str]) -> np.ndarray:
        return _normalise(np.stack(list(self._model.passage_embed(texts, batch_size=self._batch))))

    def query(self, text: str) -> np.ndarray:
        return _normalise(next(iter(self._model.query_embed([text]))))
