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
| 完整可信MIDI | 体检、明确角色和段落，进入[音符盒编配](skills/noteblock-arranger/SKILL.md) |
| 简谱、钢琴改编或待改善MIDI | [音乐导演](skills/music-director/SKILL.md)，先识别缺失的音乐功能与参考 |
| 原曲录音/分轨 | [音乐导演](skills/music-director/SKILL.md)，先对齐和体检，再选择转写/校对路线 |

只给网址时，先取得并检查实际文件；网页描述不能作为已听到原曲、已拿到乐谱的证据。

## 建立作品并推进

```shell
python run_pipeline.py init projects/my-song --title "我的作品" --midi projects/lesson/master.mid
python run_pipeline.py brief projects/my-song --text "保留主题；中央向前跟拍；先比较人声与高潮代表段；样段和最终成品请用户听看。"
python run_pipeline.py run projects/my-song
python run_pipeline.py handoff projects/my-song
```

没有MIDI时省略`--midi`，运行器会生成音乐任务，agent按相同文件合同完成。运行器不会偷偷调用收费模型或自动创建子agent。

有音乐后，技术链条是`music → sound → machine → visuals → validate → release`；[PIPELINE](PIPELINE.md)说明现有构建命令和阶段。创作可以在这些阶段之间往返，原始母版冻结，修改产生新候选。

## 专业能力入口

| 要解决的问题 | Skill |
|---|---|
| 计划、接手、选路线、用户反馈 | [redstone-producer](skills/redstone-producer/SKILL.md) |
| 转写校对、和声、配器、曲式发展 | [music-director](skills/music-director/SKILL.md) |
| MIDI到音符盒、音色连续性、延音近似 | [noteblock-arranger](skills/noteblock-arranger/SKILL.md) |
| 采样、调音、分槽、声音包与混音 | [sound-designer](skills/sound-designer/SKILL.md) |
| 实体机器、时序、加载、相机和复位 | [redstone-engineer](skills/redstone-engineer/SKILL.md) |
| 建筑模块、轨道外形、固定光和视线 | [stage-designer](skills/stage-designer/SKILL.md) |
| 粒子动作、长音轨迹、乐句演出和字幕 | [show-director](skills/show-director/SKILL.md) |
| 验证、安装、录制与成片交付 | [verify-and-deliver](skills/verify-and-deliver/SKILL.md) |

## 环境与完成范围

Minecraft机制基线为Java1.21.1、JDK21、Fabric。游戏、账号和受保护素材由操作者提供；工具环境与合法本地资源通过显式路径接入，不使用旧项目私有目录。见[环境教程](docs/ENVIRONMENT.md)。

离线生成、服务端触发、客户端画面/声音、艺术认可与成片检查分别记录。当前可执行能力和缺项以`capabilities`及真实报告为准；研究候选与拟议能力不自动可用。

发生问题时先看[诊断路线](docs/TROUBLESHOOTING.md)，交接使用`handoff`输出和项目合同。包维护者见[维护说明](docs/MAINTAINING.md)。
