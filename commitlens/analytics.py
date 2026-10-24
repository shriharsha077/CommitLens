"""
analytics.py - Computes repository-level metrics from Git history.

This module provides five functions that sit between the scanner (which
extracts raw commit data) and the future dashboard (which will visualise
the metrics).

Pure functions (operate on scan_repo() output):
    total_commits()       – count the total number of commits
    commits_by_author()   – tally commits per author
    code_churn()          – summarise line-change stats into one metric

Functions that need Git repository access (for diffs):
    file_change_frequency()  – how many commits touched each file
    lines_changed()          – per-commit lines added / deleted
"""

import os
from collections import Counter

from git import Repo
from git.exc import InvalidGitRepositoryError


# -----------------------------------------------------------------------
# Internal helper
# -----------------------------------------------------------------------

def _open_repo(path):
    """Validate *path* and return a GitPython ``Repo`` object.

    Raises:
        FileNotFoundError: If *path* does not exist on disk.
        ValueError: If *path* exists but is not a valid Git repository.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"The path '{path}' does not exist. "
            f"Please provide the full path to a Git repository folder."
        )
    try:
        return Repo(path)
    except InvalidGitRepositoryError:
        raise ValueError(
            f"The folder '{path}' is not a Git repository. "
            f"A Git repository must contain a '.git' folder."
        )


# -----------------------------------------------------------------------
# Pure functions (operate on the list returned by scan_repo())
# -----------------------------------------------------------------------

def total_commits(commits):
    """Return the total number of commits.

    Think of it like counting entries in a diary — each commit is one
    entry, and this function tells you how many entries there are.

    Args:
        commits (list[dict]): The list returned by scan_repo().

    Returns:
        int: The number of commits.
    """
    return len(commits)


def commits_by_author(commits):
    """Count how many commits each author made.

    Imagine a classroom where each student hands in homework.  This
    function counts how many pieces each student turned in.

    Args:
        commits (list[dict]): The list returned by scan_repo().

    Returns:
        dict[str, int]: Mapping of author name → commit count,
        e.g. {"Ada Lovelace": 5, "Bob Martin": 3}.
    """
    return dict(Counter(c["author"] for c in commits))


# -----------------------------------------------------------------------
# Git-accessing functions (need the repository for diffs)
# -----------------------------------------------------------------------

def file_change_frequency(repo_path):
    """Count how many commits touched each file path.

    Every time you make a commit, Git records which files you changed.
    A file that shows up in many commits is a "hotspot" — it changes a
    lot, which can signal important or risky code.

    Change-type handling:
        * **Added / Modified** — counted under the file path.
        * **Deleted** — counted under the path the file had when it was
          deleted.
        * **Renamed** — Git rename detection (``-M``) is enabled.  The
          rename commit is counted under the **new** (destination) name.
          The original creation commit still counts under the **old** name.
        * **Binary files** — included in the count (they are still
          "changed", even though Git cannot show a line-level diff).

    Args:
        repo_path (str): Path to a local Git repository.

    Returns:
        dict[str, int]: Mapping of file path → number of commits that
        changed it.

    Raises:
        FileNotFoundError: If *repo_path* does not exist.
        ValueError: If *repo_path* is not a Git repository.
    """
    repo = _open_repo(repo_path)
    frequency = {}

    try:
        for commit in repo.iter_commits():
            # Track files already counted in THIS commit so we never
            # double-count a path within a single commit.
            seen_in_commit = set()

            if commit.parents:
                # Normal commit: diff the first parent → this commit.
                # M=True enables rename detection (-M flag).
                diffs = commit.parents[0].diff(commit, M=True)

                for d in diffs:
                    if d.deleted_file:
                        # File was removed — count under its old path.
                        path = d.a_path
                    elif d.renamed_file:
                        # File was renamed — count under the NEW name.
                        path = d.b_path
                    else:
                        # Added or modified — use the current path.
                        path = d.b_path

                    if path and path not in seen_in_commit:
                        seen_in_commit.add(path)
                        frequency[path] = frequency.get(path, 0) + 1
            else:
                # First commit (no parent): every blob in the tree is new.
                # Walking the tree is simpler and avoids diff-direction
                # issues that arise when there is no parent to compare to.
                for item in commit.tree.traverse():
                    if item.type == "blob":
                        path = item.path
                        if path not in seen_in_commit:
                            seen_in_commit.add(path)
                            frequency[path] = frequency.get(path, 0) + 1

    except ValueError:
        # Empty repo — HEAD doesn't exist yet.
        pass

    return frequency


def lines_changed(repo_path):
    """Return per-commit counts of lines added and deleted.

    When you edit a file, some lines are added (new code) and some are
    removed (deleted code).  This function walks through every commit and
    asks Git: "compared to the previous version, how many lines changed?"

    Special cases:
        * **Binary files** are excluded — Git cannot meaningfully diff
          them, so they contribute 0 to both ``lines_added`` and
          ``lines_deleted``.
        * **First commit** — GitPython internally uses the ``--root``
          flag so that the first commit's newly added lines are counted
          correctly as additions (compared against the empty tree).

    Args:
        repo_path (str): Path to a local Git repository.

    Returns:
        list[dict]: Newest-first list of dicts, each containing:
            - ``hash``          (str): The full 40-character commit hash.
            - ``lines_added``   (int): Lines added in this commit.
            - ``lines_deleted`` (int): Lines deleted in this commit.

    Raises:
        FileNotFoundError: If *repo_path* does not exist.
        ValueError: If *repo_path* is not a Git repository.
    """
    repo = _open_repo(repo_path)
    results = []

    try:
        for commit in repo.iter_commits():
            # commit.stats uses 'git diff-tree --numstat' internally.
            # For root commits it adds the --root flag automatically.
            # Binary files appear as "-/-" in numstat output; GitPython
            # converts those to 0, so they don't inflate line counts.
            stats = commit.stats.total
            results.append({
                "hash": commit.hexsha,
                "lines_added": stats.get("insertions", 0),
                "lines_deleted": stats.get("deletions", 0),
            })
    except ValueError:
        # Empty repo — no commits to iterate.
        pass

    return results


# -----------------------------------------------------------------------
# Pure summary function (operates on lines_changed() output)
# -----------------------------------------------------------------------

def code_churn(line_stats):
    """Summarise per-commit line stats into total code churn.

    "Code churn" measures the total amount of change in a codebase.  It
    is calculated as **total lines added + total lines deleted**.  High
    churn can mean the code is actively evolving, or it might signal
    instability (lots of rewriting).

    This function takes the detailed per-commit breakdown from
    ``lines_changed()`` and sums it into one grand total — like getting
    the "bottom line" on a spreadsheet.

    Args:
        line_stats (list[dict]): The list returned by ``lines_changed()``.

    Returns:
        dict: Contains three keys:
            - ``total_lines_added``   (int)
            - ``total_lines_deleted`` (int)
            - ``total_churn``         (int): added + deleted
    """
    total_added = sum(entry["lines_added"] for entry in line_stats)
    total_deleted = sum(entry["lines_deleted"] for entry in line_stats)
    return {
        "total_lines_added": total_added,
        "total_lines_deleted": total_deleted,
        "total_churn": total_added + total_deleted,
    }
