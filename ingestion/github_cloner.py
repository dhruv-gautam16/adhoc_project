"""
github_cloner.py
Clones a GitHub repository to the local repos/ directory
so it can be ingested by the indexer.
"""

import re
import shutil
from pathlib import Path
from typing import Tuple

from git import Repo, GitCommandError
from loguru import logger

from utils.config import settings


def parse_github_url(github_url: str) -> Tuple[str, str]:
    url = github_url.strip().rstrip("/")
    if not url.startswith("http"):
        url = "https://" + url

    pattern = r"https://github\.com/([^/]+)/([^/]+?)(?:\.git)?$"
    match = re.match(pattern, url)

    if not match:
        raise ValueError(f"Invalid GitHub URL: {github_url}. Expected format: https://github.com/owner/repo")

    owner = match.group(1)
    repo = match.group(2)
    repo_name = f"{owner}__{repo}"
    clean_url = f"https://github.com/{owner}/{repo}.git"

    return repo_name, clean_url


def clone_repository(github_url: str, force_reclone: bool = False) -> Tuple[str, str]:
    repo_name, clean_url = parse_github_url(github_url)
    repos_dir = Path(settings.REPOS_DIR)
    repos_dir.mkdir(parents=True, exist_ok=True)

    local_path = repos_dir / repo_name

    if local_path.exists():
        if force_reclone:
            logger.info(f"Force reclone: deleting existing clone at {local_path}")
            shutil.rmtree(local_path)
        else:
            logger.info(f"Repo already cloned at {local_path}. Pulling latest changes...")
            try:
                existing_repo = Repo(local_path)
                existing_repo.remotes.origin.pull()
                logger.info("Pull complete.")
            except Exception as e:
                logger.warning(f"Pull failed ({e}), using existing clone as-is.")
            return repo_name, str(local_path)

    logger.info(f"Cloning {clean_url} → {local_path}")
    try:
        Repo.clone_from(clean_url, local_path, depth=50)
        logger.info(f"Clone complete: {local_path}")
    except GitCommandError as e:
        raise RuntimeError(f"Git clone failed: {str(e)}")

    return repo_name, str(local_path)