"""
test_analytics.py - Tests for the CommitLens analytics module.

We create temporary Git repositories with known changes, run the analytics
functions against them, and verify the results are correct.

Test count: 22 tests across 5 test classes.
"""

import os
import tempfile
import subprocess

import pytest

from commitlens.scanner import scan_repo
from commitlens.analytics import (
    total_commits,
    commits_by_author,
    file_change_frequency,
    lines_changed,
    code_churn,
)


# ---------------------------------------------------------------------------
# Constants: known author identities used across all test repos
# ---------------------------------------------------------------------------

TEST_AUTHOR_NAME = "Ada Lovelace"
TEST_AUTHOR_EMAIL = "ada@commitlens.dev"

SECOND_AUTHOR_NAME = "Bob Martin"
SECOND_AUTHOR_EMAIL = "bob@commitlens.dev"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_git(repo_dir, *args):
    """Run a git command in the given directory."""
    subprocess.run(
        ["git"] + list(args),
        cwd=repo_dir, check=True, capture_output=True,
    )


def _create_test_repo(num_commits=1):
    """Create a temporary Git repo with *num_commits* commits.

    Each commit adds a new text file (file_1.txt, file_2.txt, …) with
    one line of content.  Use 0 for an empty (freshly initialised) repo.
    """
    repo_dir = tempfile.mkdtemp(prefix="commitlens_analytics_")
    _run_git(repo_dir, "init")
    _run_git(repo_dir, "config", "user.name", TEST_AUTHOR_NAME)
    _run_git(repo_dir, "config", "user.email", TEST_AUTHOR_EMAIL)

    for i in range(1, num_commits + 1):
        path = os.path.join(repo_dir, f"file_{i}.txt")
        with open(path, "w") as f:
            f.write(f"Content for commit {i}\n")
        _run_git(repo_dir, "add", ".")
        _run_git(repo_dir, "commit", "-m", f"Commit number {i}")

    return repo_dir


def _create_multi_author_repo():
    """Create a repo with commits from two different authors.

    Ada Lovelace makes 2 commits, Bob Martin makes 3 commits.
    """
    repo_dir = tempfile.mkdtemp(prefix="commitlens_analytics_")
    _run_git(repo_dir, "init")

    # --- Ada's commits (2) ---
    _run_git(repo_dir, "config", "user.name", TEST_AUTHOR_NAME)
    _run_git(repo_dir, "config", "user.email", TEST_AUTHOR_EMAIL)
    for i in range(1, 3):
        path = os.path.join(repo_dir, f"ada_{i}.txt")
        with open(path, "w") as f:
            f.write(f"Ada's file {i}\n")
        _run_git(repo_dir, "add", ".")
        _run_git(repo_dir, "commit", "-m", f"Ada commit {i}")

    # --- Bob's commits (3) ---
    _run_git(repo_dir, "config", "user.name", SECOND_AUTHOR_NAME)
    _run_git(repo_dir, "config", "user.email", SECOND_AUTHOR_EMAIL)
    for i in range(1, 4):
        path = os.path.join(repo_dir, f"bob_{i}.txt")
        with open(path, "w") as f:
            f.write(f"Bob's file {i}\n")
        _run_git(repo_dir, "add", ".")
        _run_git(repo_dir, "commit", "-m", f"Bob commit {i}")

    return repo_dir


# ===========================================================================
# Tests for total_commits()
# ===========================================================================

class TestTotalCommits:
    """Tests for total_commits()."""

    def test_single_commit(self):
        """One commit → total_commits returns 1."""
        commits = scan_repo(_create_test_repo(num_commits=1))
        assert total_commits(commits) == 1

    def test_multiple_commits(self):
        """Five commits → total_commits returns 5."""
        commits = scan_repo(_create_test_repo(num_commits=5))
        assert total_commits(commits) == 5

    def test_empty_repo(self):
        """Empty repo → total_commits returns 0."""
        commits = scan_repo(_create_test_repo(num_commits=0))
        assert total_commits(commits) == 0


# ===========================================================================
# Tests for commits_by_author()
# ===========================================================================

