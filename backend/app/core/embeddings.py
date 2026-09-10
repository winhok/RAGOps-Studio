from __future__ import annotations
import hashlib
import math
from abc import ABC, abstractmethod
from .text import tokenize

class EmbeddingProvider(ABC):

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        raise NotImplementedError

class HashEmbeddingProvider(EmbeddingProvider):
    """Signed feature hashing for repeatable local execution; not a learned embedding model."""

    def __init__(self, dimensions: int=384) -> None:
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = tokenize(text)
        for token in tokens:
            digest = hashlib.blake2b(token.encode('utf-8'), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], 'big') % self.dimensions
            sign = -1.0 if digest[4] & 1 else 1.0
            vector[bucket] += sign
        norm = math.sqrt(sum((v * v for v in vector)))
        if norm:
            vector = [v / norm for v in vector]
        return vector
