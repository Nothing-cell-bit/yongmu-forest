# 永暮之森

面向网易《我的世界》的非官方模组适配项目，包含森林维度、地图、遗迹、Boss 战斗与客户端 UI 等内容的开发代码及图片资源。

项目基于 The Twilight Forest / 暮色森林的相关代码与素材进行适配，同时包含后续模型与玩法实验。当前仍处于开发阶段。

## 主要内容

- **森林探索**：维度入口、返程门、群系与植被相关逻辑。
- **地图系统**：魔法地图、迷宫地图、地标与玩家位置显示。
- **遗迹与机关**：结构选址、生成调度、高塔及地下遗迹相关逻辑。
- **Boss 战斗**：娜迦、巫妖、九头蛇、幻影骑士、暮色恶魂等行为与进度逻辑。
- **开发工具**：资源转换、图片生成、模型预览与离线测试。

## 仓库目录

| 路径 | 内容 |
| --- | --- |
| `TwilightBossSliceB/TwilightBossSlice/` | Python 运行逻辑与 SDK 适配代码 |
| `TwilightBossSliceR/textures/` | 439 张已记录来源的贴图、物品图标与 UI 图片 |
| `tools/` | 构建、检查、转换和预览工具 |
| `tests/` | 逻辑测试与资源契约测试 |
| `docs/` | 开发说明、当前状态与检查记录 |
| `SOURCE_SNAPSHOT.json` | 初次代码导入记录及文件校验值 |
| `ASSET_MANIFEST.json` | 图片来源、改动说明、许可与文件校验值 |

当前仓库收录代码与部分图片资源，尚未包含完整的包定义、模型、动画、声音、结构文件和网易 SDK。下载源码后不能直接作为完整模组导入游戏。

## 开发与测试

使用 Python **3.11** 运行不依赖游戏资源的公开逻辑测试：

```bash
git clone https://github.com/Nothing-cell-bit/yongmu-forest.git
cd yongmu-forest
python tools/run_public_tests.py
```

该入口使用 Python 标准库，目前包含 262 项测试。完整客户端运行与其他资源测试需要额外配置 SDK 和相应资源，详见[开发说明](docs/DEVELOPMENT.md)。

部分网易 SDK 适配代码保留 Python 2 风格语法，不能直接用本机 Python 3 启动。当前源码版本字段为 `0.12.0`，详细开发状态见[状态说明](docs/STATUS.md)。

## 来源与许可

- 上游项目：[TeamTwilight / The Twilight Forest](https://github.com/TeamTwilight/twilightforest)。
- 开发基线：`1.20.1-4.3.2508`，记录的源码提交为 `a7dd8f13c653e137f977f5ffaa870fcb20fc1625`。
- **代码**：LGPL-2.1-or-later，见 [LICENSE](LICENSE) 与 [LICENSE_CODE.md](LICENSE_CODE.md)。
- **本次发布的图片**：CC BY-NC-SA 4.0，需遵守署名、非商业性使用和相同方式共享等条件；见[图片许可与署名](IMAGE_CREDITS.md)、[许可全文](ASSET_LICENSE)及[逐文件记录](ASSET_MANIFEST.json)。

代码和图片适用不同许可证。图片许可不覆盖未发布的模型、声音、SDK、商标或其他第三方内容。

本项目为非官方开发项目，不代表 TeamTwilight、Mojang、Microsoft 或网易官方。
