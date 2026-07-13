"""把项目绝对路径编码为 ~/.claude/projects 下的目录名。"""


def encode_project_path(abs_path: str) -> str:
    result = []
    for ch in abs_path:
        result.append("-" if ch in (":", "\\", "/") else ch)
    return "".join(result)


if __name__ == "__main__":
    import sys
    print(encode_project_path(sys.argv[1]))