class TestCommitsByAuthor:
    """Tests for commits_by_author()."""

    def test_single_author(self):
        """All commits by one author → {author: count}."""
        commits = scan_repo(_create_test_repo(num_commits=3))
        result = commits_by_author(commits)
        assert result == {TEST_AUTHOR_NAME: 3}

    def test_multiple_authors(self):
        """Two authors with known commit counts."""
        commits = scan_repo(_create_multi_author_repo())
        result = commits_by_author(commits)
        assert result == {TEST_AUTHOR_NAME: 2, SECOND_AUTHOR_NAME: 3}

    def test_empty_list(self):
        """No commits → empty dict."""
        assert commits_by_author([]) == {}


# ===========================================================================
# Tests for file_change_frequency()
# ===========================================================================

class TestFileChangeFrequency:
    """Tests for file_change_frequency()."""

    def test_single_file_changed_once(self):
        """One commit adding one file → frequency is 1."""
        repo = _create_test_repo(num_commits=1)
        result = file_change_frequency(repo)
        assert result == {"file_1.txt": 1}

    def test_same_file_changed_multiple_times(self):
        """Modify the same file in 3 separate commits → frequency is 3."""
        repo_dir = tempfile.mkdtemp(prefix="commitlens_analytics_")
        _run_git(repo_dir, "init")
        _run_git(repo_dir, "config", "user.name", TEST_AUTHOR_NAME)
        _run_git(repo_dir, "config", "user.email", TEST_AUTHOR_EMAIL)

        path = os.path.join(repo_dir, "hotspot.txt")
        for i in range(1, 4):
            with open(path, "w") as f:
                f.write(f"Version {i}\n")
            _run_git(repo_dir, "add", ".")
            _run_git(repo_dir, "commit", "-m", f"Update v{i}")

        result = file_change_frequency(repo_dir)
        assert result == {"hotspot.txt": 3}

    def test_multiple_files(self):
        """Three commits, each adding a new file → each has frequency 1."""
        repo = _create_test_repo(num_commits=3)
        result = file_change_frequency(repo)
        assert result == {"file_1.txt": 1, "file_2.txt": 1, "file_3.txt": 1}

    def test_empty_repo(self):
        """Empty repo → empty dict."""
        repo = _create_test_repo(num_commits=0)
        assert file_change_frequency(repo) == {}

    def test_deleted_file_counted_in_both_commits(self):
        """A file created then deleted should be counted in both commits."""
        repo_dir = tempfile.mkdtemp(prefix="commitlens_analytics_")
        _run_git(repo_dir, "init")
        _run_git(repo_dir, "config", "user.name", TEST_AUTHOR_NAME)
        _run_git(repo_dir, "config", "user.email", TEST_AUTHOR_EMAIL)

        path = os.path.join(repo_dir, "doomed.txt")
        with open(path, "w") as f:
            f.write("I will be deleted\n")
        _run_git(repo_dir, "add", ".")
        _run_git(repo_dir, "commit", "-m", "Add doomed file")

        os.remove(path)
        _run_git(repo_dir, "add", "-A", ".")
        _run_git(repo_dir, "commit", "-m", "Delete doomed file")

        result = file_change_frequency(repo_dir)
        assert result["doomed.txt"] == 2

    def test_renamed_file_counted_under_new_name(self):
        """A renamed file is counted under its NEW name in the rename commit."""
        repo_dir = tempfile.mkdtemp(prefix="commitlens_analytics_")
        _run_git(repo_dir, "init")
        _run_git(repo_dir, "config", "user.name", TEST_AUTHOR_NAME)
        _run_git(repo_dir, "config", "user.email", TEST_AUTHOR_EMAIL)

        # Commit 1: create old.txt
        old_path = os.path.join(repo_dir, "old.txt")
        with open(old_path, "w") as f:
            f.write("I will be renamed\n")
        _run_git(repo_dir, "add", ".")
        _run_git(repo_dir, "commit", "-m", "Add old.txt")

        # Commit 2: rename old.txt → new.txt (using git mv for clean rename)
        _run_git(repo_dir, "mv", "old.txt", "new.txt")
        _run_git(repo_dir, "commit", "-m", "Rename old.txt to new.txt")

        result = file_change_frequency(repo_dir)
        # Creation commit counts under the old name
        assert result.get("old.txt") == 1
        # Rename commit counts under the new name
        assert result.get("new.txt") == 1

    def test_binary_file_is_counted(self):
        """Binary files should still appear in the frequency count."""
        repo_dir = tempfile.mkdtemp(prefix="commitlens_analytics_")
        _run_git(repo_dir, "init")
        _run_git(repo_dir, "config", "user.name", TEST_AUTHOR_NAME)
        _run_git(repo_dir, "config", "user.email", TEST_AUTHOR_EMAIL)

        # Create a file with binary content (includes null bytes → Git
        # detects it as binary).
        bin_path = os.path.join(repo_dir, "image.bin")
        with open(bin_path, "wb") as f:
            f.write(bytes(range(256)))
        _run_git(repo_dir, "add", ".")
        _run_git(repo_dir, "commit", "-m", "Add binary file")

        result = file_change_frequency(repo_dir)
        assert "image.bin" in result
        assert result["image.bin"] == 1

    def test_renamed_and_modified_in_same_commit(self):
        """A file renamed and another modified in the same commit."""
        repo_dir = tempfile.mkdtemp(prefix="commitlens_analytics_")
        _run_git(repo_dir, "init")
        _run_git(repo_dir, "config", "user.name", TEST_AUTHOR_NAME)
        _run_git(repo_dir, "config", "user.email", TEST_AUTHOR_EMAIL)

        # Commit 1: create two files
        for name in ("alpha.txt", "beta.txt"):
            with open(os.path.join(repo_dir, name), "w") as f:
                f.write(f"{name} content\n")
        _run_git(repo_dir, "add", ".")
        _run_git(repo_dir, "commit", "-m", "Add alpha and beta")

        # Commit 2: rename alpha → gamma, modify beta
        _run_git(repo_dir, "mv", "alpha.txt", "gamma.txt")
        with open(os.path.join(repo_dir, "beta.txt"), "w") as f:
            f.write("beta updated\n")
        _run_git(repo_dir, "add", ".")
        _run_git(repo_dir, "commit", "-m", "Rename alpha and modify beta")

        result = file_change_frequency(repo_dir)
        # Creation commit: alpha.txt=1, beta.txt=1
        # Rename+modify commit: gamma.txt=1 (rename), beta.txt gets +1
        assert result.get("alpha.txt") == 1
        assert result.get("beta.txt") == 2
        assert result.get("gamma.txt") == 1

    def test_mixed_add_modify_delete_in_single_commit(self):
        """A commit that adds, modifies, and deletes files simultaneously."""
        repo_dir = tempfile.mkdtemp(prefix="commitlens_analytics_")
        _run_git(repo_dir, "init")
        _run_git(repo_dir, "config", "user.name", TEST_AUTHOR_NAME)
        _run_git(repo_dir, "config", "user.email", TEST_AUTHOR_EMAIL)

        # Commit 1: create keep.txt and remove_me.txt
        for name in ("keep.txt", "remove_me.txt"):
            with open(os.path.join(repo_dir, name), "w") as f:
                f.write(f"Initial {name}\n")
        _run_git(repo_dir, "add", ".")
        _run_git(repo_dir, "commit", "-m", "Initial files")

        # Commit 2: modify keep.txt, delete remove_me.txt, add new.txt
        with open(os.path.join(repo_dir, "keep.txt"), "w") as f:
            f.write("Modified content\n")
        os.remove(os.path.join(repo_dir, "remove_me.txt"))
        with open(os.path.join(repo_dir, "new.txt"), "w") as f:
            f.write("Brand new file\n")
        _run_git(repo_dir, "add", "-A", ".")
        _run_git(repo_dir, "commit", "-m", "Mixed operations")

        result = file_change_frequency(repo_dir)
        assert result["keep.txt"] == 2       # created + modified
        assert result["remove_me.txt"] == 2  # created + deleted
        assert result["new.txt"] == 1        # added

    def test_nonexistent_path_raises_file_not_found(self):
        """Passing a non-existent path should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            file_change_frequency("/tmp/does_not_exist_at_all")

    def test_non_repo_raises_value_error(self):
        """Passing a regular directory (not a repo) should raise ValueError."""
        plain_dir = tempfile.mkdtemp(prefix="commitlens_analytics_")
        with pytest.raises(ValueError):
            file_change_frequency(plain_dir)

    def test_many_files_in_root_commit(self):
        """Root commit with many files should count all of them."""
        repo_dir = tempfile.mkdtemp(prefix="commitlens_analytics_")
        _run_git(repo_dir, "init")
        _run_git(repo_dir, "config", "user.name", TEST_AUTHOR_NAME)
        _run_git(repo_dir, "config", "user.email", TEST_AUTHOR_EMAIL)

        # Create 20 files in one commit
        for i in range(20):
            with open(os.path.join(repo_dir, f"bulk_{i}.txt"), "w") as f:
                f.write(f"File {i}\n")
        _run_git(repo_dir, "add", ".")
        _run_git(repo_dir, "commit", "-m", "Bulk add 20 files")

        result = file_change_frequency(repo_dir)
        assert len(result) == 20
        for i in range(20):
            assert result[f"bulk_{i}.txt"] == 1


# ===========================================================================
# Tests for lines_changed()
# ===========================================================================

class TestLinesChanged:
    """Tests for lines_changed()."""

    def test_first_commit_counts_as_additions(self):
        """The very first commit's new lines are all counted as additions."""
        repo_dir = tempfile.mkdtemp(prefix="commitlens_analytics_")
        _run_git(repo_dir, "init")
        _run_git(repo_dir, "config", "user.name", TEST_AUTHOR_NAME)
        _run_git(repo_dir, "config", "user.email", TEST_AUTHOR_EMAIL)

        path = os.path.join(repo_dir, "hello.txt")
        with open(path, "w") as f:
            f.write("line 1\nline 2\nline 3\nline 4\nline 5\n")
        _run_git(repo_dir, "add", ".")
        _run_git(repo_dir, "commit", "-m", "First commit with 5 lines")

        result = lines_changed(repo_dir)
        assert len(result) == 1
        assert result[0]["lines_added"] == 5
        assert result[0]["lines_deleted"] == 0

    def test_modification_shows_adds_and_deletes(self):
        """Replacing lines should show both additions and deletions."""
        repo_dir = tempfile.mkdtemp(prefix="commitlens_analytics_")
        _run_git(repo_dir, "init")
        _run_git(repo_dir, "config", "user.name", TEST_AUTHOR_NAME)
        _run_git(repo_dir, "config", "user.email", TEST_AUTHOR_EMAIL)

        path = os.path.join(repo_dir, "code.txt")
        # Commit 1: 3 lines
        with open(path, "w") as f:
            f.write("alpha\nbeta\ngamma\n")
        _run_git(repo_dir, "add", ".")
        _run_git(repo_dir, "commit", "-m", "Initial 3 lines")

        # Commit 2: keep "alpha", replace "beta"+"gamma" with 3 new lines
        with open(path, "w") as f:
            f.write("alpha\nBETA_NEW\nGAMMA_NEW\nDELTA_NEW\n")
        _run_git(repo_dir, "add", ".")
        _run_git(repo_dir, "commit", "-m", "Replace 2 lines with 3")

        result = lines_changed(repo_dir)
        # Newest first → result[0] is the modification commit
        assert result[0]["lines_added"] == 3    # BETA_NEW, GAMMA_NEW, DELTA_NEW
        assert result[0]["lines_deleted"] == 2  # beta, gamma

    def test_multiple_commits_each_have_stats(self):
        """Every commit dict must have hash, lines_added, and lines_deleted."""
        repo = _create_test_repo(num_commits=3)
        result = lines_changed(repo)
        assert len(result) == 3
        for entry in result:
            assert "hash" in entry
            assert isinstance(entry["lines_added"], int)
            assert isinstance(entry["lines_deleted"], int)

    def test_empty_repo(self):
        """Empty repo → empty list."""
        repo = _create_test_repo(num_commits=0)
        assert lines_changed(repo) == []

    def test_binary_file_excluded_from_line_counts(self):
        """A commit with only a binary file should show 0 added / 0 deleted."""
        repo_dir = tempfile.mkdtemp(prefix="commitlens_analytics_")
        _run_git(repo_dir, "init")
        _run_git(repo_dir, "config", "user.name", TEST_AUTHOR_NAME)
        _run_git(repo_dir, "config", "user.email", TEST_AUTHOR_EMAIL)

        bin_path = os.path.join(repo_dir, "data.bin")
        with open(bin_path, "wb") as f:
            f.write(bytes(range(256)))  # includes null byte → binary
        _run_git(repo_dir, "add", ".")
        _run_git(repo_dir, "commit", "-m", "Add binary only")

        result = lines_changed(repo_dir)
        assert len(result) == 1
        assert result[0]["lines_added"] == 0
        assert result[0]["lines_deleted"] == 0

    def test_deleted_file_counts_lines_as_deleted(self):
        """Deleting a 3-line file should count 3 lines as deleted."""
        repo_dir = tempfile.mkdtemp(prefix="commitlens_analytics_")
        _run_git(repo_dir, "init")
        _run_git(repo_dir, "config", "user.name", TEST_AUTHOR_NAME)
        _run_git(repo_dir, "config", "user.email", TEST_AUTHOR_EMAIL)

        path = os.path.join(repo_dir, "temp.txt")
        with open(path, "w") as f:
            f.write("line 1\nline 2\nline 3\n")
        _run_git(repo_dir, "add", ".")
        _run_git(repo_dir, "commit", "-m", "Add file with 3 lines")

        os.remove(path)
        _run_git(repo_dir, "add", "-A", ".")
        _run_git(repo_dir, "commit", "-m", "Delete the file")

        result = lines_changed(repo_dir)
        # Newest first → result[0] is the delete commit
        assert result[0]["lines_added"] == 0
        assert result[0]["lines_deleted"] == 3


