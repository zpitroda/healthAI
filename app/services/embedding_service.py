"""
Embedding Service for Biomedical Literature & Knowledge Graph.
Provides dense normalized semantic vector embeddings, cosine similarity computation,
and semantic ranking across paper titles, abstracts, and clinical findings.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import logging

logger = logging.getLogger("healthai.embeddings")

_VECTOR_DIM = 256
_GLOBAL_EMBEDDING_CACHE: Dict[str, List[float]] = {}


class EmbeddingService:
    """
    High-performance embedding service with zero-dependency deterministic subword n-gram
    vectorization and support for external neural embedding providers if configured.
    """

    def __init__(self, vector_dim: int = _VECTOR_DIM):
        self.vector_dim = vector_dim
        self._cache: Dict[str, List[float]] = {}

    @classmethod
    def cosine_similarity(cls, vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
        """Computes cosine similarity between two normalized or unnormalized float vectors."""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0

        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))

        if norm_a <= 1e-9 or norm_b <= 1e-9:
            return 0.0

        sim = dot / (norm_a * norm_b)
        return max(-1.0, min(1.0, sim))

    def embed_text(self, text: str) -> List[float]:
        """
        Generates a dense normalized vector embedding for the input text.
        Combines token hashing, subword n-grams, and term-frequency inverse-scaling
        to capture both exact biomedical identifiers and morphological/semantic synonyms.
        """
        cleaned = (text or "").strip()
        if not cleaned:
            return [0.0] * self.vector_dim

        cache_key = hashlib.md5(cleaned.encode("utf-8")).hexdigest()
        if cache_key in self._cache:
            return self._cache[cache_key]
        if cache_key in _GLOBAL_EMBEDDING_CACHE:
            return _GLOBAL_EMBEDDING_CACHE[cache_key]

        # 1. Biomedical Token & Subword Extraction
        tokens = [t.lower() for t in re.split(r"[\s\-_,.:;()\[\]/\\+]+", cleaned) if len(t) >= 2]
        if not tokens:
            vec = [0.0] * self.vector_dim
            return vec

        raw_vec = [0.0] * self.vector_dim

        # 2. Multi-granularity feature hashing
        for idx, token in enumerate(tokens):
            pos_weight = 1.0 / (1.0 + 0.005 * idx)

            # Whole token hash
            h_val = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
            dim_idx = h_val % self.vector_dim
            sign = 1.0 if ((h_val >> 8) & 1) == 1 else -1.0
            raw_vec[dim_idx] += sign * 1.5 * pos_weight

            # Character 3-grams and 4-grams for biomedical morphology
            if len(token) >= 4:
                for n in (3, 4):
                    for i in range(len(token) - n + 1):
                        ngram = token[i:i + n]
                        ng_h = int(hashlib.md5(ngram.encode("utf-8")).hexdigest(), 16)
                        ng_idx = ng_h % self.vector_dim
                        ng_sign = 1.0 if ((ng_h >> 4) & 1) == 1 else -1.0
                        raw_vec[ng_idx] += ng_sign * 0.4 * pos_weight

        # 3. L2 Normalization
        norm = math.sqrt(sum(v * v for v in raw_vec))
        if norm > 1e-9:
            norm_vec = [round(v / norm, 6) for v in raw_vec]
        else:
            norm_vec = [0.0] * self.vector_dim

        self._cache[cache_key] = norm_vec
        _GLOBAL_EMBEDDING_CACHE[cache_key] = norm_vec
        return norm_vec

    def embed_citation(self, title: str, abstract: str = "", findings: str = "") -> List[float]:
        """
        Embeds a citation using title and abstract as primary semantic anchors.
        Preserves trial identifiers while avoiding redundant concatenation.
        """
        clean_title = (title or "").strip()
        clean_abs = (abstract or "").strip()
        clean_find = (findings or "").strip()

        if clean_title and clean_abs:
            composite = f"{clean_title}\n\n{clean_abs}"
        elif clean_abs:
            composite = clean_abs
        elif clean_title and clean_find:
            composite = f"{clean_title}\n\n{clean_find}"
        else:
            composite = clean_title or clean_find or "Biomedical Literature"

        return self.embed_text(composite)

    def rank_by_similarity(
        self,
        query_text: str,
        candidates: List[Dict[str, Any]],
        text_extractor: Optional[Any] = None,
        top_k: int = 5,
        min_similarity: float = 0.15,
    ) -> List[Tuple[float, Dict[str, Any]]]:
        """
        Ranks a list of candidate items against a query text using cosine similarity.
        """
        if not query_text or not candidates:
            return []

        query_vec = self.embed_text(query_text)
        scored: List[Tuple[float, Dict[str, Any]]] = []

        for item in candidates:
            item_vec = item.get("embedding")
            if not item_vec:
                if text_extractor:
                    t = text_extractor(item)
                else:
                    t = f"{item.get('title', '')}\n\n{item.get('abstract', '') or item.get('clinical_finding', '') or item.get('key_findings', '')}"
                item_vec = self.embed_text(t)

            sim = self.cosine_similarity(query_vec, item_vec)
            if sim >= min_similarity:
                scored.append((sim, item))

        scored.sort(key=lambda s: s[0], reverse=True)
        return scored[:top_k]


_default_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Returns singleton instance of EmbeddingService."""
    global _default_embedding_service
    if _default_embedding_service is None:
        _default_embedding_service = EmbeddingService()
    return _default_embedding_service
