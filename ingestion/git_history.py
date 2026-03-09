"""
git_history.py
Extracts commit history and per-file change summaries from a git repository
using GitPython. This enriches the knowledge base with the "why" behind code changes.
"""

from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from git import Repo, InvalidGitRepositoryError, GitCommandError
from loguru import logger


# Max commits to process (keep it reasonable for hackathon/prototype)
MAX_COMMITS = 200

# Max diff length per commit to avoid bloating the index
MAX_DIFF_LENGTH = 1500


def load_git_history(repo_path: str, max_commits: int = MAX_COMMITS) -> List[Dict]:
    """
    Walk through the git log of a repository and extract commit information.

    Returns:
        List of commit dicts with: hash, author, date, message, files_changed, diff_summary
    """
    repo_path = Path(repo_path).resolve()

    try:
        repo = Repo(repo_path)
    except InvalidGitRepositoryError:
        logger.warning(f"Not a git repository: {repo_path}. Skipping git history.")
        return []

    if repo.bare:
        logger.warning("Repository is bare. Skipping git history.")
        return []

    logger.info(f"Extracting git history (up to {max_commits} commits)...")

    commits_data = []

    try:
        commits = list(repo.iter_commits("HEAD", max_count=max_commits))
    except GitCommandError as e:
        logger.warning(f"Could not read commits: {e}")
        return []

    for commit in commits:
        try:
            # Get list of changed files
            files_changed = []
            diff_summary = ""

            if commit.parents:
                parent = commit.parents[0]
                diffs = parent.diff(commit)

                for diff in diffs:
                    if diff.a_path:
                        files_changed.append(diff.a_path)
                    elif diff.b_path:
                        files_changed.append(diff.b_path)

                # Build a short diff summary from the first few diffs
                diff_texts = []
                for diff in diffs[:5]:  # Limit to first 5 file diffs
                    try:
                        if diff.diff:
                            diff_text = diff.diff.decode("utf-8", errors="ignore")
                            diff_texts.append(f"--- {diff.a_path or diff.b_path} ---\n{diff_text[:300]}")
                    except Exception:
                        continue

                diff_summary = "\n".join(diff_texts)[:MAX_DIFF_LENGTH]

            commit_data = {
                "hash": commit.hexsha[:10],
                "author": str(commit.author),
                "date": datetime.fromtimestamp(commit.authored_date).isoformat(),
                "message": commit.message.strip(),
                "files_changed": files_changed[:20],  # Cap file list
                "diff_summary": diff_summary,
            }
            commits_data.append(commit_data)

        except Exception as e:
            logger.debug(f"Skipping commit {commit.hexsha[:8]}: {e}")
            continue

    logger.info(f"Extracted {len(commits_data)} commits from git history")
    return commits_data


def format_commits_as_chunks(commits: List[Dict], repo_name: str) -> List[Dict]:
    """
    Convert raw commit data into chunk dicts suitable for embedding,
    same format as file_parser output so the indexer can handle both uniformly.
    """
    chunks = []

    for commit in commits:
        # Build a readable text block for this commit
        files_list = ", ".join(commit["files_changed"][:10]) or "N/A"

        chunk_text = (
            f"Commit: {commit['hash']}\n"
            f"Author: {commit['author']}\n"
            f"Date: {commit['date']}\n"
            f"Message: {commit['message']}\n"
            f"Files Changed: {files_list}\n"
        )

        if commit["diff_summary"]:
            chunk_text += f"\nDiff Summary:\n{commit['diff_summary']}"

        chunks.append({
            "chunk_text": chunk_text,
            "metadata": {
                "relative_path": f"git_history/{commit['hash']}",
                "extension": ".git",
                "chunk_index": 0,
                "total_chunks": 1,
                "commit_hash": commit["hash"],
                "author": commit["author"],
                "date": commit["date"],
                "source_type": "git_commit",
            }
        })

    logger.info(f"Formatted {len(chunks)} git commit chunks for indexing")
    return chunks