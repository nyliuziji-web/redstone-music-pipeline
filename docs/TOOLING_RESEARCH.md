# 专业工具研究与集成顺序

研究日期：2026-11-17。本文是后续开发决策，**不是已实现功能清单**。v0.1当前能力以[生产说明](../PIPELINE.md)和[验证记录](../PIPELINE_VERIFICATION.md)为准。

后续已形成[正式改写方案](REWRITE_PLAN.md)及[Nevada复盘](NEVADA_RETROSPECTIVE.md)。工具的采用/可选/暂缓以正式方案为准，本页保留研究过程。

Minecraft专门能力的后续研究见[领域技能与学习计划](MINECRAFT_DOMAIN_SKILLS.md)，涵盖ColorBlock类演出、音符盒编配、资源包音色和模组工程。

## 目标

让agent通过专业工具分析、编辑、渲染、比较和修订音乐与建筑。保留现有CLI、JSON任务和可恢复产物；宿主可以替换，不依赖Codex专用工具、子agent API或某家模型。

当前核心能够导入MIDI并构建实体机器，但专业编曲、通用试听和建筑预览仍有缺口。首要补足创作反馈，随后比较生成模型。

## 第一批：音乐分析与试听

| 工具 | 拟接入用途 | 边界 |
|---|---|---|
| [music21](https://github.com/cuthbertLab/music21) | 调性/和声候选、音域和声部分析 | BSD-3-Clause；开发分支Python≥3.12，需核实与核心Python3.11基线的版本兼容。先只读分析，不默认往返导出覆盖原始MIDI |
| [TinySoundFont Python](https://pypi.org/project/tinysoundfont/0.3.7/) | 全曲、独奏与分组GM试听 | MIT引擎，SoundFont单独提供与记录；GM效果不代表音符盒效果 |
| [librosa](https://github.com/librosa/librosa) | 音频能量、chroma、节奏候选 | ISC；指标辅助定位问题，不充当审美评分 |
| [FFmpeg](https://ffmpeg.org/ffmpeg-filters.html) | 片段提取、LUFS/true-peak、响度匹配和成片检测 | 外部程序，记录具体构建与许可；不随MIT源码包直接混发 |
| [SwiftF0](https://github.com/lars76/swift-f0) | 单旋律/可信分轨F0依据 | MIT；不能从主导音高推成混音多轨转写 |
| [Basic Pitch](https://github.com/spotify/basic-pitch) | 单乐器复音MIDI候选 | Apache-2.0；作者README的Python范围与本地既有环境不同，需干净安装验收；转写不等于编曲 |

[FluidSynth](https://github.com/FluidSynth/fluidsynth)可作为SoundFont渲染替代后端，无需同时强制安装两个合成器。[nbswave](https://github.com/OpenNBS/nbswave)是MIT的音符盒试听候选，但需验证NBS映射不会丢失当前1GT事件和来源；游戏空间声音仍应实机验证。

预期闭环：结构化分析→指定声部/小节编辑→GM与音符盒双预览→同段A/B→局部修订。精确编辑保留冻结内容、tempo map、CC64和来源ID。理论规则产生建议，不能把调外音、平行运动等一律判错。

## 第二批：建筑模块与预览

| 工具 | 拟接入用途 | 边界 |
|---|---|---|
| [mcbuild](https://github.com/harrynull/mcbuild) | 离线蓝图、体素模块、CPU多视角预览和局部修改 | MIT代码；不引入其OpenRouter主控或NeoForge实时模组。附带Minecraft资源另有[说明](https://github.com/harrynull/mcbuild/blob/main/src/mcbuild/assets/NOTICE.md)，不能统一按MIT分发 |
| [Lodestone](https://github.com/mattzh72/lodestone) | 读取现有litematic的浏览器预览 | MIT；依赖WebGL，默认首个region，无内置截图API、红石或真实光照传播。按[限制文档](https://github.com/mattzh72/lodestone/blob/main/docs/unsupported.md)做适配 |
| [prismarine-viewer](https://github.com/PrismarineJS/prismarine-viewer) | 1.21.1世界视图、截图/视频的备选 | MIT；需要Node/WebGL适配，不会自动显示自有Fabric演出模组 |

mcbuild的体素空间默认单轴最多512格，适合构件试验。生成灯座、框架、栏杆等模块后缓存并重复布置，比反复要求agent重画整条长轨道更可控。工程还需自己的机器邻域、音符盒上方空气与音色基底、相机通道和遮挡保护；装饰加入后重新验证实际事件。

[GDPC](https://github.com/avdstaaij/gdpc)是可选程序化接口，需要GDMC HTTP Interface。现有离线存档构建能够施工，当前无需为接口更换写世界方法。[OBS WebSocket](https://github.com/obsproject/obs-websocket)后续用于录制控制，最终画面和声音仍需实际客户端证据。

## 生成与agent工具：选择性采用

| 项目 | 可借鉴能力 | 决策 |
|---|---|---|
| [MIDI-GPT](https://github.com/Metacreation-Lab/MIDI-GPT) | 指定轨道/小节补写、保留上下文 | 代码MIT，公开权重是非商业研究许可。隔离实验，不作为默认无约束后端 |
| [Structured-Arrangement-Code](https://github.com/zhaojw1998/Structured-Arrangement-Code) | lead sheet→伴奏→全曲多轨配器 | 作者代码MIT；推荐的旧Python/PyTorch依赖需独立环境，权重另核实。先前AccoMontage-3引用含旧fork，实施时固定作者仓库和提交 |
| [MusicLang Predict](https://github.com/MusicLang/musiclang_predict) | 和弦条件与续写 | GPL-3.0代码、模型另有条款；约束并不保证完全遵守，留作对照 |
| [music21-mcp](https://github.com/cclawton/music21-mcp) | 可独立Python调用的分析/编辑与MCP封装 | MIT；不是专业编曲模型。[和声实现](https://github.com/cclawton/music21-mcp/blob/main/src/music21_mcp/tools/harmonize_melody.py)主要逐音查固定和弦表，声明的风格参数未用于生成分支，须逐功能验证 |
| [music.build](https://github.com/deer/music.build) | 有类型的曲式/声部/乐理编辑、MIDI和MCP、编曲Skill | Apache-2.0；需要Java25，与MC Java21运行时分开；共享会话状态需任务隔离 |
| [ComposerBench](https://github.com/newmattock/ComposerBench) | 实际音频、回滚、响度匹配和修订证据 | 暂不采用代码：README明确未授予开源许可。真实音频另需MAGDA，不能把fake adapter通路当音乐生产 |
| [Orpheus](https://github.com/mal0ware/Orpheus) | REAPER的分析、局部修改、回滚与音频反馈 | MIT桥接代码，但REAPER另需许可；pre-alpha、部分功能仍待实机。留给以后DAW手工接管方向 |
| [Pedalboard](https://github.com/spotify/pedalboard) / [DawDreamer](https://github.com/DBraun/DawDreamer) | 效果、乐器和离线渲染图 | GPL-3.0；音色实验备选。首版采样预览不必引入完整插件环境 |
| [MuScriptor](https://github.com/muscriptor/muscriptor) | 录音到多轨MIDI | MIT代码与CC BY-NC4.0权重分开；按需转写研究，不作默认无约束后端 |

以上依据是作者资料与少量源码核查，未形成艺术质量排名。不要把公开可见源码、代码许可、模型权重许可和素材许可混为一谈；采用时固定具体版本并更新THIRD_PARTY。

## 通用工具合同

工具通过Python函数或受控CLI返回JSON及本地文件；MCP和各宿主Skill只是可选包装。拟议的分析、局部编辑、预览、比较能力尚未新增为CLI命令。

- 输入绑定文件hash、角色、时间/小节范围、操作、冻结区域；明确秒、beat/PPQ与music GT。
- 输出带文件hash、差异、时间定位、引擎/权重/资源版本、测量、预览和局限。原始音视频留磁盘，大模型只取必要片段与摘要。
- 原始MIDI、GM试听、音符盒采样试听、空间近似和实际录制各自标明真实性等级。
- A/B对齐内容和时间，记录响度匹配与真峰值余量；保留原始相对声部平衡，不能独立归一化每个stem后声称混音改善。
- 可选工具在隔离环境按需安装，按内容与版本缓存；模型常驻仅在需要时启动。安装配置决定受控后端，曲目JSON不允许任意shell。
- 执行、测量、模型意见和听看验收分开。宿主不能传入真实音频/视频时，可由外部评审接口或人接手，不自动标记通过。

## 已做的有限可行性检查

维护者现有Windows/Python3.12环境，以原创4秒三音正弦短句和项目原有8秒原创demo探测：SwiftF0、Basic Pitch的既有ONNX环境、TinySoundFont离线渲染、FFmpeg loudnorm均可运行。未安装新依赖、下载权重或运行新agent/MCP项目。

这只证明本地通路，不证明全新环境安装、混音转写、专业编曲或艺术验收。Basic Pitch冷启动与热调用差异明显，应测实际成功任务的总耗时，而非摘取一次热调用作为整曲性能。

## 实施退出条件

先做音乐闭环，再做建筑预览，再比较生成后端。每一步都需要可复现样例和明确失败案例：冻结旋律未变、局部编辑无越界、故意错音/遮挡能被发现、装饰不改变机器事件。使用同内容试听与同机位比较，同时保留全曲发展检查；技术正确、主观改善和最终录制分别记录。
