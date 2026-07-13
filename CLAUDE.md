<!-- project-memory:start -->
会话开始时：先核对 .mcp.json 的 MEMORY_FILE_PATH 指向本项目 .memory/memory.jsonl（用 project-memory skill 的 check_memory_path.py，不一致则 --fix 修正并提示重启）；然后重建并读取 .memory/index.md 这份轻量索引（名字/类型/摘要），据此了解本项目有哪些记忆，**不开场全量 read_graph**。对话中需要某条记忆正文时，再用 open_nodes/search_nodes 按需读取。若因 MCP 服务/包缺失失败，按 project-memory skill 的 setup Step 0 自愈安装后重试。
<!-- project-memory:end -->
