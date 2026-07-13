import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from encode_project_path import encode_project_path


def test_windows_drive_path():
    assert encode_project_path(r"e:\LBS-FramWare") == "e--LBS-FramWare"


def test_windows_nested_path():
    assert encode_project_path(r"C:\Users\24160\proj") == "C--Users-24160-proj"


def test_posix_path():
    assert encode_project_path("/home/x/proj") == "-home-x-proj"


def test_mixed_separators():
    assert encode_project_path("e:/LBS-FramWare") == "e--LBS-FramWare"
