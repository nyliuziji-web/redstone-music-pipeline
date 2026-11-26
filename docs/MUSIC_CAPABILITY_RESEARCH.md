# 音乐能力专项研究：从 MP3 到有 Minecraft 风味的红石改编

研究日期：2026-11-17。目的：补足真实音乐制作能力，暂不改写流水线或安装新后端。本次核对作者仓库、部分源码、论文/官方教学，并回查 Nevada 的实际制作记录；以下新候选均未在本机做音质、速度或安装验收。作者示例与 benchmark 不能当成本项目听审结论。

## 1. 主要结论

有现成资源，值得采用的也不只是模型。最有价值的组合是：多种转写候选、细致的编曲方法与可编辑乐谱、可靠音源和局部修订工具、可定位的实际音频反馈，以及专门的音符盒配器/采样逻辑。

目前不能确认存在一个现成项目，能独自可靠完成“任意 MP3 还原→缺失素材补写→专业编曲→实体红石适配→专用音色包”。专业工具不自动赋予模型听觉；增加更多角色名、原则性 Skill 和技术阶段门，也不等于建立专业音乐能力。

应明确区分三种结果：有音频依据的恢复；依据乐理与风格的新编；为游戏表达而做的改编。后两者可以很好听，但不能作为原曲逐音恢复的证据。

## 2. Nevada 为什么较成功

本地复查依据是 Nevada 的素材交接、v04 制作说明、全曲编曲脚本，以及 M2/P3 音色研究。公开经验概述见 [Nevada 复盘](NEVADA_RETROSPECTIVE.md)。

- **素材条件确实更有利**：六条对齐的完整音频分轨，另有 LMMS 主题谱可辅助恢复；网站 MIDI 实际缺段，并非直接拿到完美全曲 MIDI。
- **转写按声部处理**：主唱/低音使用独立音频的 F0；钢琴/吉他用复音候选结合谱面、音频和清理。包含重复乐句的音频支持检查、八度/滑音取舍和泄漏过滤。
- **有具体编曲**：主题起音/持续层、主唱与应答、低频分工、共同音和声连接、钢琴段、滚奏和结尾，按 13 个工作段落改变密度、音区和力度。不是一直套同一种伴奏公式。
- **有真实音色选择与返工**：多套音色按角色组合；主唱与 pad 共槽问题被定位，改独立槽后做同段比较，最终用户选择 P3 与 +3 dB。这个增益与具体音色不是新作品的默认答案。

判断：丰富素材减少了歧义；逐声部恢复、编曲、声音调教和用户反馈同样贡献明显。没有同条件消融对照，不能量化“素材占几成”，也不能由 Nevada 推断仅凭 MP3 的制作能力已经成熟。

## 3. MP3 扒谱：采用两条可比较路线

### 重点现成资源

