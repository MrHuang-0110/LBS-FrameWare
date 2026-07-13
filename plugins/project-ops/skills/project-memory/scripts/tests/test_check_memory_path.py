import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from check_memory_path import expected_path, needs_fix


def test_expected_path_is_absolute_project_memory():
    assert expected_path(r"e:/LBS-FramWare") == "e:/LBS-FramWare/.memory/memory.jsonl"


def test_expected_path_normalizes_backslashes():
    assert expected_path(r"e:\LBS-FramWare") == "e:/LBS-FramWare/.memory/memory.jsonl"


def test_needs_fix_true_when_unexpanded_variable():
    cur = "${CLAUDE_PROJECT_DIR}/.memory/memory.jsonl"
    assert needs_fix(cur, r"e:/LBS-FramWare") is True


def test_needs_fix_true_when_relative():
    assert needs_fix(".memory/memory.jsonl", r"e:/LBS-FramWare") is True


def test_needs_fix_true_when_other_project():
    cur = "d:/OtherProj/.memory/memory.jsonl"
    assert needs_fix(cur, r"e:/LBS-FramWare") is True


def test_needs_fix_false_when_already_correct():
    cur = "e:/LBS-FramWare/.memory/memory.jsonl"
    assert needs_fix(cur, r"e:/LBS-FramWare") is False


def test_needs_fix_false_ignores_slash_direction_and_case():
    cur = r"E:\LBS-FramWare\.memory\memory.jsonl"
    assert needs_fix(cur, r"e:/LBS-FramWare") is False
