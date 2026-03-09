"""
retriever.py
Takes a natural language query, embeds it, and retrieves the
most relevant code chunks from ChromaDB.
"""

from typing import List, Dict, Optional
from loguru import logger

from indexing.embedder import Embedder
from indexing.vector_store import VectorStore


class Retriever:
    def __init__(self, repo_name: str):
        self.repo_name = repo_name
        self.embedder = Embedder()
        self.vector_store = VectorStore(repo_name=repo_name)
        logger.info(f"Retriever initialized for repo: {repo_name}")

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        source_type: Optional[str] = None,
    ) -> List[Dict]:
        """
        Retrieve the most relevant chunks for a given query.

        Args:
            query: The developer's natural language question
            top_k: Number of chunks to retrieve
            source_type: Optional filter — 'git_commit' to only search history,
                         or None to search everything

        Returns:
            List of retrieved chunks with text, metadata, and similarity score
        """
        if not query.strip():
            raise ValueError("Query cannot be empty.")

        logger.info(f"Retrieving top {top_k} chunks for query: '{query[:80]}...'")

        # Embed the query
        query_embedding = self.embedder.embed_single(query)

        # Optional metadata filter
        filter_metadata = None
        if source_type:
            filter_metadata = {"source_type": {"$eq": source_type}}

        # Query ChromaDB
        results = self.vector_store.query(
            query_embedding=query_embedding,
            top_k=top_k,
            filter_metadata=filter_metadata,
        )

        logger.info(f"Retrieved {len(results)} chunks (top similarity: "
                    f"{results[0]['similarity'] if results else 'N/A'})")

        return results

    def format_context(self, results: List[Dict]) -> str:
        """
        Format retrieved chunks into a readable context string
        to be injected into the LLM prompt.
        """
        if not results:
            return "No relevant code context found."

        context_parts = []
        for i, result in enumerate(results, start=1):
            meta = result["metadata"]
            file_path = meta.get("relative_path", "unknown")
            similarity = result.get("similarity", 0)

            header = f"[{i}] File: {file_path} (similarity: {similarity:.2f})"
            context_parts.append(f"{header}\n{result['text']}")

        return "\n\n---\n\n".join(context_parts)