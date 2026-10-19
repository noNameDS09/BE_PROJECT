"""Text embedders. Every vector is L2-normalised, so a dot product is cosine similarity.

FastEmbedder (ONNX, CPU) is the default and is always used for queries. TorchEmbedder runs
the same model weights on a GPU (CUDA or Apple MPS) to build the passage index much faster;
`loupe index check` confirms both produce the same vectors (cosine >= 0.99).
"""

import os
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

    def __init__(self, name: str = "bge-small", batch_size: int = 64, threads: int | None = None):
        from fastembed import TextEmbedding

        self.name = name
        # ONNX Runtime's default thread count is ~3x slower than using every core on an M1
        self._model = TextEmbedding(EMBEDDERS[name], threads=threads or os.cpu_count())
        self._batch = batch_size

    def passages(self, texts: list[str]) -> np.ndarray:
        return _normalise(np.stack(list(self._model.passage_embed(texts, batch_size=self._batch))))

    def query(self, text: str) -> np.ndarray:
        return _normalise(next(iter(self._model.query_embed([text]))))


class TorchEmbedder:
    """Same model on a GPU via sentence-transformers (optional extra: `uv sync --extra gpu`)."""

    def __init__(self, name: str = "bge-small", device: str = "cuda", batch_size: int = 128):
        import torch
        from sentence_transformers import SentenceTransformer

        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA is not available: install a CUDA build of torch (docs/GPU-INDEX-BUILD.md)"
            )
        self.name = name
        self.device = device
        self._model = SentenceTransformer(EMBEDDERS[name], device=device)
        self._model.max_seq_length = 512
        self._batch = batch_size

    def passages(self, texts: list[str]) -> np.ndarray:
        vecs = self._model.encode(
            texts, batch_size=self._batch, normalize_embeddings=True, convert_to_numpy=True
        )
        return _normalise(vecs)

    def query(self, text: str) -> np.ndarray:
        return self.passages([text])[0]


def make_embedder(name: str = "bge-small", device: str = "cpu") -> Embedder:
    """device: cpu (ONNX) | cuda | mps."""
    return FastEmbedder(name) if device == "cpu" else TorchEmbedder(name, device)


def agreement(stored: np.ndarray, recomputed: np.ndarray) -> np.ndarray:
    """Row-wise cosine between stored vectors and freshly computed ones (both normalised)."""
    return np.sum(_normalise(stored) * _normalise(recomputed), axis=1)
