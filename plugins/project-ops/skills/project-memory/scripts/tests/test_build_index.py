import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from build_index import first_sentence, build_index


def test_first_sentence_truncates_long_text():
    text = "这是一个很长很长的观察内容" * 10
    s = first_sentence(text)
    assert len(s) <= 50


def test_first_sentence_stops_at_period():
    assert first_sentence("第一句。第二句。") == "第一句"


def test_first_sentence_stops_at_newline():
    assert first_sentence("标题行\n正文其余") == "标题行"


def test_first_sentence_strips_markdown_frontmatter_noise():
    assert first_sentence("  第一句话  ") == "第一句话"


def test_build_index_groups_by_type_and_lists_entries():
    graph = {
        "entities": [
            {"name": "project-progress", "entityType": "progress",
             "observations": ["截至今日的进度快照。详情省略。"]},
            {"name": "npx-var-pitfall", "entityType": "pitfall",
             "observations": ["${CLAUDE_PROJECT_DIR} 在 MCP env 不展开。"]},
        ],
        "relations": [],
    }
    md = build_index(graph)
    # 按类型分组标题
    assert "## progress" in md
    assert "## pitfall" in md
    # 每条一行：- name — 摘要
    assert "- project-progress — 截至今日的进度快照" in md
    assert "- npx-var-pitfall — ${CLAUDE_PROJECT_DIR} 在 MCP env 不展开" in md


def test_build_index_empty_graph():
    md = build_index({"entities": [], "relations": []})
    assert "（暂无记忆）" in md


def test_build_index_entity_without_observations():
    graph = {"entities": [{"name": "foo", "entityType": "component",
                           "observations": []}], "relations": []}
    md = build_index(graph)
    assert "- foo —" in md  # 无摘要也要列出
