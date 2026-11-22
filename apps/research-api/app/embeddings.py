from __future__ import annotations

import hashlib
from typing import Iterable, Protocol

import numpy as np

from .chunking import tokenize


class Embedder(Protocol):
    name: str
    dim: int

    def embed_documents(self, texts: Iterable[str]) -> list[np.ndarray]: ...

    def embed_query(self, text: str) -> np.ndarray: ...


class HashingEmbedder:
    """Deterministic bag-of-tokens hashing embedding.

    This is a PLACEHOLDER, not a semantic model: it captures lexical overlap
    only. Real semantic embeddings come from `knowledge_vector` once the user
    plugs that project in (see retrieval.KnowledgeVectorBackend). Keeping it
    deterministic means the index is reproducible offline and tests are stable.
    """

    def __init__(self, dim: int = 384) -> None:
        self.dim = int(dim)
        self.name = f"hashing-v1-{self.dim}"

    def _embed(self, text: str) -> np.ndarray:
        vector = np.zeros(self.dim, dtype=np.float32)
        for token in tokenize(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "little") % self.dim
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign
        norm = float(np.linalg.norm(vector))
        if norm > 0:
            vector /= norm
        return vector

    def embed_documents(self, texts: Iterable[str]) -> list[np.ndarray]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> np.ndarray:
        return self._embed(text)


def vectors_to_blobs(vectors: Iterable[np.ndarray]) -> list[bytes]:
    return [
        np.ascontiguousarray(vector, dtype=np.float32).tobytes() for vector in vectors
    ]


def stack_matrix(vectors: Iterable[np.ndarray]) -> np.ndarray:
    rows = list(vectors)
    if not rows:
        return np.zeros((0, 0), dtype=np.float32)
    return np.vstack(rows).astype(np.float32)
