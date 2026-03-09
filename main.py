"""
Codebase AI Assistant - Main Entry Point
Can be used as CLI to trigger ingestion or just run the API server.
"""

import argparse
import sys
from loguru import logger

from utils.config import settings
from indexing.indexer import Indexer


def setup_logger():
    logger.remove()
    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <cyan>{name}</cyan> - <level>{message}</level>"
    )


def ingest_repo(repo_path: str, repo_name: str):
    """Trigger full ingestion pipeline for a local repo path."""
    logger.info(f"Starting ingestion for repo: {repo_name} at path: {repo_path}")
    indexer = Indexer()
    result = indexer.index_repository(repo_path=repo_path, repo_name=repo_name)
    logger.info(f"Ingestion complete. Chunks indexed: {result['chunks_indexed']}")
    return result


def main():
    setup_logger()

    parser = argparse.ArgumentParser(
        description="Codebase AI Assistant - Index a repo or start the API server"
    )
    subparsers = parser.add_subparsers(dest="command")

    # Sub-command: ingest
    ingest_parser = subparsers.add_parser("ingest", help="Ingest a local repository")
    ingest_parser.add_argument("--path", required=True, help="Absolute or relative path to the repo")
    ingest_parser.add_argument("--name", required=True, help="A unique name for this repo (used as namespace)")

    # Sub-command: serve (just a hint — actual serving is done via uvicorn in docker)
    subparsers.add_parser("serve", help="Start the FastAPI server (use uvicorn directly or docker-compose)")

    args = parser.parse_args()

    if args.command == "ingest":
        ingest_repo(repo_path=args.path, repo_name=args.name)

    elif args.command == "serve":
        logger.info("To start the server run: uvicorn api.server:app --reload")
        logger.info("Or simply use: docker-compose up")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()