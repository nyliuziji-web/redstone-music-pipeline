# Minecraft领域技能与学习计划

2026-11-17研究。本文记录尚待实现、学习与验证的专业能力，不是已安装Skill或模组清单。当前仍以Java1.21.1、实体红石发声为基线。

本研究已纳入[正式改写方案](REWRITE_PLAN.md)，具体集成决定与实施顺序以该方案为准。

## 为什么还需要专业适配

好的MIDI进入音符盒后，仍需重新选择音色、分配有限槽位、处理音区和延音、适应空间衰减。当前声音阶段的角色偏好/音域回退、固定补触发和ZIP检查是可运行基线，尚未做到乐句级配器与样本校准。

建议把原始MIDI与音符盒编配分开。适配输出应说明音色变换、移调、持续策略、近似损失与实际试听；技术正确、听感改善分别验收。

## 可研究的现成Skill和工具

| 来源 | 用处 | 接入边界 |
|---|---|---|
| [Minecraft Agent Skills](https://github.com/Jahrome907/minecraft-agent-skills) | MIT的modding、resource-pack、datapack、commands和testing等技能 | 选取需要的技能，按1.21.1核对；其最新26.x示例不构成本项目迁移要求 |
| [Modding Workbench](https://github.com/adhi-jp/agent-skills/blob/main/skills/minecraft-modding-workbench/SKILL.md)与[Minecraft Modding MCP](https://github.com/adhi-jp/minecraft-modding-mcp) | 版本源码、映射、模组JAR与Mixin检查 | MCP为MIT、通用stdio；Node≥22.13。源码检查不能替代构建/实机；NBT载荷工具不是MCA区域文件编辑器 |
| [NoteBlockLib](https://github.com/RaphiMC/NoteBlockLib) / [NoteBlockTool](https://github.com/RaphiMC/NoteBlockTool) | MIDI/NBS转换、移调、重采样、乐器替换及试听对照 | 库为LGPL-3.0；不默认重采样至10TPS，本项目已有1GT分辨率。前端通常不保留编辑后的NBS层，需对比来源 |
| [Audio2Minecraft](https://tremblestarman.github.io/Audio2Minecraft/) | 20t/s转换、声音包与参数资料 | 其playsound命令流不等于实体红石触发；适合学习方法，不能直接替代本项目机器 |
| [NoteBetter](https://github.com/chsbuffer/NoteBetter) / [Infinote](https://github.com/RS-256/infinote) | 基底方块→自定义声音的可配置映射 | 核实具体JAR、源码和版本。Infinote为MIT Fabric候选，扩展音高可能需要客户端配合；两者均不能自动提供专业采样或完整note-off |

以上只完成资料核查，未安装新工具或证明兼容。

## ColorBlock与视觉能力

用户偏好ColorBlock类演出效果，后续样段以其创作语言作为学习与比较目标。[OCEAN教程](https://www.bilibili.com/video/BV1984y1s79M/)和[生成器](https://mc.ecylt.top/pages/creation/index.html)提供函数轨迹、旋转与颜色变化的实际先例；已有作品还体现了线框节点、圆环和多尺度空间。模组、贴图、光影、场景与作者编排共同决定效果，换后端需要同段/同机位比较。

| 后端候选 | 特点 | 当前版本/分发边界 |
|---|---|---|
| ColorBlock / AnotherColorBlock | 数学表达式和命令创作，贴近红石音乐作者实践 | 未核实可直接用于1.21.1 Fabric的可靠发行及统一许可；勿与同名染色方块项目混淆 |
| [ExParticle](https://modrinth.com/mod/exparticle) | 参数/时间/RGBA表达式、分组、图片/视频 | 发行页为1.21.1 NeoForge、LGPL-3.0；并非当前Fabric的直接安装项 |
| [Photon 2](https://github.com/Low-Drag-MC/Photon) | 编辑器、曲线、拖尾、光束与时间轴；[中文教程](https://low-drag-mc.github.io/LowDragMC-Doc/zh/photon2/getting-started.html) | 新版与旧Fabric移植分开；[许可](https://github.com/Low-Drag-MC/Photon/blob/1.21/LICENSE)对模组代码/资源与创作内容有不同规定，勿统一当MIT |
| [Photon Editor Fabric](https://modrinth.com/mod/photon-editor-fabric) | 非官方1.21.1 Fabric移植 | 不据移植名称假定拥有Photon 2全部功能；旧样段运行记录不证明新时间轴和工程格式兼容 |

演出数据应描述音乐作用、效果名、锚点、坐标变换、曲线、寿命、颜色、种子和清理方式，再交给后端。各后端明确能力范围。节点、长音轨迹、乐句大动作分层编排；保留主读、前后景与段落留白。停止重开、回放时间、帧时、光影和录制均需实测。

## 应形成的四项项目技能

| 技能 | 核心方法 | 必备练习与证据 |
|---|---|---|
| 音符盒编配 | 按角色/乐句选音色，保留旋律走向；长音策略依据样本，记录近似损失 | 同一原创乐句做原版与专用采样方案，独奏/混合/实际游戏比较 |
| 资源包音色设计 | 选音或合成、中心音校准、包络、分槽、相对音量和叠加余量 | 拨弦/持续/打击各一例，低中高音及共享槽冲突检查，声音包与录音hash |
| 粒子导演 | 参数运动、颜色/尺寸曲线、材质、世界/局部空间与乐句发展 | 节点/长音/跨轨动作各一例，同段同机位录制、性能和清理记录 |
| 模组工程验证 | 固定游戏/Loader/API/映射，源码查证、构建、客户端与服务器分工 | 一个真实映射诊断、最小效果构建、资源加载及中止重播验证 |

声音文件、声音事件、基底与方块note建立同一profile。[Fabric声音文档](https://docs.fabricmc.net/1.21.1/develop/sounds/custom)是格式依据；定位音效采用正确的单声道OGG Vorbis。变速播放同时改变音高和样本长度；MIDI踏板、velocity和note-off不是音符盒原生行为。更换资源包中心音后，以实际频率和声音验证，不只比服务器note数字。

最终每项技能应包含教程、通用工具入口、原创成功样例、故意失败样例、证据与回退路线。CLI/JSON为能力接口，宿主Skill/MCP为可选包装；专业能力不依赖某一家agent。先完成短样段学习与对照，再扩全曲。
