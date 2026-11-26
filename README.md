# Redstone Music Production Kit

供新 agent 冷启动的 Minecraft 红石音乐制作工作包：8 个专业 Skill、实操教程、可执行工具、项目合同、原创练习与证据交接。中文从 [START_HERE](START_HERE.md) 开始；设计和取舍见[改写方案](docs/REWRITE_PLAN.md)。

`0.4.0a1` 开发预览加入独立 Minecraft 演奏谱、逐音改编记录与按乐句布置的实体轨道。新 agent 从 [START_HERE](START_HERE.md) 开始。各模块的完成度、实测范围与短板见[实施与验证](docs/IMPLEMENTATION_STATUS.md)。

## 安装与开始

基线使用 Python 3.12、Node 24，专业音乐功能另需 FFmpeg。实体演奏与可玩世界使用 Minecraft Java 1.21.1 / JDK 21。Fabric 用于可选的客户端粒子和字幕。离线制作可以在未安装游戏的环境运行。

```shell
python -m venv .venv
# Windows；Linux 使用 .venv/bin/python
.venv\Scripts\python.exe -m pip install -e ".[production,pitch]"
.venv\Scripts\python.exe run_pipeline.py capabilities --probe
.venv\Scripts\python.exe run_pipeline.py bundle-check
.venv\Scripts\python.exe run_pipeline.py learn projects/lesson
```

有 MIDI 后按 START_HERE 建独立项目。没有 MIDI 时运行器生成音乐任务，由 agent 按合同创作和导入。用户默认只在代表样段与最终成品时听看；主 agent 自主推进、记录理由，遇到具体问题再读对应专业 Skill。

## 包里的能力

| 环节 | 具体工具与能力 |
|---|---|
| 音乐 | Mido 保留母版与局部编辑；music21 乐理候选；librosa 音频测量；可选 SwiftF0 单旋律候选 |
| 音符盒与声音 | 按乐句显式适配、音色分槽/根音/延音策略、原创采样资源包、频谱校准、参考/GM/采样试听与等响 A/B |
| 轻声部织体 | 原创 `texture-study` 生成同谱基线、增加底色/回声/颗粒的样段、同增益试听及两个可独立构建的项目 |
| 实体机器 | 偶/奇双线路、复音、受限声部位置/相机参数、保护区建筑合入、Anvil/Litematica 独立回读 |
| 建筑与演出 | 固定提交 mcbuild 体素核心、原创几何四视图、节点/环/螺旋/曲线 show score、标准 Fabric 客户端源码 |
| 制作管理 | 8 角色文件任务、不可变产物/失效重建、决策、绑定文件哈希的反馈、当前交接、媒体检查与源码包导出 |

Skill 按需加载；工具不会秘密调用模型、创建子 agent 或消耗 API。支持单 agent 顺序工作，也可由宿主按文件合同分工。能读写文件、运行 CLI、编程、检查结果并管理上下文的 agent 可使用；听觉/视觉能力或实际用户反馈决定艺术验收能力。

## 运行与交付

确定性构建为 `music → sound → machine → visuals → validate → release`。生成候选后，修改受影响输入只重建相关阶段；旧产物保留。`handoff PROJECT` 为新 agent 导出事实状态，避免依赖旧聊天。

```shell
python run_pipeline.py demo
python run_pipeline.py --help
python run_pipeline.py bundle-export outputs/source-kit
```

Git checkout 和 Python wheel 都包含 Skill、schema、教程与客户端源码。wheel 安装后使用 `python -m redstone_music`，`bundle-export` 可导出可读的工作包。GM 模式需要另行提供许可明确的 SoundFont；游戏文件、账号、商用歌曲、材质和光影不随源码分发。Photon 目前是检查与同段对比准备接口，不是已实现的 show 导入后端。

详见[工作流](docs/WORKFLOW.md)、[环境](docs/ENVIRONMENT.md)、[故障诊断](docs/TROUBLESHOOTING.md)、[CLI 和合同](PIPELINE.md)、[第三方来源](THIRD_PARTY.md)。

An agent-neutral production kit for Minecraft note-block performances. The package carries professional methods and tools for a fresh agent to reason, create, revise and hand off a performance. Static exports, actual game replay, artistic approval and finished recordings remain separate evidence levels.