| 资源 | 可补的实际能力 | 环境、限制与采用判断 |
|---|---|---|
| [audio-separator](https://github.com/nomadkaraoke/python-audio-separator) | 统一 CLI/Python 调用不同分离后端，输出音频分轨 | 包装代码 MIT；模型逐项登记许可。CPU/CUDA 等后端视模型而定。分离不等于转写，可能损伤起音/尾音 |
| [MuScriptor](https://github.com/muscriptor/muscriptor) | 混音多乐器 MIDI/可编辑事件候选，可指定预期乐器 | 代码 MIT，权重 CC BY-NC 4.0 且需接受获取条款。small 可作 CPU 实验，大模型另评 GPU；建议按需启用，不捆绑为默认必需 |
| [Basic Pitch](https://github.com/spotify/basic-pitch)＋已有 SwiftF0 | 单乐器复音候选＋可信单旋律候选 | Basic Pitch 作者明确更适合一次一种乐器，官方 Python 兼容表较旧，宜隔离/ONNX 适配；SwiftF0 不能代替完整混音转写 |
| [Beat This!](https://github.com/CPJKU/beat_this) | beat/downbeat 时间点，比单个 BPM 更能支持原音频对齐 | 代码与发布权重 MIT；PyTorch，CPU 可用/GPU 可加速。仍需核对拍速半倍/倍速、小节相位与拍号 |

路线 A：混音直接多乐器转写。路线 B：针对性的音源分离，再按声部选择单音/复音转写。应在同一个困难样段比较两者，不强制每首歌都先分轨；分离误差有时会使转写更差。

MuScriptor 的 [main.py](https://github.com/muscriptor/muscriptor/blob/main/muscriptor/main.py) 有允许乐器组、可编辑 JSON、首个 downbeat/tempo 等纠正参数及原曲/重建对照；其 [跨块处理](https://github.com/muscriptor/muscriptor/blob/main/muscriptor/transcription_model.py) 还明确了并行吞吐与持续音承接的代价。这些接口值得借鉴，不代表已经证明它适合本曲。

暂不优先把 [YourMT3](https://github.com/mimbres/YourMT3) 作为默认依赖：实际代码/检查点入口与仓库展示分散，许可标识需按确切分发来源核对。[Magenta MT3](https://github.com/magenta/mt3) 可作研究第二意见，但工程集成更重。

### 比“再换一个 F0 模型”更重要的校对能力

1. 同一音频零点、实际 beat/downbeat 和原曲时间线；不为得到整齐 GT 而擅自改成 100 BPM。
2. 保留未清理音符、置信度与不确定区间，明确疑点发生在哪个声部/时间。
3. 按句处理八度别名、谐波假音、音符拆碎、踏板、重复音和呼吸，不一律“吸附调内”。
4. 提供原曲、对应声部、重建独奏和混合的同段对照。色度相关只定位问题，不能充当准确率或审美评分。
5. 有已知谱面真值时用 [mir_eval.transcription](https://mir-eval.readthedocs.io/latest/api/transcription.html) 分别评价音高/起音与结束；没有真值时明确是候选检查。

[HPSS](https://librosa.org/doc/main/generated/librosa.effects.hpss.html) 分的是谐波/打击成分，[pYIN](https://librosa.org/doc/0.11.0/generated/librosa.pyin.html) 给出 F0 序列；频段过滤也不会自动把重叠乐器分开。因此 WorkBuddy 那条临时路线不足以代表专业多轨扒谱。

许可纠正：[Demucs 作者维护仓库](https://github.com/adefossez/demucs#license) 对权重许可提出明确疑问，尤其涉及 6-stem 训练数据。不能再从代码 MIT 推断所有权重都可自由随包分发。

## 4. 素材不足时，agent 怎样真正编曲

### 优先研究 music-skill

[owoevan-dev/music-skill](https://github.com/owoevan-dev/music-skill) 最贴近这次缺口：主模型写可编辑音符，配合真实音源、分轨和版本比较；它本身不扒谱、不负责 Minecraft。

其 [arrangement.md](https://github.com/owoevan-dev/music-skill/blob/main/skills/music-production/references/arrangement.md) 和 [development-and-groove.md](https://github.com/owoevan-dev/music-skill/blob/main/skills/music-production/references/development-and-groove.md) 有比本包目前更具体的声部进行、低音/转位、动机发展、段落与律动方法；其中风格启发式不能升级为所有音乐的硬禁令。

[studio.py](https://github.com/owoevan-dev/music-skill/blob/main/skills/music-production/scripts/studio.py) 有指定音符修订、渲染回合及音色比较。需要保留我们自己的冻结母版/区域差异检查；尚未确认它能将任意已有 MIDI 无损导入完整项目，不能直接替换母版层。

主体 MIT，但 Surge 主机脚本及外部程序、音库各有许可，见 [THIRD_PARTY](https://github.com/owoevan-dev/music-skill/blob/main/THIRD_PARTY.md)。CPU 路线适合先试少量音源，没必要先装全部数 GB 音库。实际试听质量尚待测试。

### 配套知识与候选生成

- 已有 music21 继续负责表示、分析与精确变换，不能把它当自动编曲师。[官方文档](https://www.music21.org/music21docs/)
- [Open Music Theory](https://openmusictheory.github.io/contents.html) 与 [MIT Harmony and Counterpoint](https://ocw.mit.edu/courses/21m-301-harmony-and-counterpoint-i-spring-2005/) 适合建立可执行练习；古典规则不直接裁决流行/电子编曲。
- [Groove MIDI Dataset](https://magenta.tensorflow.org/datasets/groove) 可学鼓手律动/重音，MIDI 部分很小；按官方鼓映射与 CC BY 4.0 归属处理，不先下载整套大音频。
- [OpenScore Lieder](https://github.com/OpenScore/Lieder) 的 CC0 谱例可用于研究旋律与伴奏活动密度，但不是现代流行编曲的万能模板。
- [MIDI-GPT](https://github.com/Metacreation-Lab/MIDI-GPT) 的局部补写可用于生成少量伴奏候选；权重有非商业研究/教育限制。不是凭空恢复原曲缺失声部。
- [Structured Arrangement](https://github.com/zhaojw1998/Structured-Arrangement-Code) 更适合已有旋律/和弦的配器实验，旧环境与权重条款需进一步核对；不建议首批强依赖。

### 应形成的实际编曲方法

先冻结可信旋律、关键节奏与低音/和声依据，再写声部职责和段落目的。每次只为缺失部分写 2–3 个有区别的方案：例如持续内声、切分和弦、间隙应答，不能只是多加一轨复制旋律。记录和弦连接、音区、重音、疏密与进入/退出原因，实际渲染后修改。

如果输入无法确定原来的某条伴奏，允许依据乐理和风格新编，明确标注。不能用“理论上合理”证明它原本存在。Skill 应配完整音符例子、不同方案的试听和失败诊断，不再只列抽象注意事项。

## 5. 专门适配红石音乐，需要自己的领域逻辑

[NoteBlockLib](https://github.com/RaphiMC/NoteBlockLib)、[NoteBlockTool](https://github.com/RaphiMC/NoteBlockTool-Desktop)、[Note Block Studio](https://github.com/OpenNBS/NoteBlockStudio) 适合作 NBS/MIDI 交换、检查、试听和作者实践的参照；不能把逐音 clamp/换乐器当作专业编配，也不能把传统结构导出的 10 TPS 限制施加到本项目 1 GT 机器。

[nbswave](https://github.com/OpenNBS/nbswave) 可作独立试听对照，但当前依赖约束与本包 NumPy 2 / WorkBuddy Python 3.13 不同，宜隔离。编辑器里的 velocity、panning、自定义乐器和新版乐器表不自动等于 1.21.1 实体机器能力，见 [官方自定义乐器说明](https://noteblock.world/help/custom-instruments)。

必须自主实现的不是再一个格式转换器，而是这些决策：

- 保留主旋律轮廓、律动、句尾、关键低音/和声；伴奏简化要服务主读。
- 以乐句/角色固定音色身份，选择合适采样根音和分区，避免超范围就逐音换乐器。
- 分别比较自然尾音、定制持续样本、独立持续层与补触发；计入颤动、跨和声尾音、机器规模和掩蔽代价。
- 分配有限声音槽；共享槽的增益/包络会联动。按角色需求分槽，不按 GM program 数量机械分槽。
- 将相机/声部距离和方位作为空间配器，保持声音与可见实体演奏对应。

一个可立即验证的设计例子：本次《烟袋斜街》转写主旋律为 MIDI 61–82，跨度 21 半音，本可放入音符盒 25 个调音格。若制作实际根音为 MIDI 72 的统一采样，理论上映射到 note=1–22，无需 56 次 banjo/flute 交替。还须验证音色与变速尾音，不能据此宣称已经好听；它说明“选择/制作合适音色”比默认逐音回退更符合任务。

## 6. 专用资源包：从格式打包升级为音色设计

### 现成工作台

| 资源 | 适合的用途 | 限制 |
|---|---|---|
| [Polyphone](https://github.com/davy7125/polyphone)＋[FluidSynth](https://www.fluidsynth.org/wiki/UserManual/) | 采样根音、包络、循环、音域及真实音源试听；离线单音渲染 | 代码各自 GPL/LGPL；音源另算。并非所有编辑都可 CLI；SF2 循环/note-off 不会自动成为 OGG 的游戏功能 |
| [Faust / faustbrowser-mcp](https://github.com/grame-cncm/faustbrowser-mcp) | 让 agent 实际调合成器、滤波、包络与探针测量 | 官方项目含 [metering Skill](https://github.com/grame-cncm/faustbrowser-mcp/blob/main/skills/faust-internal-metering/SKILL.md)，但不是 MC 包导出器。需自有离线渲染适配；MCP 项目 LGPL-2.1-or-later |
| [VSCO 2 CE](https://github.com/sgossner/VSCO-2-CE) 等许可明确的单音 | 自制音色材料和听审音源 | VSCO 样本 CC0；不保证每个乐器符合本曲，不必一次装完所有音库 |
| [SFZ legato 教程](https://sfzformat.com/tutorials/legato/)与[元音素材](https://github.com/sfzinstruments/legato_vocal_tutorial) | 学习持续/衔接的实际机制，研究类元音代奏 | 元音素材 CC0；SFZ 的键控与 loop 机制不能原样宣称已进入原版音符盒 |

### “还原原曲＋Minecraft 风味”的设计方式

这是一项按曲目决策的创作目标，不存在通用的混合百分比。建议比较三种方向：原版主导、原版瞬态＋定制音体、偏真实音体。

保留原曲身份的重点是旋律、节奏、音区、包络与声部分工；MC 身份可以由木质/拨弦/方波起音、钟声点缀、离散触发和可见红石承担。不要求每个角色同等“原版”，也不要求把每条轨变成逼真的现实乐器。

将音色做成配方：材料来源→根音→攻击/音体/尾音→滤波/共振→有限持续→槽位与增益→渲染与游戏校验。可预烘焙为一个单音，也可显式分起音/持续两条实体声部；不能把 sounds.json 随机候选列表当分层合成器。

原版 note=0…24 对样本变速，倍率为 `2^((note-12)/12)`，音高升高时尾音同时缩短。必须测低/中/高、快连奏、同刻和弦、长音及跨和声尾巴。普通资源包不按 MIDI note-off 停音，也不直接执行每音力度。位置音效使用单声道 OGG Vorbis，格式依据见 [1.21.1 Fabric 声音文档](https://docs.fabricmc.net/1.21.1/develop/sounds/custom)。

Nevada 的可复用资产不是 M2/P3 常数，而是：按角色混合音色方案、主唱/pad 共槽诊断、同增益独奏与混合、单变量比较、实际用户听审与相同机位检查。这些方法应比试听器/ZIP 生成器获得更多开发投入。

## 7. 给 agent 增加实际“耳朵”

可研究 [Music Flamingo](https://huggingface.co/nvidia/music-flamingo-2601-hf) 或可接受真实音频的 [Qwen3-Omni](https://github.com/QwenLM/Qwen3-Omni) 作为独立听觉意见接口。前者模型卡明确非商业研究用途；部署、内存和具体 API 需另测。这些模型不是主控/编程 agent 的替代品。

必须真的传入对应原曲/候选片段。让评审指出时间、声部、具体听到的差异，再给出反例核查；不只问“好不好听”。音频描述能力不证明逐音准确或审美判断可靠；文本转录、色度图和模型自信不能冒充听到音乐。

建议优先定位：主旋律丢失、节奏错位、长音变短/补触发颤动、音色换段、低频拥挤、原曲织体被公式化替换。人工认可仍按代表段/最终成品记录；日常 agent 也应有自己的听觉修订回路。

## 8. 推荐下一步的三项小实验

1. **只有 MP3 的恢复实验**：三段 20–30 秒，覆盖主旋律、复杂叠奏、长音交接。比较直接多乐器转写与分轨后逐声部转写；保留疑点和音频对照，代表段有用再跑全曲。
2. **素材不足的编曲实验**：给 16 小节可信旋律/和声骨架，冻结旋律，用具体编配 Skill 创作两种伴奏与应答；比真实独奏/混合，检查是否有段落发展，不能由“音符更多”判优。
3. **同谱音色与红石实验**：保持认可音符和时序，做原版/混合/偏真实三组音色，再比较持续策略。最终使用同一个实体样机与相机路径录音，区分编曲、音色、音量和距离的影响。

先补 audio-separator/Beat This!/可选多乐器转写与对照试听；同时试验 music-skill 的方法和渲染修订工作台，再将 Nevada 的声音配方/路由经验产品化。MIDI-GPT、大型 DAW 接管、扩展乐器模组按实验结果再决定，不先把所有工具设为必装。

节省资源依赖于少量样段、分层缓存、局部修订、选择性分离、按需加载音库/模型，而非降低校对标准。记录下载/冷启动/推理/修订总成本；本次没有实测成本，不能报告节约百分比。

**这份研究支持的是明确的试验优先级，不是新后端已经集成或专业音乐质量已经得到证明。**
