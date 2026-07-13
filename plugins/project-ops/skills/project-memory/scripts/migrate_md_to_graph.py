"""把旧文件式 .md 记忆解析为知识图谱 {entities, relations}。仅用标准库。"""
import os
import re

# server-memory 图谱允许的 6 种 entityType（见 references/schema.md）。
ALLOWED = {"pitfall", "decision", "progress", "operation", "component", "convention"}


def parse_md_file(text: str) -> dict:
    text = text.replace("\r\n", "\n")  # 规范化 CRLF，兼容 Windows 生成的 .md
    name, mtype, body = "", "decision", text
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.DOTALL)
    if m:
        front, body = m.group(1), m.group(2)
        nm = re.search(r"^\s*name:\s*(.+?)\s*$", front, re.MULTILINE)
        if nm:
            name = nm.group(1).strip()
        tm = re.search(r"^\s*type:\s*(.+?)\s*$", front, re.MULTILINE)
        if tm:
            mtype = tm.group(1).strip()
    links = re.findall(r"\[\[([^\]]+)\]\]", body)
    return {"name": name, "type": mtype, "body": body.strip(), "links": links}


def derive_name(parsed: dict) -> str:
    """取实体名：优先 frontmatter name；为空则回退到文件名 stem。
    两者都缺 → 抛 ValueError，让调用方中止迁移而非静默合并覆盖。"""
    name = (parsed.get("name") or "").strip()
    if name:
        return name
    filename = (parsed.get("filename") or "").strip()
    if filename:
        return os.path.splitext(os.path.basename(filename))[0]
    raise ValueError("cannot migrate memory file with empty name and no filename")


def build_graph(files: list) -> dict:
    entities, relations = [], []
    for f in files:
        name = derive_name(f)
        etype = f["type"] if f["type"] in ALLOWED else "decision"
        entities.append({
            "name": name,
            "entityType": etype,
            "observations": [f["body"]],
        })
        for link in f["links"]:
            relations.append({
                "from": name,
                "to": link,
                "relationType": "relates_to",
            })
    return {"entities": entities, "relations": relations}
