"""Idempotently create or reuse the workspace branch and push it with upstream.

Pure git-CLI wrapper; all functions take an explicit cwd so they are testable
against a temp repo. No GitHub MCP dependency — core git only.
"""
import argparse
import subprocess
import sys


def run_git(args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def worktree_clean(cwd=None):
    proc = run_git(["status", "--porcelain"], cwd=cwd)
    return proc.returncode == 0 and proc.stdout.strip() == ""


def local_branch_exists(name, cwd=None):
    proc = run_git(["rev-parse", "--verify", "--quiet", "refs/heads/" + name], cwd=cwd)
    return proc.returncode == 0


def remote_branch_exists(name, remote="origin", cwd=None):
    if not _remote_exists(remote, cwd=cwd):
        return False
    return _remote_has_branch(name, remote, cwd=cwd)


def _remote_exists(remote, cwd=None):
    proc = run_git(["remote"], cwd=cwd)
    remotes = proc.stdout.split()
    return remote in remotes


def _remote_has_branch(name, remote, cwd=None):
    """ls-remote branch check; assumes <remote> is already known to exist."""
    proc = run_git(["ls-remote", "--heads", remote, name], cwd=cwd)
    return proc.returncode == 0 and proc.stdout.strip() != ""


def init_workspace(branch="workspace", main="main", remote="origin", cwd=None):
    if not worktree_clean(cwd=cwd):
        raise RuntimeError("dirty worktree: commit or stash changes before init")

    has_remote = _remote_exists(remote, cwd=cwd)

    if local_branch_exists(branch, cwd=cwd):
        run_git(["checkout", branch], cwd=cwd)
        action = "reused-local"
    elif has_remote and _remote_has_branch(branch, remote, cwd=cwd):
        run_git(["checkout", "-b", branch, remote + "/" + branch], cwd=cwd)
        action = "reused-remote"
    else:
        run_git(["checkout", "-b", branch, main], cwd=cwd)
        action = "created"

    pushed = False
    if has_remote:
        proc = run_git(["push", "-u", remote, branch], cwd=cwd)
        pushed = proc.returncode == 0

    return {"action": action, "branch": branch, "pushed": pushed}


def main():
    parser = argparse.ArgumentParser(description="Init/reuse the workspace branch.")
    parser.add_argument("--branch", default="workspace")
    parser.add_argument("--main", default="main")
    parser.add_argument("--remote", default="origin")
    args = parser.parse_args()
    try:
        result = init_workspace(branch=args.branch, main=args.main, remote=args.remote)
    except RuntimeError as e:
        sys.stderr.write(str(e) + "\n")
        return 1
    print("{action}: {branch} (pushed={pushed})".format(**result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
