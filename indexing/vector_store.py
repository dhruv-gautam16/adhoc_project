"""
vector_store.py
Wraps ChromaDB to handle storing chunks + embeddings and querying them.
"""

import uuid
from typing import List, Dict, Optional
import chromadb
from loguru import logger

from utils.config import settings


class VectorStore:
    def __init__(self, repo_name: str):
        self.repo_name = repo_name
        self.collection_name = self._sanitize_collection_name(
            f"{settings.CHROMA_COLLECTION_NAME}_{repo_name}"
        )

        # Use HttpClient without Settings object (compatible with 0.4.x)
        self.client = chromadb.HttpClient(
            host=settings.CHROMA_HOST,
            port=settings.CHROMA_PORT,
        )

        # Ensure default tenant/database exist
        try:
            self.client.heartbeat()
        except Exception as e:
            raise RuntimeError(f"Cannot connect to ChromaDB at {settings.CHROMA_HOST}:{settings.CHROMA_PORT} — {e}")

        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        logger.info(f"VectorStore ready | Collection: {self.collection_name}")

    @staticmethod
    def _sanitize_collection_name(name: str) -> str:
        """ChromaDB collection names: alphanumeric + underscores, 3-63 chars."""
        sanitized = "".join(c if c.isalnum() or c == "_" else "_" for c in name)
        # Must start with alphanumeric
        if sanitized and not sanitized[0].isalnum():
            sanitized = "c" + sanitized
        return sanitized[:63]

    def add_chunks(self, chunks: List[Dict], embeddings: List[List[float]]) -> int:
        if not chunks or not embeddings:
            return 0

        valid = [
            (chunk, emb)
            for chunk, emb in zip(chunks, embeddings)
            if emb is not None
        ]

        if not valid:
            logger.warning("No valid embeddings to store.")
            return 0

        valid_chunks, valid_embeddings = zip(*valid)

        ids = [str(uuid.uuid4()) for _ in valid_chunks]
        documents = [c["chunk_text"] for c in valid_chunks]
        metadatas = []

        for c in valid_chunks:
            meta = {
                k: str(v) if not isinstance(v, (str, int, float, bool)) else v
                for k, v in c["metadata"].items()
            }
            meta["repo_name"] = self.repo_name
            metadatas.append(meta)

        BATCH = 500
        stored = 0
        for i in range(0, len(ids), BATCH):
            self.collection.upsert(
                ids=ids[i: i + BATCH],
                embeddings=list(valid_embeddings)[i: i + BATCH],
                documents=documents[i: i + BATCH],
                metadatas=metadatas[i: i + BATCH],
            )
            stored += len(ids[i: i + BATCH])

        logger.info(f"Stored {stored} chunks in ChromaDB | Collection: {self.collection_name}")
        return stored

    def query(self, query_embedding: List[float], top_k: int = 5, filter_metadata: Optional[Dict] = None) -> List[Dict]:
        query_params = {
            "query_embeddings": [query_embedding],
            "n_results": min(top_k, self.collection.count() or 1),
            "include": ["documents", "metadatas", "distances"],
        }

        if filter_metadata:
            query_params["where"] = filter_metadata

        results = self.collection.query(**query_params)

        output = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            output.append({
                "text": doc,
                "metadata": meta,
                "distance": round(dist, 4),
                "similarity": round(1 - dist, 4),
            })

        return output

    def get_collection_info(self) -> Dict:
        count = self.collection.count()
        return {
            "collection_name": self.collection_name,
            "repo_name": self.repo_name,
            "total_chunks": count,
        }

    def delete_collection(self):
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"Collection deleted and recreated: {self.collection_name}")