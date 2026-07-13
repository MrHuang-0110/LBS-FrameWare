"""开场路径自愈：核对 .mcp.json 的 MEMORY_FILE_PATH 是否指向当前项目。

server-memory 只认绝对路径；相对路径或未展开的 ${CLAUDE_PROJECT_DIR} 会被拼到
npm 包目录，导致读不到项目记忆。本脚本在每次会话开场检查并（可选）修正。

用法：
  python check_memory_path.py <当前项目绝对路径> [--fix <.mcp.json 路径>]
无 --fix 时只报告是否需要修正（退出码 0=一致，1=需修正）。
"""
import json
import os
import sys


def _norm(p: str) -> str:
    """统一为小写正斜杠，用于路径等价比较（Windows 大小写/斜杠不敏感）。"""
    return p.replace("\\", "/").rstrip("/").lower()


def expected_path(project_dir: str) -> str:
    """当前项目应有的记忆文件绝对路径（正斜杠形式）。"""
    return project_dir.replace("\\", "/").rstrip("/") + "/.memory/memory.jsonl"


def needs_fix(current: str, project_dir: str) -> bool:
    """current（.mcp.json 里现有值）是否需要改写为当前项目绝对路径。"""
    if not os.path.isabs(current.replace("\\", "/")):
        return True  # 相对路径或未展开变量（${...} 非绝对）
    return _norm(current) != _norm(expected_path(project_dir))


def fix_mcp_json(mcp_path: str, project_dir: str) -> bool:
    """把 .mcp.json 的 memory.MEMORY_FILE_PATH 改为当前项目绝对路径。返回是否改动。"""
    with open(mcp_path, encoding="utf-8") as f:
        cfg = json.load(f)
    env = cfg["mcpServers"]["memory"].setdefault("env", {})
    want = expected_path(project_dir)
    if env.get("MEMORY_FILE_PATH") == want:
        return False
    env["MEMORY_FILE_PATH"] = want
    with open(mcp_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return True


if __name__ == "__main__":
    project_dir = sys.argv[1]
    if "--fix" in sys.argv:
        mcp_path = sys.argv[sys.argv.index("--fix") + 1]
        changed = fix_mcp_json(mcp_path, project_dir)
        print("FIXED" if changed else "ALREADY-OK")
    else:
        mcp_path = os.path.join(project_dir, ".mcp.json")
        try:
            cur = json.load(open(mcp_path, encoding="utf-8"))[
                "mcpServers"]["memory"]["env"]["MEMORY_FILE_PATH"]
        except (OSError, KeyError, json.JSONDecodeError):
            print("NEEDS-FIX (no valid MEMORY_FILE_PATH)")
            sys.exit(1)
        if needs_fix(cur, project_dir):
            print(f"NEEDS-FIX (current={cur}, expected={expected_path(project_dir)})")
            sys.exit(1)
        print("OK")
