"""
repo_loader.py
Responsible for scanning a local repository directory and returning
a list of all valid, readable source code files.
"""

import os
from pathlib import Path
from typing import List, Dict
from loguru import logger

from utils.config import settings


# File extensions we care about
SUPPORTED_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".java", ".go", ".rb", ".rs", ".cpp",
    ".c", ".h", ".cs", ".php", ".swift",
    ".kt", ".scala", ".r", ".sh", ".yaml",
    ".yml", ".json", ".toml", ".md", ".txt",
    ".html", ".css", ".sql",
}

# Folders to always skip
IGNORED_DIRS = {
    ".git", ".github", "node_modules", "__pycache__",
    ".venv", "venv", "env", "dist", "build",
    ".idea", ".vscode", "coverage", ".pytest_cache",
    "migrations", "static", "assets",
}


def load_repository(repo_path: str) -> List[Dict]:
    """
    Walk through the repo directory and load all supported source files.

    Returns:
        List of dicts with keys: file_path, relative_path, extension, content
    """
    repo_path = Path(repo_path).resolve()

    if not repo_path.exists():
        raise FileNotFoundError(f"Repository path does not exist: {repo_path}")

    if not repo_path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {repo_path}")

    logger.info(f"Scanning repository at: {repo_path}")

    files = []
    skipped = 0

    for root, dirs, filenames in os.walk(repo_path):
        # Prune ignored directories in-place (prevents os.walk from descending into them)
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

        for filename in filenames:
            file_path = Path(root) / filename
            extension = file_path.suffix.lower()

            # Skip unsupported file types
            if extension not in SUPPORTED_EXTENSIONS:
                skipped += 1
                continue

            # Skip files that are too large
            try:
                file_size_kb = file_path.stat().st_size / 1024
                if file_size_kb > settings.MAX_FILE_SIZE_KB:
                    logger.debug(f"Skipping large file ({file_size_kb:.1f} KB): {file_path.name}")
                    skipped += 1
                    continue
            except OSError:
                skipped += 1
                continue

            # Read file content
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                if not content.strip():
                    skipped += 1
                    continue

                relative_path = str(file_path.relative_to(repo_path))

                files.append({
                    "file_path": str(file_path),
                    "relative_path": relative_path,
                    "extension": extension,
                    "content": content,
                    "size_kb": round(file_size_kb, 2),
                })

            except Exception as e:
                logger.warning(f"Could not read file {file_path}: {e}")
                skipped += 1

    logger.info(f"Loaded {len(files)} files | Skipped {skipped} files")
    return files