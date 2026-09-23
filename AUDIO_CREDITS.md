# 音效来源与加工说明

资源包包含 73 个 OGG。维护者确认这些文件由本项目生成/加工；已有生成脚本进一步记录了输入来源。此处区分“生成输出”和“所有输入均为原创”。

| 目录 | 来源/处理记录 |
| --- | --- |
| `sounds/mob/naga` | 嘶声为程序合成；受伤和响尾音使用 Minecraft Java 1.20.1 末影龙、骷髅音效加工，见 `generate_original_naga_sounds.py` |
| `sounds/mob/hostile_wolf` | Minecraft Java 1.20.1 狼声加工，见 `generate_hostile_wolf_sounds.py` |
| `sounds/mob/redcap` | CC0 笑声、程序合成，以及 Minecraft 女巫/掠夺者声音加工，见 `generate_redcap_sounds.py` |
| `sounds/mob/hydra` | 本地 CC0 声音库加工；输入名称和组合见 `generate_hydra_sounds.py`，本次未独立重做其来源核验 |
| `sounds/mob/kobold` | Amada44 的两份犬吠录音，经裁切、变速、反转、滤波和包络加工；原录音 CC BY-SA 3.0，改编音效保留 CC BY-SA 3.0，不附加非商业限制 |
| `sounds/mob/deer` | Sacha.Julien 的 CC0 鹿叫录音加工 |
| `sounds/mob/raven` | CC0/公有领域鸦类录音加工 |
| `sounds/mob/tiny_bird` | CC0 鸟叫录音加工 |
| `sounds/mob/wraith` | CC0 幽灵声音加工 |

所有生成脚本均在 `tools/`。逐文件路径和输出 SHA-256 见 `PACK_SNAPSHOT.json`；已记录的录音来源、作者、许可与输入哈希见下表及对应 JSON。本次只发布运行所需的加工输出与来源记录，没有打包整套游戏音频或原始录音库。

程序合成与本项目对 CC0 输入所作的原创贡献按 CC BY-NC-SA 4.0 提供；不改变 CC0 原始素材本身的自由使用条件。Kobold 录音改编遵循 CC BY-SA 3.0。Minecraft 原版声音及其加工结果的底层权利仍属于 Mojang / Microsoft，本仓库不为这些内容授予 CC 许可或独立音效库再分发授权。游戏相关条款见 https://www.minecraft.net/eula 。

CC BY-SA 3.0 许可：https://creativecommons.org/licenses/by-sa/3.0/
CC0 声明：https://creativecommons.org/publicdomain/zero/1.0/

## 已有源录音记录

以下记录来自本项目的素材来源文件；部分为候选输入，并不表示每份都进入最终音效。实际使用由各生成脚本的固定文件名/哈希确定。

| 作品 | 作者 | 原许可 | 来源记录 |
| --- | --- | --- | --- |
| [Roe Deer calls Forest of Saou](https://freesound.org/people/Sacha.Julien/sounds/724578/) | Sacha.Julien | CC0-1.0 | [JSON](tools/audio_sources/deer/roe_deer_calls_forest_of_saou_724578_hq.source.json) |
| [Barking of a dog](https://commons.wikimedia.org/wiki/File:Barking_of_a_dog.ogg) | Amada44 | CC BY-SA 3.0 | [JSON](tools/audio_sources/kobold/barking_of_a_dog.source.json) |
| [Barking of a dog 2](https://commons.wikimedia.org/wiki/File:Barking_of_a_dog_2.ogg) | Amada44 | CC BY-SA 3.0 | [JSON](tools/audio_sources/kobold/barking_of_a_dog_2.source.json) |
| [Crow caw](https://opengameart.org/content/crow-caw) | zeroisnotnull | CC0 | [JSON](tools/audio_sources/raven/public_domain/cc0_crow_caw.source.json) |
| [Common Raven Grand Teton National Park](https://commons.wikimedia.org/wiki/File:Common_Raven_Grand_Teton_National_Park.ogg) | Public domain source as marked by Wikimedia Commons | Public domain | [JSON](tools/audio_sources/raven/public_domain/common_raven_grand_teton.source.json) |
| [Corvus cornix](https://commons.wikimedia.org/wiki/File:Corvus_cornix.ogg) | Public domain source as marked by Wikimedia Commons | Public domain | [JSON](tools/audio_sources/raven/public_domain/public_domain_hooded_crow.source.json) |
| [Yellowstone sound library - Common Raven - 001](https://commons.wikimedia.org/wiki/File:Yellowstone_sound_library_-_Common_Raven_-_001.mp3) | Public domain source as marked by Wikimedia Commons | Public domain | [JSON](tools/audio_sources/raven/public_domain/yellowstone_common_raven_001.source.json) |
| [Evil Cackle Laugh 2](https://opengameart.org/content/evil-cackle-laugh-2) | Nocturnal_Vanguard | CC0 | [JSON](tools/audio_sources/redcap/cc0_laughter/evil_cackle_laugh_2.source.json) |
| [Evil Laugh 2](https://opengameart.org/content/evil-laugh-2) | Sickmind33 | CC0 | [JSON](tools/audio_sources/redcap/cc0_laughter/evil_laugh_2.source.json) |
| [evil laughter](https://opengameart.org/content/evil-laughter-0) | Venn Stone (VennStone) | CC0 | [JSON](tools/audio_sources/redcap/cc0_laughter/evil_laughter_0.source.json) |
| [Group Giggling](https://opengameart.org/content/group-giggling) | Nocturnal_Vanguard | CC0 | [JSON](tools/audio_sources/redcap/cc0_laughter/group_giggling.source.json) |
| [Witch Cackle](https://opengameart.org/content/witch-cackle) | AntumDeluge | CC0 | [JSON](tools/audio_sources/redcap/cc0_laughter/witch_cackle.source.json) |
| [Sinister Laugh](https://opengameart.org/content/sinister-laugh) | WeaponGuy | CC0 | [JSON](tools/audio_sources/redcap/sinister_laugh.source.json) |
| [20191014 102654 phylloscopus thiru](https://commons.wikimedia.org/wiki/File:20191014_102654_phylloscopus_thiru.ogg) | Wikimedia Commons contributor | CC0 | [JSON](tools/audio_sources/tiny_bird/cc0_birds/phylloscopus_thiru.source.json) |
| [Bird call with so-called separated chirps](https://commons.wikimedia.org/wiki/File:Bird_call_with_so-called_separated_chirps.ogg) | Wikimedia Commons contributor | CC0 | [JSON](tools/audio_sources/tiny_bird/cc0_birds/separated_chirps.source.json) |
| [4 Atmospheric ghostly loops](https://opengameart.org/content/4-atmospheric-ghostly-loops) | Independent.nu | CC0 | [JSON](tools/audio_sources/wraith/cc0_ghosts/cc0_atmospheric_ghostly_loops.source.json) |
| [Ghost breath](https://opengameart.org/content/ghost-breath) | qubodup | CC0 | [JSON](tools/audio_sources/wraith/cc0_ghosts/cc0_ghost_breath.source.json) |
| [Ghost Monster Voice Moaning & Growling](https://opengameart.org/content/ghost-monster-voice-moaning-growling) | qubodup | CC0 | [JSON](tools/audio_sources/wraith/cc0_ghosts/cc0_ghost_moan_growl.source.json) |
| [Ghostly Humming](https://opengameart.org/content/ghostly-humming) | Nocturnal_Vanguard | CC0 | [JSON](tools/audio_sources/wraith/cc0_ghosts/cc0_ghostly_humming.source.json) |
