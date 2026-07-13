"""从 memory.jsonl（知识图谱）生成轻量索引 index.md。

两层记忆架构的索引层：开场只读 index.md（名字/类型/一句话摘要），
正文按需用 open_nodes/search_nodes 读 memory.jsonl。索引是纯派生物，
每次写入后重建，绝不手工维护，避免与正文漂移。

用法：
  python build_index.py <memory.jsonl 路径> <index.md 输出路径>
"""
import json
import sys

SUMMARY_MAX = 50
# 类型展示顺序：高频入口在前
TYPE_ORDER = ["progress", "pitfall", "operation", "decision", "convention", "component"]


def first_sentence(text: str) -> str:
    """取正文首句作摘要：在首个句号/换行处截断，再限长到 SUMMARY_MAX。"""
    s = (text or "").strip()
    for sep in ("\n", "。", ". "):
        idx = s.find(sep)
        if idx != -1:
            s = s[:idx]
    s = s.strip()
    return s[:SUMMARY_MAX]


def load_graph(memory_path: str) -> dict:
    """读 memory.jsonl 为 {entities, relations}；文件不存在或空 → 空图。"""
    entities, relations = [], []
    try:
        with open(memory_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                if item.get("type") == "entity":
                    entities.append(item)
                elif item.get("type") == "relation":
                    relations.append(item)
    except FileNotFoundError:
        pass
    return {"entities": entities, "relations": relations}


def build_index(graph: dict) -> str:
    """生成 index.md 文本：按类型分组，每条一行 `- name — 摘要`。"""
    entities = graph.get("entities", [])
    lines = ["# 项目记忆索引（自动生成，勿手改；正文在 memory.jsonl）", ""]
    if not entities:
        lines.append("（暂无记忆）")
        return "\n".join(lines) + "\n"

    by_type = {}
    for e in entities:
        by_type.setdefault(e.get("entityType", "decision"), []).append(e)

    ordered = TYPE_ORDER + [t for t in by_type if t not in TYPE_ORDER]
    for t in ordered:
        if t not in by_type:
            continue
        lines.append(f"## {t}")
        for e in by_type[t]:
            obs = e.get("observations") or []
            summary = first_sentence(obs[0]) if obs else ""
            lines.append(f"- {e['name']} — {summary}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


if __name__ == "__main__":
    memory_path, index_path = sys.argv[1], sys.argv[2]
    md = build_index(load_graph(memory_path))
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"wrote {index_path}")
