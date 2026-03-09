"""
indexer.py
Orchestrates the full pipeline:
  repo_loader → file_parser → git_history → embedder → vector_store

This is the single entry point called by main.py and the API
whenever a repository needs to be indexed or re-indexed.
"""

from typing import Dict
from loguru import logger

from ingestion.repo_loader import load_repository
from ingestion.file_parser import parse_files
from ingestion.git_history import load_git_history, format_commits_as_chunks
from indexing.embedder import Embedder
from indexing.vector_store import VectorStore


class Indexer:
    def __init__(self):
        self.embedder = Embedder()

    def index_repository(
        self,
        repo_path: str,
        repo_name: str,
        reindex: bool = False,
        include_git_history: bool = True,
    ) -> Dict:
        """
        Full pipeline: load → parse → embed → store.

        Args:
            repo_path: Local path to the repository
            repo_name: Unique name/identifier for this repo
            reindex: If True, wipe existing collection before indexing
            include_git_history: Whether to also index git commit history

        Returns:
            Summary dict with stats about the indexing run
        """
        logger.info(f"=== Starting indexing for repo: {repo_name} ===")

        vector_store = VectorStore(repo_name=repo_name)

        if reindex:
            logger.info("Reindex flag set — wiping existing collection...")
            vector_store.delete_collection()

        # ── Step 1: Load all source files ──────────────────────────────────
        logger.info("Step 1/4: Loading repository files...")
        files = load_repository(repo_path)

        if not files:
            logger.warning("No files found in repository. Aborting.")
            return {"status": "no_files", "chunks_indexed": 0}

        # ── Step 2: Parse files into chunks ────────────────────────────────
        logger.info("Step 2/4: Parsing files into chunks...")
        file_chunks = parse_files(files)

        # ── Step 3: Load git history (optional) ────────────────────────────
        git_chunks = []
        if include_git_history:
            logger.info("Step 3/4: Extracting git history...")
            commits = load_git_history(repo_path)
            git_chunks = format_commits_as_chunks(commits, repo_name)
        else:
            logger.info("Step 3/4: Skipping git history (disabled).")

        all_chunks = file_chunks + git_chunks
        logger.info(f"Total chunks to embed: {len(all_chunks)} "
                    f"({len(file_chunks)} code + {len(git_chunks)} git)")

        if not all_chunks:
            logger.warning("No chunks to index. Aborting.")
            return {"status": "no_chunks", "chunks_indexed": 0}

        # ── Step 4: Embed and store ─────────────────────────────────────────
        logger.info("Step 4/4: Generating embeddings and storing in ChromaDB...")
        texts = [c["chunk_text"] for c in all_chunks]
        embeddings = self.embedder.embed_texts(texts)

        stored_count = vector_store.add_chunks(all_chunks, embeddings)

        collection_info = vector_store.get_collection_info()

        summary = {
            "status": "success",
            "repo_name": repo_name,
            "repo_path": repo_path,
            "files_loaded": len(files),
            "file_chunks": len(file_chunks),
            "git_chunks": len(git_chunks),
            "chunks_indexed": stored_count,
            "total_in_collection": collection_info["total_chunks"],
        }

        logger.info(f"=== Indexing complete ===")
        logger.info(f"  Files loaded    : {summary['files_loaded']}")
        logger.info(f"  File chunks     : {summary['file_chunks']}")
        logger.info(f"  Git chunks      : {summary['git_chunks']}")
        logger.info(f"  Chunks stored   : {summary['chunks_indexed']}")
        logger.info(f"  Total in DB     : {summary['total_in_collection']}")

        return summary