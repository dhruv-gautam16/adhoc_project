"""
embedder.py
Generates vector embeddings for text chunks using OpenAI's embedding API.
Handles batching and retries gracefully.
"""

import time
from typing import List
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log
from loguru import logger
import logging

from utils.config import settings


# OpenAI allows up to 2048 inputs per batch but we keep it conservative
BATCH_SIZE = 100


class Embedder:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_EMBEDDING_MODEL
        logger.info(f"Embedder initialized with model: {self.model}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Send a single batch of texts to OpenAI and return embeddings."""
        response = self.client.embeddings.create(
            model=self.model,
            input=texts,
        )
        # Sort by index to ensure order is preserved
        sorted_data = sorted(response.data, key=lambda x: x.index)
        return [item.embedding for item in sorted_data]

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a list of texts in batches.

        Returns:
            List of embedding vectors (same order as input texts)
        """
        if not texts:
            return []

        all_embeddings = []
        total_batches = (len(texts) + BATCH_SIZE - 1) // BATCH_SIZE

        logger.info(f"Embedding {len(texts)} chunks in {total_batches} batch(es)...")

        for batch_num, i in enumerate(range(0, len(texts), BATCH_SIZE), start=1):
            batch = texts[i: i + BATCH_SIZE]
            logger.debug(f"Processing batch {batch_num}/{total_batches} ({len(batch)} texts)")

            try:
                embeddings = self._embed_batch(batch)
                all_embeddings.extend(embeddings)
            except Exception as e:
                logger.error(f"Failed to embed batch {batch_num}: {e}")
                # Fill with None so indexes stay aligned — vector_store will skip these
                all_embeddings.extend([None] * len(batch))

            # Small sleep between batches to be kind to rate limits
            if batch_num < total_batches:
                time.sleep(0.3)

        logger.info(f"Embedding complete. Got {len(all_embeddings)} vectors.")
        return all_embeddings

    def embed_single(self, text: str) -> List[float]:
        """Embed a single query string — used at retrieval time."""
        results = self.embed_texts([text])
        if not results or results[0] is None:
            raise ValueError("Failed to embed query text.")
        return results[0]