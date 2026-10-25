"""
test_scanner.py - Tests for the CommitLens repository scanner.

We create temporary Git repositories during each test, run scan_repo()
against them, and verify the results are correct.
"""

import os
import tempfile
import subprocess

import pytest

from commitlens.scanner import scan_repo


# ---------------------------------------------------------------------------
# Constants: The known author identity we configure in every test repo.
# We use these to verify that scan_repo() returns the correct author.
# ---------------------------------------------------------------------------

TEST_AUTHOR_NAME = "Ada Lovelace"
TEST_AUTHOR_EMAIL = "ada@commitlens.dev"


# ---------------------------------------------------------------------------
# Helper: create a tiny Git repo with a given number of commits
# ---------------------------------------------------------------------------

def _create_test_repo(num_commits=1):
    """
    Create a temporary Git repository with dummy commits.

    The repo is configured with a KNOWN author name and email
    (TEST_AUTHOR_NAME / TEST_AUTHOR_EMAIL) so that tests can verify
    the scanner returns the correct author.

    Args:
        num_commits (int): How many commits to create. Use 0 for an empty repo.

    Returns:
        str: The path to the temporary repo folder.
    """
    repo_dir = tempfile.mkdtemp(prefix="commitlens_test_")

    # Initialise a new Git repo
    subprocess.run(["git", "init"], cwd=repo_dir, check=True,
                   capture_output=True)

    # Configure a KNOWN test identity so we can verify author later.
    subprocess.run(
        ["git", "config", "user.name", TEST_AUTHOR_NAME],
        cwd=repo_dir, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", TEST_AUTHOR_EMAIL],
        cwd=repo_dir, check=True, capture_output=True,
    )

    # Create the requested number of commits
    for i in range(1, num_commits + 1):
        file_path = os.path.join(repo_dir, f"file_{i}.txt")
        with open(file_path, "w") as f:
            f.write(f"Content for commit {i}")

        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True,
                       capture_output=True)
        subprocess.run(["git", "commit", "-m", f"Commit number {i}"],
                       cwd=repo_dir, check=True, capture_output=True)

    return repo_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestScanRepo:
    """Tests for the scan_repo() function."""

    # --- Happy path tests ---

    def test_single_commit(self):
        """A repo with one commit should return a list with one entry."""
        repo_path = _create_test_repo(num_commits=1)
        results = scan_repo(repo_path)

        assert len(results) == 1
        commit = results[0]
        assert len(commit["hash"]) == 40          # SHA-1 hashes are 40 hex chars
        assert commit["message"] == "Commit number 1"
        assert "date" in commit

    def test_multiple_commits_are_newest_first(self):
        """A repo with 3 commits should return them newest-first."""
        repo_path = _create_test_repo(num_commits=3)
        results = scan_repo(repo_path)

        assert len(results) == 3
        # iter_commits returns newest first
        assert results[0]["message"] == "Commit number 3"
        assert results[1]["message"] == "Commit number 2"
        assert results[2]["message"] == "Commit number 1"

    def test_commit_has_all_required_fields(self):
        """Every commit dict must have exactly the 4 required keys."""
        repo_path = _create_test_repo(num_commits=1)
        commit = scan_repo(repo_path)[0]

        expected_keys = {"hash", "author", "date", "message"}
        assert set(commit.keys()) == expected_keys

    def test_empty_repo_returns_empty_list(self):
        """A freshly initialised repo with zero commits should return an empty list."""
        repo_path = _create_test_repo(num_commits=0)
        results = scan_repo(repo_path)

        assert results == []

    # --- Author verification tests ---

    def test_author_matches_configured_identity(self):
        """The scanner must return the exact author name that was configured in Git."""
        repo_path = _create_test_repo(num_commits=1)
        commit = scan_repo(repo_path)[0]

        # We configured the repo with TEST_AUTHOR_NAME = "Ada Lovelace",
        # so the scanner must return exactly that.
        assert commit["author"] == TEST_AUTHOR_NAME

    def test_all_commits_have_same_author(self):
        """When a single author makes all commits, every commit should show that author."""
        repo_path = _create_test_repo(num_commits=3)
        results = scan_repo(repo_path)

        for commit in results:
            assert commit["author"] == TEST_AUTHOR_NAME

    # --- Error handling tests ---

    def test_nonexistent_path_raises_file_not_found(self):
        """A path that does not exist should raise FileNotFoundError with a helpful message."""
        fake_path = os.path.join(tempfile.gettempdir(), "this_folder_does_not_exist")

        with pytest.raises(FileNotFoundError, match="does not exist"):
            scan_repo(fake_path)

    def test_invalid_repo_raises_value_error(self):
        """A folder that exists but is NOT a Git repo should raise ValueError."""
        not_a_repo = tempfile.mkdtemp(prefix="commitlens_notrepo_")

        with pytest.raises(ValueError, match="not a Git repository"):
            scan_repo(not_a_repo)

    def test_error_messages_are_helpful(self):
        """Error messages should mention what went wrong and suggest a fix."""
        not_a_repo = tempfile.mkdtemp(prefix="commitlens_notrepo_")

        with pytest.raises(ValueError) as exc_info:
            scan_repo(not_a_repo)

        error_message = str(exc_info.value)
        # The error message should include the path so the user knows which folder failed
        assert not_a_repo in error_message
        # The error message should suggest running 'git init'
        assert "git init" in error_message

    def test_commit_with_utf8_and_non_ascii_characters(self):
        """Commits with non-ASCII UTF-8 characters, emojis, and special chars should not fail decoding."""
        repo_dir = tempfile.mkdtemp(prefix="commitlens_utf8_")
        subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "René Déscartes ✨"],
            cwd=repo_dir, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "rene@commitlens.dev"],
            cwd=repo_dir, check=True, capture_output=True,
        )

        file_path = os.path.join(repo_dir, "file.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("UTF-8 content: \u009d \u2014 \U0001F680")

        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Commit with UTF-8: \u009d — \U0001F680 sparkles ✨"],
            cwd=repo_dir, check=True, capture_output=True,
        )

        results = scan_repo(repo_dir)
        assert len(results) == 1
        assert "✨" in results[0]["author"] or "Ren" in results[0]["author"]
        assert results[0]["message"] is not None
        assert len(results[0]["message"]) > 0

    def test_commit_with_empty_message(self):
        """Commits with empty message should be parsed safely with empty string."""
        repo_dir = tempfile.mkdtemp(prefix="commitlens_empty_msg_")
        subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", TEST_AUTHOR_NAME],
            cwd=repo_dir, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", TEST_AUTHOR_EMAIL],
            cwd=repo_dir, check=True, capture_output=True,
        )

        file_path = os.path.join(repo_dir, "empty.txt")
        with open(file_path, "w") as f:
            f.write("content")

        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "--allow-empty-message", "-m", ""],
            cwd=repo_dir, check=True, capture_output=True,
        )

        results = scan_repo(repo_dir)
        assert len(results) == 1
        assert results[0]["message"] == ""
