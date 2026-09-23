# 永暮之森

面向网易《我的世界》的非官方模组适配项目，包含森林维度、地图、遗迹、Boss 战斗与客户端 UI，仍处于开发阶段。

项目基于 The Twilight Forest / 暮色森林相关代码与素材进行适配，并包含烬铜盘蛇等后续模型与玩法实验。

## 获取与运行

```bash
git clone https://github.com/Nothing-cell-bit/yongmu-forest.git
cd yongmu-forest
python tools/check_runtime_packs.py --verify-snapshot
python tools/package_addon.py
```

使用 Python 3.11 运行上述检查和打包命令。生成文件为 `dist/yongmu-forest-0.12.0.mcaddon`。

仓库已包含本次发布时本地行为包和资源包的 **9,544 个运行文件**，包括 441 张 PNG、73 个 OGG、7,318 个结构文件及全部包内 JSON 配置。不使用 Git LFS；普通 `git clone` 即可取得这些文件，无须重新生成建筑、模型或音效。现成导入包见 [Releases](https://github.com/Nothing-cell-bit/yongmu-forest/releases)。

**游戏运行需要网易 MC Studio / ModSDK 开发环境及其配套客户端。** 将两个包导入同一 AddOn 项目，在新建测试世界中同时启用行为包与资源包。导入压缩包方式受所用开发工具版本影响，目录导入方式及排错见[运行说明](docs/DEVELOPMENT.md)。这不是 Java Forge/Fabric 模组，也不能用 Python 直接启动游戏逻辑。SDK 和游戏客户端由官方工具提供，不随仓库分发。

本次发布验证了文件完整性和静态资源检查，**未重新进行客户端运行时验收**。源码版本为 `0.12.0`；开发快照可能仍有 Bug，详见[状态说明](docs/STATUS.md)。

## 主要内容

- 森林维度入口、返程门、群系与植被。
- 魔法地图、迷宫地图、地标与玩家位置显示。
- 结构选址、遗迹生成、高塔及地下机关。
- 娜迦、巫妖、九头蛇、幻影骑士、暮色恶魂等战斗与进度逻辑。
- 烬铜盘蛇的模型与战斗实验。

## 仓库目录

| 路径 | 内容 |
| --- | --- |
| `TwilightBossSliceB/` | 完整行为包：运行代码、实体、物品、群系、配方、结构和包清单 |
| `TwilightBossSliceR/` | 完整资源包：模型、动画、贴图、UI、语言、声音和包清单 |
| `tools/` | 资源工具、检查器与导入包打包脚本 |
| `tests/` | 离线逻辑与资源契约测试 |
| `PACK_SNAPSHOT.json` | 本次完整运行包逐文件大小与 SHA-256 |
| `ASSET_MANIFEST.json` | 441 张图片的来源与校验值 |
| `SOURCE_SNAPSHOT.json` | 最初代码导入的历史记录 |
| `AUDIO_CREDITS.md` | 音效生成、加工来源和许可区分 |

## 开发检查

```bash
python tools/check_public_snapshot.py
python tools/check_runtime_packs.py
python tools/run_public_tests.py
```

公开逻辑入口包含 262 项标准库测试；通过这些检查不等于所有游戏功能已完成实机验证。资源生成工具可能依赖额外的源录音、上游 JAR 或预览工具，运行现成模组包不需要这些构建输入。

## 来源与许可

- 上游：[TeamTwilight / The Twilight Forest](https://github.com/TeamTwilight/twilightforest)，基线 `1.20.1-4.3.2508`，记录的源码提交 `a7dd8f13c653e137f977f5ffaa870fcb20fc1625`。
- 代码：LGPL-2.1-or-later，见 [LICENSE](LICENSE) 和 [LICENSE_CODE.md](LICENSE_CODE.md)。
- 图片及适用的美术资产：见 [IMAGE_CREDITS.md](IMAGE_CREDITS.md)、[ASSET_CREDITS.md](ASSET_CREDITS.md) 和 [ASSET_LICENSE](ASSET_LICENSE)。
- 音效包含自行合成和录音加工，分别保留原来源条件，见 [AUDIO_CREDITS.md](AUDIO_CREDITS.md)，不把所有声音统一重新授权为 CC。

本项目免费提供。各类文件分别适用其许可证；项目免费不改变上游许可。本项目不代表 TeamTwilight、Mojang、Microsoft 或网易官方。
