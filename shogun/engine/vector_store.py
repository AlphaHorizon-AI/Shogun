"""Qdrant vector store — embedding + search for agent memory.

Provides the vector layer for Shogun's memory system:
  - Embeds text via sentence-transformers (BAAI/bge-small-en-v1.5, 384d)
  - Stores/retrieves vectors in Qdrant (embedded mode, zero external deps)
  - Supports filtered search by memory_type, agent_id, importance, etc.

Usage:
    store = get_vector_store()          # singleton
    await store.ensure_collection()     # called on bootstrap
    vec = store.embed("some text")      # synchronous embedding
    store.upsert(memory_id, text, payload)
    results = store.search(query_text, filters, limit)
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    Range,
    VectorParams,
)

from shogun.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "shogun_memories"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384

# ── Singleton ────────────────────────────────────────────────────

_store_instance: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Get or create the singleton VectorStore."""
    global _store_instance
    if _store_instance is None:
        _store_instance = VectorStore()
    return _store_instance


# ── VectorStore ──────────────────────────────────────────────────


class VectorStore:
    """Qdrant-backed vector store with sentence-transformer embeddings."""

    def __init__(self) -> None:
        self._client: QdrantClient | None = None
        self._embedder: Any = None  # lazy-loaded SentenceTransformer

    # ── Client ───────────────────────────────────────────────────

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            if settings.qdrant_url:
                self._client = QdrantClient(url=settings.qdrant_url)
            else:
                self._client = QdrantClient(path=str(settings.qdrant_path))
            logger.info("Qdrant client initialized (path=%s)", settings.qdrant_path)
        return self._client

    # ── Embedder ─────────────────────────────────────────────────

    @property
    def embedder(self):
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading embedding model: %s", EMBEDDING_MODEL)
            self._embedder = SentenceTransformer(EMBEDDING_MODEL)
            logger.info("Embedding model loaded (dim=%d)", EMBEDDING_DIM)
        return self._embedder

    def embed(self, text: str) -> list[float]:
        """Embed a single text string → 384d float vector."""
        # bge models benefit from a query prefix for retrieval
        vector = self.embedder.encode(text, normalize_embeddings=True)
        return vector.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts → list of 384d float vectors."""
        vectors = self.embedder.encode(texts, normalize_embeddings=True, batch_size=32)
        return [v.tolist() for v in vectors]

    # ── Collection management ────────────────────────────────────

    def ensure_collection(self) -> None:
        """Create the memory collection if it doesn't exist."""
        collections = [c.name for c in self.client.get_collections().collections]
        if COLLECTION_NAME not in collections:
            self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=EMBEDDING_DIM,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("Created Qdrant collection '%s' (dim=%d, cosine)", COLLECTION_NAME, EMBEDDING_DIM)
        else:
            logger.info("Qdrant collection '%s' already exists", COLLECTION_NAME)

    def collection_info(self) -> dict[str, Any]:
        """Get collection info (point count, status, etc.)."""
        try:
            info = self.client.get_collection(COLLECTION_NAME)
            return {
                "name": COLLECTION_NAME,
                "points_count": getattr(info, "points_count", 0),
                "status": str(getattr(info, "status", "unknown")),
            }
        except Exception as e:
            # Most common error is the lock error if another process is accessing
            msg = str(e)
            if "already accessed by another instance" in msg:
                return {"name": COLLECTION_NAME, "status": "active (locked)", "points_count": "unknown"}
            return {"name": COLLECTION_NAME, "error": msg}

    # ── Upsert ───────────────────────────────────────────────────

    def upsert(
        self,
        memory_id: str,
        text: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Embed text and upsert into Qdrant with metadata payload."""
        vector = self.embed(text)
        point_payload = payload or {}
        point_payload["memory_id"] = memory_id
        # Truncate content for payload (full content lives in SQLite)
        point_payload["content_preview"] = text[:500]

        self.client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                PointStruct(
                    id=memory_id,
                    vector=vector,
                    payload=point_payload,
                )
            ],
        )

    def upsert_batch(
        self,
        items: list[dict[str, Any]],
    ) -> int:
        """Batch upsert: each item must have 'id', 'text', and optional 'payload'."""
        if not items:
            return 0

        texts = [item["text"] for item in items]
        vectors = self.embed_batch(texts)

        points = []
        for item, vector in zip(items, vectors):
            payload = item.get("payload", {})
            payload["memory_id"] = item["id"]
            payload["content_preview"] = item["text"][:500]
            points.append(
                PointStruct(id=item["id"], vector=vector, payload=payload)
            )

        self.client.upsert(collection_name=COLLECTION_NAME, points=points)
        return len(points)

    # ── Search ───────────────────────────────────────────────────

    def search(
        self,
        query_text: str,
        *,
        memory_types: list[str] | None = None,
        agent_id: str | None = None,
        min_importance: float | None = None,
        pinned_only: bool = False,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Semantic search with optional payload filters.

        Returns list of dicts with: memory_id, score, payload.
        """
        query_vector = self.embed(query_text)

        # Build Qdrant filter conditions
        conditions = []
        if memory_types:
            for mt in memory_types:
                conditions.append(
                    FieldCondition(key="memory_type", match=MatchValue(value=mt))
                )
        if agent_id:
            conditions.append(
                FieldCondition(key="agent_id", match=MatchValue(value=agent_id))
            )
        if min_importance is not None:
            conditions.append(
                FieldCondition(key="importance_score", range=Range(gte=min_importance))
            )
        if pinned_only:
            conditions.append(
                FieldCondition(key="is_pinned", match=MatchValue(value=True))
            )

        qdrant_filter = Filter(should=conditions) if memory_types and len(memory_types) > 1 else (
            Filter(must=conditions) if conditions else None
        )

        # Use the newer query_points API
        response = self.client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            query_filter=qdrant_filter,
            limit=limit,
            with_payload=True,
            score_threshold=0.15,  # filter out very low similarity
        )

        return [
            {
                "memory_id": str(hit.id),
                "score": hit.score,
                "payload": hit.payload or {},
            }
            for hit in response.points
        ]

    # ── Delete ───────────────────────────────────────────────────

    def delete_point(self, memory_id: str) -> None:
        """Remove a vector point by memory ID."""
        try:
            self.client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=[memory_id],
            )
        except Exception as e:
            logger.warning("Failed to delete point %s from Qdrant: %s", memory_id, e)

    # ── Reindex ──────────────────────────────────────────────────

    def drop_and_recreate(self) -> None:
        """Drop the collection and recreate it (for full reindex)."""
        try:
            self.client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
        self.ensure_collection()
