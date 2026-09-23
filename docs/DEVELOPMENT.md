# 开发与运行

## 可以立即运行的部分

使用 Python 3.11：

```bash
python tools/run_public_tests.py
```

公开测试入口仅依赖标准库，运行明确列出的离线逻辑测试。它不会启动 Minecraft、MC Studio、资源生成器或包部署工具。

## SDK 适配代码

`modMain.py`、`serverSystem.py`、`clientSystem.py`、UI 类及相关服务通过网易 `server.extraServerApi`、`client.extraClientApi` 和 `common.mod` 接口运行。SDK 不随本仓库分发，需要由开发者从合法渠道配置。

部分适配层保留 Python 2 语法，例如 `print` 语句；这是当前开发代码的运行环境特征，不应直接拿 Python 3 的全目录 compileall 结果当作适配层可运行性结论。纯逻辑模块与公开测试在 Python 3.11 下检查。

## 可选工具依赖

```bash
python -m pip install -r requirements-tools.txt
python -m pip install -r requirements-dev.txt
```

`requirements-tools.txt` 中 Pillow / NumPy 用于部分资源生成和预览脚本。`requirements-dev.txt` 中 pytest 供原有 pytest 风格测试使用。这些包不是运行公开标准库测试入口的前提。

## 缺少哪些输入

本仓库没有 `TwilightBossSliceR` 游戏资源、行为包 JSON 定义/清单、结构二进制、上游 JAR、模型验收记录和网易 SDK。原有资源契约测试可能会因此失败；不建议直接把所有测试发现命令当作本代码快照的验收入口。

资源工具保留作实现参考，多数不能在当前快照里直接完成构建。接力者需要分别取得输入素材的分发/使用依据，恢复包配置和资源引用，再在隔离世界中进行真实客户端验证。仅补齐文件名不会解决许可或行为正确性问题。

`tools/sync_packs.py` 等工具会写入指定目标。当前仓库不提供部署目标配置，不应对原有个人世界执行未经核对的写入。
