import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from migrate_md_to_graph import parse_md_file, build_graph

SAMPLE = """---
name: dev-team-agents
description: 三角色开发团队
metadata:
  type: project
---

LBS 建了开发团队，见 [[subagent-driven-development]] 流水线。
"""


def test_parse_extracts_name_and_type():
    r = parse_md_file(SAMPLE)
    assert r["name"] == "dev-team-agents"
    assert r["type"] == "project"


def test_parse_extracts_links():
    r = parse_md_file(SAMPLE)
    assert r["links"] == ["subagent-driven-development"]


def test_parse_body_excludes_frontmatter():
    r = parse_md_file(SAMPLE)
    assert "name: dev-team-agents" not in r["body"]
    assert "LBS 建了开发团队" in r["body"]


def test_parse_type_defaults_to_decision():
    txt = "---\nname: foo\ndescription: bar\n---\n\nbody text"
    assert parse_md_file(txt)["type"] == "decision"


def test_build_graph_entities_and_relations():
    files = [parse_md_file(SAMPLE)]
    g = build_graph(files)
    assert g["entities"][0]["name"] == "dev-team-agents"
    # SAMPLE carries off-schema type "project" → mapped to "decision"
    assert g["entities"][0]["entityType"] == "decision"
    assert g["entities"][0]["observations"] == [files[0]["body"]]
    assert {"from": "dev-team-agents", "to": "subagent-driven-development",
            "relationType": "relates_to"} in g["relations"]


def test_parse_handles_crlf():
    crlf = SAMPLE.replace("\n", "\r\n")
    r = parse_md_file(crlf)
    assert r["name"] == "dev-team-agents"
    assert r["type"] == "project"
    assert r["links"] == ["subagent-driven-development"]


def test_build_graph_maps_offschema_type_to_decision():
    off = {"name": "n1", "type": "project", "body": "b", "links": []}
    keep = {"name": "n2", "type": "pitfall", "body": "b", "links": []}
    g = build_graph([off, keep])
    assert g["entities"][0]["entityType"] == "decision"
    assert g["entities"][1]["entityType"] == "pitfall"


def test_build_graph_empty_name_falls_back_to_filename_stem():
    f = {"name": "", "type": "decision", "body": "b", "links": [],
         "filename": "my-note.md"}
    g = build_graph([f])
    assert g["entities"][0]["name"] == "my-note"


def test_build_graph_empty_name_no_filename_raises():
    f = {"name": "", "type": "decision", "body": "b", "links": []}
    import pytest
    with pytest.raises(ValueError):
        build_graph([f])
