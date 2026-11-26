# 从这里开始制作红石音乐

这是一套供agent使用的制作工作包：专业方法、工具、项目合同与证据一起工作。先读取用户需求，保留创作判断；不要把生成ZIP或测试成功当成作品已经好听、好看。

## 新agent的第一轮

在仓库根目录，先确认可运行的Python3.12与Node24。首次使用创建独立环境并安装：

```shell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[production]"
```

上述是Windows路径；Linux使用`.venv/bin/python`。下面的`python`均指该独立环境的解释器；也可始终用完整解释器路径，不需要修改全局PATH。然后执行：

```shell
python run_pipeline.py capabilities --probe
python run_pipeline.py learn projects/lesson
```

第一条检查本机实际能力，缺项有安装或替代路线；第二条在新的独立目录生成原创学习素材。学习目录若已存在，按命令帮助选择新目录，不删除旧成果。

先读[主控Skill](skills/redstone-producer/SKILL.md)和[工作流](docs/WORKFLOW.md)。按当前问题再读一个专业Skill，不需要加载全部教程。模型无法直接听音频时，生成真实试听文件，安排用户样段与成品听审。

## 三种起点

| 用户有什么 | 从哪开始 |
|---|---|
| 原曲录音、分轨或待改善的转写 | [从混音校出可信母版](docs/MIX_TO_MIDI.md)，先校一个能暴露问题的乐句 |
| 有谱面、简谱或局部 MIDI | [用谱面、短 MIDI 和录音重建母版](docs/SCORE_FROM_REFERENCES.md)，先列版本与素材覆盖范围 |
| 完整可信 MIDI | [制作独立游戏演奏谱](docs/PERFORMANCE_AND_TRACK.md#1-先做一段游戏编曲)。先对照母版、改编报告与游戏采样试听 |
| 已试听的 Minecraft 演奏谱与声音包 | [从乐句到轨道、建筑与稳镜头](docs/PHRASE_TO_WORLD.md)。用触发谱、声音 profile 与资源包设计代表段 |

只给网址时，先取得并检查实际文件；网页描述不能作为已听到原曲、已拿到乐谱的证据。

接手只有 MP3 的作品时，运行 `init PROJECT --reference-audio SOURCE.mp3`，按[本机音频后端](integrations/transcription/README.md)先制作代表段。按录音的有效时间轴比原曲与重建，经校正后再准备全曲音乐任务交付。可信旋律和缺失伴奏可从 `composition study` 学习冻结主题与变换织体。进入音符盒制作用 `timbre-study` 练习同谱异音色和长音策略。

要试轻薄底色、句尾回声和拍缝颗粒，可以运行 `python run_pipeline.py texture-study projects/texture`。[原创练习](examples/texture-study/README.md)含两种可构建的样段和同增益试听。现有能力与待补足部分见[模块状态](docs/IMPLEMENTATION_STATUS.md)。

## 建立作品并推进

```shell
python run_pipeline.py init projects/my-song --title "我的作品" --midi projects/lesson/master.mid
python run_pipeline.py brief projects/my-song --text "保留主题；中央向前跟拍；先比较人声与高潮代表段；样段和最终成品请用户听看。"
python run_pipeline.py run projects/my-song
python run_pipeline.py handoff projects/my-song
```

没有MIDI时省略`--midi`，运行器会生成音乐任务，agent按相同文件合同完成。运行器不会偷偷调用收费模型或自动创建子agent。

有音乐后，技术链条是`music → sound → machine → visuals → validate → release`；[PIPELINE](PIPELINE.md)说明现有构建命令和阶段。创作可以在这些阶段之间往返，原始母版冻结，修改产生新候选。

有可信 MIDI 但仍需为 Minecraft 改配器时，先做[演奏谱与随谱轨道](docs/PERFORMANCE_AND_TRACK.md)。新工程会按乐句分配实体支路。想精细设计时，写出自己的段落、主读位置与造型决定，再新建游戏候选。

## 专业能力入口

| 要解决的问题 | Skill |
|---|---|
| 计划、接手、选路线、用户反馈 | [redstone-producer](skills/redstone-producer/SKILL.md) |
| 转写校对、和声、配器、曲式发展 | [music-director](skills/music-director/SKILL.md) |
| MIDI到音符盒、音色连续性、延音近似 | [noteblock-arranger](skills/noteblock-arranger/SKILL.md) |
| 采样、调音、分槽、声音包与混音 | [sound-designer](skills/sound-designer/SKILL.md) |
| 实体机器、时序、加载、相机和复位 | [redstone-engineer](skills/redstone-engineer/SKILL.md) |
| 建筑与街区、轨道外形、视线 | [Minecraft 建筑模块](docs/MINECRAFT_ARCHITECTURE.md)、[stage-designer](skills/stage-designer/SKILL.md)与[场景收尾及 Nevada 材质光影](docs/SCENE_FINISH_AND_LOOK.md) |
| 粒子动作、长音轨迹、乐句演出和字幕 | [原版轨道粒子教程](docs/VANILLA_RAIL_PARTICLES.md)与 [show-director](skills/show-director/SKILL.md) |
| 验证、安装、录制与成片交付 | [verify-and-deliver](skills/verify-and-deliver/SKILL.md) |

## 环境与完成范围

实体红石、声音包和跟拍支持 Minecraft Java 1.21.1 原版，运行使用 JDK 21。Fabric 用于可选客户端效果。游戏、账号和受保护素材由操作者提供，工具环境与本地资源通过实际路径接入。见[环境教程](docs/ENVIRONMENT.md)。

离线生成、服务端触发、客户端画面/声音、艺术认可与成片检查分别记录。当前可执行能力和缺项以`capabilities`及真实报告为准；研究候选与拟议能力不自动可用。

发生问题时先看[诊断路线](docs/TROUBLESHOOTING.md)，交接使用`handoff`输出和项目合同。包维护者见[维护说明](docs/MAINTAINING.md)。

听感或观看有问题时，从[制作判断与复查](docs/PRODUCTION_DECISIONS.md)选一种修法。每轮代表段用[制作与复查记录](templates/sample-review.md)保存依据、候选与反馈。