# ===========================================================================
# Tests for code_churn()
# ===========================================================================

class TestCodeChurn:
    """Tests for code_churn()."""

    def test_churn_sums_correctly(self):
        """code_churn() should sum all additions and deletions."""
        stats = [
            {"hash": "aaa", "lines_added": 10, "lines_deleted": 3},
            {"hash": "bbb", "lines_added": 20, "lines_deleted": 5},
        ]
        result = code_churn(stats)
        assert result["total_lines_added"] == 30
        assert result["total_lines_deleted"] == 8
        assert result["total_churn"] == 38

    def test_churn_from_real_repo(self):
        """End-to-end: create a repo, compute lines_changed, then code_churn."""
        repo_dir = tempfile.mkdtemp(prefix="commitlens_analytics_")
        _run_git(repo_dir, "init")
        _run_git(repo_dir, "config", "user.name", TEST_AUTHOR_NAME)
        _run_git(repo_dir, "config", "user.email", TEST_AUTHOR_EMAIL)

        path = os.path.join(repo_dir, "main.txt")

        # Commit 1: add 3 lines (a, b, c)
        with open(path, "w") as f:
            f.write("a\nb\nc\n")
        _run_git(repo_dir, "add", ".")
        _run_git(repo_dir, "commit", "-m", "Add 3 lines")

        # Commit 2: keep "a", replace "b"+"c" with "B"+"C"+"D"
        #   → +3 lines (B, C, D), -2 lines (b, c)
        with open(path, "w") as f:
            f.write("a\nB\nC\nD\n")
        _run_git(repo_dir, "add", ".")
        _run_git(repo_dir, "commit", "-m", "Replace and extend")

        stats = lines_changed(repo_dir)
        result = code_churn(stats)
        # Commit 1: +3 added, 0 deleted
        # Commit 2: +3 added, 2 deleted
        assert result["total_lines_added"] == 6     # 3 + 3
        assert result["total_lines_deleted"] == 2   # 0 + 2
        assert result["total_churn"] == 8           # 6 + 2

    def test_empty_stats(self):
        """Empty list → all zeros."""
        result = code_churn([])
        assert result == {
            "total_lines_added": 0,
            "total_lines_deleted": 0,
            "total_churn": 0,
        }
