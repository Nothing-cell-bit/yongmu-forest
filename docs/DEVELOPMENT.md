# 开发与运行

## 环境

- Git：拉取完整仓库，不使用 LFS 或子模块。
- Python 3.11：仅供离线检查、测试与打包；这些入口仅需标准库。
- 网易 MC Studio、ModSDK 及配套游戏客户端：通过官方开发工具安装。游戏脚本使用 `server.extraServerApi`、`client.extraClientApi`、`common.mod` 接口；普通国际基岩版或 Java 版不会提供这些接口。
- 包内清单声明最低引擎版本 `1.21.0`。实际兼容性以所用网易客户端与 ModSDK 为准，本次没有验证所有版本。

## 从源码取得运行包

```bash
git clone https://github.com/Nothing-cell-bit/yongmu-forest.git
cd yongmu-forest
python tools/check_runtime_packs.py --verify-snapshot
python tools/package_addon.py
```

最后一步只压缩现有文件，不运行任何生成器、不写入 MC Studio 或已有存档。输出路径默认是 `dist/yongmu-forest-0.12.0.mcaddon`；若已存在，请通过 `--output` 指定新文件名。旁边的 `.sha256` 文件供下载后校验。

也可从 GitHub Releases 下载现成包。平台不接受 `.mcaddon` 时，可将其作为 ZIP 解压，取得下列两个目录：

```text
TwilightBossSliceB/manifest.json
TwilightBossSliceR/manifest.json
```

## 网易开发环境内运行

1. 在 MC Studio 中创建用于测试的 AddOn 项目，使用当前安装的配套 ModSDK 和客户端。
2. 按该版本开发工具的本地 AddOn 导入流程，导入压缩包；若只支持目录导入，则分别导入上面两个完整目录。每个包的 `manifest.json` 必须处于包根目录，不能多套一层仓库文件夹。
3. 在同一新建测试世界中同时启用行为包和资源包。保留原 UUID 和版本依赖，不要只复制 Python 或 textures 子目录。
4. 通过开发工具启动测试客户端；观察启动日志、物品资源及 Boss/UI 加载情况。不要把离线 Python 测试当作客户端启动测试。

行为包 UUID：`8b8df0d2-33a4-4b23-b1d4-2fe84c4b7a11`。
资源包 UUID：`cf9ac2fa-4bca-4cc9-8a78-92d62579e9d4`。
两包版本均为 `0.12.0`，行为包已声明对资源包的依赖。

首次建议用新世界测试。存档、账户、游戏安装、个人路径、调试日志和 SDK 未随源码公开。本次发布没有对下载后的安装流程做新的实机验收；遇到问题请附客户端/SDK 版本、复现步骤和去除私人信息后的日志。

## 开发与检查

```bash
python tools/check_public_snapshot.py
python tools/check_runtime_packs.py
python tools/run_public_tests.py
```

`--verify-snapshot` 用于核对原始发布快照；修改资源后可不加该选项运行资源检查，并在正式发布时更新快照清单。

部分 SDK 适配代码保留 Python 2 风格语法，不能使用 Python 3 全目录 compileall 判定其运行状态。公开逻辑测试用 Python 3.11；游戏适配代码交由网易运行环境加载。

可选工具依赖：`python -m pip install -r requirements-tools.txt`；开发测试依赖：`python -m pip install -r requirements-dev.txt`。源录音、上游 JAR、离线模型验收输入并未全部打包；需要重新生成资产时，请阅读相应工具参数及来源记录。预生成的运行包已经包含全部现有运行资源。

`tools/sync_packs.py` 是原项目的部署工具，带有本机部署检查和运行时验收要求，不是新用户的快速启动入口。不要伪造验收记录或直接向已有个人世界运行该工具。
