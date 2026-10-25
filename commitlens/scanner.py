"""
scanner.py - Reads a local Git repository and extracts commit information.

This module provides the scan_repo() function which takes a path to a local
Git repository and returns a list of commits with their hash, author, date,
and message.
"""

import os
import subprocess
from datetime import datetime


def _run_git_command(args, cwd):
    """Run a git command and return its stdout as text.
    Raises a RuntimeError if the command fails.
    """
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"Git command failed: {' '.join(args)}\n{result.stderr}")
    return (result.stdout or "").strip()


def _is_git_repository(path: str) -> bool:
    """Return True if the given path is a Git repository (has a .git folder)."""
    if not os.path.isdir(path):
        return False
    git_dir = os.path.join(path, ".git")
    if os.path.exists(git_dir):
        return True
    if (
        os.path.exists(os.path.join(path, "HEAD"))
        and os.path.exists(os.path.join(path, "objects"))
        and os.path.exists(os.path.join(path, "refs"))
    ):
        return True
    return False


def scan_repo(path: str):
    """Scan a local Git repository and extract commit history.

    Args:
        path: Absolute path to a local Git repository folder.

    Returns:
        List of commit dictionaries with keys ``hash``, ``author``, ``date``
        (ISO‑8601 string, timezone‑naïve), and ``message``.

    Raises:
        FileNotFoundError: If *path* does not exist.
        ValueError: If *path* is not a Git repository.
    """
    # Validate path existence
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"The path '{path}' does not exist. Please provide a valid repository path."
        )

    # Validate that the directory is a git repository
    if not _is_git_repository(path):
        raise ValueError(
            f"The folder '{path}' is not a Git repository. Did you run 'git init' there?"
        )

    # Use git log to retrieve commit information in a parsable format.
    # %H = commit hash, %an = author name, %ad = author date (iso), %s = subject
    # Separate fields with a ASCII Record Separator (\x1f) to avoid collisions.
    try:
        log_output = _run_git_command(
            [
                "log",
                "--pretty=format:%H%x1f%an%x1f%ad%x1f%s",
                "--date=iso-strict",
            ],
            cwd=path,
        )
    except RuntimeError as e:
        # If the repo has no commits, ``git log`` exits with code 0 and empty output.
        # An empty string is fine; we will return an empty list.
        log_output = ""

    commits = []
    if not log_output:
        return commits

    for line in log_output.splitlines():
        parts = line.split("\x1f", 3)
        if len(parts) == 4:
            commit_hash, author, date_str, subject = parts
        elif len(parts) == 3:
            commit_hash, author, date_str = parts
            subject = ""
        else:
            continue
        # Convert date to timezone‑naïve ISO string (remove any offset)
        try:
            dt = datetime.fromisoformat(date_str)
            # If the datetime is aware, convert to UTC then drop tzinfo
            if dt.tzinfo is not None:
                dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
            date_iso = dt.isoformat()
        except Exception:
            # Fallback: keep the raw string
            date_iso = date_str
        commits.append({
            "hash": commit_hash,
            "author": author,
            "date": date_iso,
            "message": (subject or "").strip(),
        })
    return commits
