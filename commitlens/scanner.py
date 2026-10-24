"""
scanner.py - Reads a local Git repository and extracts commit information.

This module provides the scan_repo() function which takes a path to a local
Git repository and returns a list of commits with their hash, author, date,
and message.
"""

import os

from git import Repo
from git.exc import InvalidGitRepositoryError, NoSuchPathError


def scan_repo(path):
    """
    Scan a local Git repository and extract commit history.

    Args:
        path (str): Absolute path to a local Git repository folder.

    Returns:
        list[dict]: A list of dictionaries, each containing:
            - hash    (str): The full commit hash (40-character hex string).
            - author  (str): The name of the person who wrote the commit.
            - date    (str): The commit timestamp in ISO 8601 format.
            - message (str): The commit message text.

    Raises:
        FileNotFoundError: If the path does not exist on disk.
        ValueError: If the path exists but is not a valid Git repository.
    """
    # --- Step 1: Validate the path and open the repository ---

    # Check if the path exists on disk. We do this first so the user gets
    # a clear message instead of GitPython's internal error.
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"The path '{path}' does not exist. "
            f"Please provide the full path to a Git repository folder."
        )

    # Try to open it as a Git repo. A valid Git repo has a hidden .git folder.
    try:
        repo = Repo(path)
    except InvalidGitRepositoryError:
        raise ValueError(
            f"The folder '{path}' is not a Git repository. "
            f"A Git repository must contain a '.git' folder. "
            f"Did you run 'git init' in this folder?"
        )

    # --- Step 2: Extract commits ---

    commits = []

    # A freshly initialised repo (git init, but no commits yet) has no HEAD,
    # so iter_commits() would raise a ValueError. We catch that and simply
    # return an empty list — this is normal, not an error.
    try:
        # iter_commits() walks through every commit starting from HEAD
        # (newest commit first, oldest commit last).
        for commit in repo.iter_commits():
            commits.append({
                "hash": commit.hexsha,
                "author": str(commit.author),
                "date": commit.committed_datetime.isoformat(),
                "message": commit.message.strip(),
            })
    except ValueError:
        # No commits exist yet (HEAD is invalid) — perfectly normal.
        pass

    return commits
