# 挖掘工具标签来源

`mining_tags_1_20_1.json` 保存本项目工具/采集等级查询能到达的 61 个 Java 方块标签定义。
第一层是 Mojang Minecraft 1.20.1 client JAR（SHA1 `0c3ec587af28e5a785c0b4a7b8a30f9a8f78f838`），第二层是锁定 Twilight Forest 1.20.1-4.3.2508 JAR；各层原始 JSON 以及归档 SHA256/SHA1 保留在文件内。

`tools/upstream_mining_tags.py` 校验整个来源文件 SHA256，按原版→模组顺序合并，不丢弃原版父标签；遵循 replace、required 与递归引用。它独立核对冻结合同的工具与采集等级，不把 normalizer 的结果当作来源。

实际修复、前后差异与限制见 `D:/MCmods/.task-work/twilight-bookshelf-axe-fix-20261019/REPORT.md`。更换上游版本必须重新从对应归档提取、审阅相关闭包、更新来源哈希与回归，不直接编辑来源值满足测试。
