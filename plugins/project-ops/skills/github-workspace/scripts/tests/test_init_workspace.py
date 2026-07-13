import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import init_workspace as iw


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    """A git repo on 'main' with one commit and a bare 'origin' remote."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(origin)], check=True, capture_output=True)
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init")
    _git(work, "checkout", "-b", "main")
    _git(work, "config", "user.email", "t@t.t")
    _git(work, "config", "user.name", "t")
    (work / "f.txt").write_text("hi", encoding="utf-8")
    _git(work, "add", ".")
    _git(work, "commit", "-m", "init")
    _git(work, "remote", "add", "origin", str(origin))
    _git(work, "push", "-u", "origin", "main")
    return work


def test_creates_workspace_from_main(repo):
    result = iw.init_workspace(cwd=repo)
    assert result["action"] == "created"
    assert result["branch"] == "workspace"
    assert result["pushed"] is True
    assert iw.local_branch_exists("workspace", repo)
    assert iw.remote_branch_exists("workspace", "origin", repo)


def test_reuses_existing_local_branch(repo):
    _git(repo, "branch", "workspace")
    result = iw.init_workspace(cwd=repo)
    assert result["action"] == "reused-local"


def test_reuses_existing_remote_branch(repo):
    # create + push workspace, then delete it locally so only remote has it
    _git(repo, "checkout", "-b", "workspace")
    _git(repo, "push", "-u", "origin", "workspace")
    _git(repo, "checkout", "main")
    _git(repo, "branch", "-D", "workspace")
    result = iw.init_workspace(cwd=repo)
    assert result["action"] == "reused-remote"
    assert iw.local_branch_exists("workspace", repo)


def test_rejects_dirty_worktree(repo):
    (repo / "dirty.txt").write_text("x", encoding="utf-8")
    with pytest.raises(RuntimeError, match="dirty"):
        iw.init_workspace(cwd=repo)


def test_worktree_clean_detects_state(repo):
    assert iw.worktree_clean(repo) is True
    (repo / "dirty.txt").write_text("x", encoding="utf-8")
    assert iw.worktree_clean(repo) is False
