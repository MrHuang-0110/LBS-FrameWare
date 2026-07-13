import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import diff_summary as ds


def test_parse_numstat_counts_files_and_lines():
    text = "10\t2\tsrc/a.py\n5\t0\tsrc/b.py\n"
    stat = ds.parse_numstat(text)
    assert stat["files"] == 2
    assert stat["insertions"] == 15
    assert stat["deletions"] == 2
    assert stat["paths"] == ["src/a.py", "src/b.py"]


def test_parse_numstat_handles_binary_dashes():
    text = "-\t-\tassets/logo.png\n3\t1\tREADME.md\n"
    stat = ds.parse_numstat(text)
    assert stat["files"] == 2
    assert stat["insertions"] == 3
    assert stat["deletions"] == 1


def test_parse_numstat_empty():
    stat = ds.parse_numstat("")
    assert stat == {"files": 0, "insertions": 0, "deletions": 0, "paths": []}


def test_top_modules_dedupes_and_ranks():
    paths = ["src/gui/a.py", "src/gui/b.py", "src/backend/c.py", "README.md"]
    mods = ds.top_modules(paths, limit=3)
    assert mods[0] == "src"  # most frequent top-level segment
    assert "(root)" in mods


def test_format_summary_shape():
    stat = {"files": 3, "insertions": 42, "deletions": 7, "paths": []}
    out = ds.format_summary(stat, ["backend", "gui"])
    assert out == "3 files, +42/-7 (backend, gui)"


def test_format_summary_no_modules():
    stat = {"files": 1, "insertions": 1, "deletions": 0, "paths": []}
    out = ds.format_summary(stat, [])
    assert out == "1 file, +1/-0"
