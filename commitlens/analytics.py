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
import subprocess
from collections import Counter

# Helper functions for git operations without GitPython

def _run_git_command(args, cwd):
    """Run a git command and return its stdout as text.
    Raises RuntimeError on failure.
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
    """Check if the given path is a Git repository."""
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


# -----------------------------------------------------------------------
# Internal helper
# -----------------------------------------------------------------------

def _open_repo(path):
    """Validate *path* and return the path if it is a Git repository.

    Raises:
        FileNotFoundError: If *path* does not exist.
        ValueError: If *path* is not a Git repository.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"The path '{path}' does not exist. Please provide a valid repository path."
        )
    if not _is_git_repository(path):
        raise ValueError(
            f"The folder '{path}' is not a Git repository. Did you run 'git init' there?"
        )
    # Return the path string for downstream functions.
    return path


def _file_change_frequency_fast(repo):
    """Compute file-change frequency using one ``git log`` call.

    Instead of running a separate ``git diff-tree`` for every commit
    (GitPython's ``commit.diff()``), this helper asks Git to walk all
    commits in a single process and report the name-status for each one.
    On a repository with ~8 000 commits this turns minutes into seconds.

    The ``-z`` flag NUL-separates records so filenames with special
    characters are parsed safely.  The ``--root`` flag ensures the very
    first commit is diffed against the empty tree (matching the original
    tree-walk behaviour).  Rename detection is enabled with ``-M``.

    With ``-z``, the output format per file change is::

        <status>\\0<path>\\0           — for A, M, D, T
        <status>\\0<old_path>\\0<new_path>\\0  — for R (rename) or C (copy)

    We use a sentinel in ``--format`` to delimit commit boundaries so
    that each file path is counted at most once per commit.
    """
    _COMMIT_SEP = "---commit-boundary---"

    cmd = [
        "git", "log",
        "--all",
        "--format=%n" + _COMMIT_SEP,  # blank line + sentinel after header
        "--name-status",
        "-M",        # rename detection (matches old behaviour)
        "--root",    # diff the first commit against empty tree
        "-z",        # NUL-separate status entries for safe parsing
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=repo,
            capture_output=True,
            text=False,           # raw bytes — we decode ourselves
            check=True,
        )
    except subprocess.CalledProcessError:
        # Unexpected git failure — treat like an empty repo.
        return {}

    raw = result.stdout
    if not raw:
        return {}  # empty repo or no commits

    frequency = {}

    # With -z, the entire output is NUL-separated tokens.  The tokens
    # are a flat sequence of:
    #   "\n<sentinel>"  — commit boundary
    #   "<status>"      — a status letter (A/M/D/T or Rnnn/Cnnn)
    #   "<path>"        — file path (for R/C this is old_path, followed
    #                      by another path token for new_path)
    # We walk the token list, using the sentinel to reset per-commit
    # deduplication.
    tokens = raw.split(b"\0")
    sep_bytes = _COMMIT_SEP.encode("utf-8")

    seen_in_commit: set[str] = set()
    i = 0

    while i < len(tokens):
        token = tokens[i].strip()

        # Check for commit boundary (sentinel token).
        if sep_bytes in token:
            seen_in_commit = set()
            i += 1
            continue

        if not token:
            i += 1
            continue

        entry = token.decode("utf-8", errors="replace").strip()

        # Status tokens are a single letter optionally followed by digits
        # (e.g. "A", "M", "D", "R100", "C095").
        if len(entry) >= 1 and entry[0] in "AMDRTC":
            status = entry

            if status.startswith("R") or status.startswith("C"):
                # Rename/Copy: next two tokens are old_path and new_path.
                if i + 2 < len(tokens):
                    # old_path is tokens[i+1], new_path is tokens[i+2]
                    new_path = tokens[i + 2].strip().decode("utf-8", errors="replace")
                    i += 3
                else:
                    i += 1
                    continue
                path = new_path  # count under the NEW name
            elif status.startswith("D"):
                # Deleted: next token is the (old) path.
                if i + 1 < len(tokens):
                    path = tokens[i + 1].strip().decode("utf-8", errors="replace")
                    i += 2
                else:
                    i += 1
                    continue
            else:
                # A (added), M (modified), T (type change)
                if i + 1 < len(tokens):
                    path = tokens[i + 1].strip().decode("utf-8", errors="replace")
                    i += 2
                else:
                    i += 1
                    continue

            if path and path not in seen_in_commit:
                seen_in_commit.add(path)
                frequency[path] = frequency.get(path, 0) + 1
        else:
            i += 1

    return frequency


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
    return _file_change_frequency_fast(repo)


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
        log_output = _run_git_command(
            [
                "log",
                "--format=%H",  # one hash per commit
                "--numstat",    # lines added / deleted per file
                "--root",       # include the first commit
            ],
            cwd=repo,
        )
    except RuntimeError:
        # Empty repo or git failure — return empty list.
        return results

    if not log_output:
        return results

    current_hash = None
    added = 0
    deleted = 0

    for line in log_output.splitlines():
        line = line.strip()
        # A 40-char hex string alone on a line is a commit hash.
        if len(line) == 40 and all(c in "0123456789abcdefABCDEF" for c in line):
            # Save the previous commit before starting a new one.
            if current_hash is not None:
                results.append({
                    "hash": current_hash,
                    "lines_added": added,
                    "lines_deleted": deleted,
                })
            current_hash = line
            added = 0
            deleted = 0
        elif line and current_hash is not None:
            # numstat lines look like:  <added>\t<deleted>\t<filename>
            # Binary files show "-" for both counts — skip them.
            parts = line.split("\t", 2)
            if len(parts) == 3 and parts[0] != "-" and parts[1] != "-":
                try:
                    added += int(parts[0])
                    deleted += int(parts[1])
                except ValueError:
                    pass

    # Don't forget the last commit.
    if current_hash is not None:
        results.append({
            "hash": current_hash,
            "lines_added": added,
            "lines_deleted": deleted,
        })

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
