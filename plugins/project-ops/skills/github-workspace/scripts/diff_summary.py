"""Generate a one-line summary of staged git changes.

Used by github-workspace to build commit messages and memory-write summaries.
Parsing is separated from git invocation so it is unit-testable.
"""
import subprocess
import sys
from collections import Counter


def parse_numstat(text):
    """Parse `git diff --numstat` output into a stat dict.

    Binary files appear as '-\t-\tpath' and count as a changed file with 0/0.
    """
    files = 0
    insertions = 0
    deletions = 0
    paths = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        add, delete, path = parts[0], parts[1], parts[2]
        files += 1
        if add != "-":
            insertions += int(add)
        if delete != "-":
            deletions += int(delete)
        paths.append(path)
    return {"files": files, "insertions": insertions, "deletions": deletions, "paths": paths}


def top_modules(paths, limit=3):
    """Top-level path segment per file (root files -> '(root)'), ranked by frequency."""
    segments = []
    for p in paths:
        norm = p.replace("\\", "/")
        head = norm.split("/", 1)
        segments.append(head[0] if len(head) > 1 else "(root)")
    ranked = [seg for seg, _ in Counter(segments).most_common()]
    return ranked[:limit]


def format_summary(stat, modules):
    """One-line summary, e.g. '3 files, +42/-7 (backend, gui)'."""
    noun = "file" if stat["files"] == 1 else "files"
    base = "{n} {noun}, +{ins}/-{dels}".format(
        n=stat["files"], noun=noun, ins=stat["insertions"], dels=stat["deletions"]
    )
    if modules:
        base += " (" + ", ".join(modules) + ")"
    return base


def main():
    proc = subprocess.run(
        ["git", "diff", "--cached", "--numstat"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        return 1
    stat = parse_numstat(proc.stdout)
    print(format_summary(stat, top_modules(stat["paths"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
