# 音符盒扩展模组研究与默认依赖判断

日期：2026-11-17。对象：Minecraft Java 1.21.1 / Java 21 / Fabric，音乐仍由实体红石逐音触发。

本次查了作者源码、官方发行 API、准确版本的 JAR 元数据与部分字节码/音频。没有安装模组、启动游戏、更改已认可世界或修改默认环境。新模组的启动、听感、实际音高、重播清理均未通过本项目实机验收。

## 1. 决定

**当前不把任何新增第三方音符盒模组列为全包强制默认依赖。默认继续为原版音符盒＋作品专用声音资源包。**

这不是认为模组没有价值，而是目前候选分别补不同能力，没有一个已核实的发行能够直接补齐本包需要的声音表达，并兼容现有编译、短脉冲线路和验证链。

优先顺序：

1. **Infinote：优先研究定制声音槽/音区配置的可选后端。** 它接近现有“基底→单音→音符盒”的逻辑，但不是完整延音/力度引擎。
2. **Rosen：现成 Minecraft 风味音色库与扩展预设候选。** 内置音色实用，但不能因新增 choir/violin 名称就认为具有键控长音。
3. **Extended Note Block：表达增强与可维护 fork 的研究候选。** 功能最接近每音力度、时长和多采样，但不适合直接默认依赖其无人维护发行。

如果某作品确实使用扩展后端，该作品的安装包必须将其作为必需依赖锁定；不能在缺模组时悄悄回退并继续声称同一音乐表现。离线工具不应因为没有游戏模组就无法分析、编曲或试听。

## 2. 实用候选对照

| 模组 | 已核实的价值 | 不能直接解决的部分 | 本次决定 |
|---|---|---|---|
| [Rosen](https://modrinth.com/mod/rosen) | 1.21.1 Fabric；18 个新增乐器，保留 MC 音色方向；支持数据驱动自定义乐器 | 仍是原版 NOTE 范围；没有 MIDI velocity / note-off / 循环延音引擎 | 音色/预设候选，不作强制默认 |
| [Infinote](https://github.com/RS-256/infinote) | 按基底配置声音 ID、半音偏移、音量；独立自定义声音槽，不必新增方块实体 | 每个音符盒仍是 25 格；偏移按基底配置；没有每音时长/释放和 MIDI 力度事件 | 优先做定制资源包扩展适配，实测前不默认必装 |
| [Extended Note Block](https://github.com/atemukesu/ExtendedNoteBlock) | 自定义实体方块，MIDI 音高、力度、持续/延迟/淡出、多采样音区 | 已归档；下降沿停音与本包线路冲突；有限样本不等于自动无限持续；有需复现/修复的停止疑点 | 独立原型/fork 候选 |
| [Note Block Master](https://modrinth.com/mod/note-block-master) | 宽音域、音量核心与持续音实验 | 1.21.1 为 NeoForge；持续能力仍 alpha、仅部分乐器 | 不为它迁移当前 Fabric 主线 |
| [Glissando](https://github.com/axialeaa/Glissando) | 调音界面与数据化乐器，适合游戏内作者操作 | 不能据此认定支持 MIDI 力度/键控延音；额外 YACL 依赖，作者提示重构 | 非核心作者辅助工具 |

MIDI 自动播放器、唱片/整曲音频播放、NBS 服务器播放插件不作为替代选择：它们与实体红石线路逐音演奏不是相同生产合同。

## 3. Rosen 的准确能力与集成成本

官方 [1.21.1 Fabric 1.1.0 发行](https://modrinth.com/mod/rosen/version/kPFw7yz4) 的版本 ID 为 `kPFw7yz4`；不要拿同版本号的 NeoForge 文件。

- 文件：`rosen-fabric-1.21.1-1.1.0.jar`，1,395,767 字节。
- SHA256：`2d7905e6e2cbd4b4875ff42c322b12168f66ac308725059953d921b2f65a4fd2`，本地文件 SHA1 与官方 API 相符。
- JAR 要求 Fabric Loader ≥0.16.9、Fabric API、MC1.21.1、Java21，环境为 client/server；当前 Loader0.18.2 满足该版本门槛。
- 官方 API 的 dependencies 数组为空，但 JAR 有依赖要求。安装器不能只看 API 数组。
- 作者仓库默认分支为 1.21.1，最新该发行更新于 2025-11-04；未归档不等于持续活跃维护。

实际实现扩展乐器枚举与基底 tag；没有将每个 note block 变成全 MIDI 采样器。现有 Python 16 乐器白名单、基底校验和 vanilla 服务端运行器都不能原样验证这些新增值。默认内置映射还可能改变既有世界某些基底的音色，需要回归。

**音频核对结果**：18 个 OGG 可解码，均 mono/44.1kHz，约 0.210–0.857 秒；choir/organ/saxophone/synth 约 0.429 秒、violin 约 0.482 秒。名称不等于真实键控延音；不能指望安装后自然承担数秒长音。高音变速还会缩短样本。

自定义数据来自 `data/<namespace>/noteblock_instrument/*.json`，有 `name` / `sound_event`；核对的 1.1.0 查找基底 tag 使用 `rosen:<name>_noteblocks`。应以 [作者源码](https://github.com/Violunae/rosen/tree/1.21.1) 与准确 JAR 为准，不照抄网页中不精确的目录/命名空间示例。

该动态映射只看到服务端数据重载与静态 map，未确认专用服务器到远程客户端的同步机制。因此“同时标 client/server”不能证明自定义乐器联网同步已可靠；内置音色与单机同 JVM 路径也不能替它作证。

Rosen 的 `fabric.mod.json` description 含原始换行，Python 严格 JSON 会拒绝，但实际 Fabric Loader0.18.2 的内置读取器允许这种字符。本包当前严格元数据检查也需要兼容处理，不能直接据此判断模组不能启动。

仓库根许可证为 MIT、Copyright 2024 Notjang，未找到独立音频许可/credits；没有逐个确认音源原始来源。技术上还可考虑在明确来源/许可后选取少量音色映射回原版槽位，从而不依赖整个模组；本次没有提取发布音色或声称来源已全部核清。

## 4. Infinote 与定制资源包更接近，但不是完整 MIDI 后端

选定 [专门的 1.21.1 发行](https://modrinth.com/mod/infinote/version/KZ2K3X7V)，版本 ID `KZ2K3X7V`：

- 文件：`infinote-v1.6.0-mc1.21.1.jar`，48,398 字节。
- SHA256：`d27ea996c42cf916d2b781bb7e290915a247e98ff8c1303dfe9f171ed09dac0d`，本地文件与官方 SHA1 匹配。
- JAR 内版本显示 1.5.3，文件/发行名为1.6.0；锁文件应同时保存，不能只按显示名识别。
- 要求 Fabric Loader ≥0.18.6，**高于当前0.18.2**；不能直接说与当前基线已兼容。
- 官方兼容标签也会返回名为 mc1.21.4 的文件，不能下载排序第一项。

[作者说明](https://modrinth.com/mod/infinote) 与 [NoteBlockMixin 源码](https://github.com/RS-256/infinote/blob/main/src/main/java/com/rs256/infinote/mixin/NoteBlockMixin.java) 支持如下判断：

基底映射包含 sound/category/pitchShift/volume。原版红石起音处被接管，播放指定声音；资源包仍必须提供实际单音。客户端模组扩大 pitch clamp；缺客户端不能保证超出原版范围的音准。

这能减少原版声音槽共用的束缚，也可用不同基底代表同一乐器的不同音区。但 NOTE 属性仍是0…24，pitchShift 是基底配置值；不能说每个原版音符盒因此拥有128个可直接调音格。volume 也不是每个 MIDI note 独立变化的 velocity。

没有看到独立 note-off、门控循环或每音 ADSR 机制；它仍按样本长度发声。原版 playSound 中大于1的 volume 还会影响传播范围，不能直接将配置倍率解释为等量 dB 增益，需实际声音验证。

现有追踪器钩住原版 note-block 事件路径；该模组在播放处取消并改发声音。因此要新增实际 sound ID、pitch、音量、位置与时序的证据，不能照搬原版 `serverVerified`。普通原版 note-block 的 NBT/几何较易复用，但不能只增加一个安装 JAR 的步骤就称为已集成。

## 5. Extended Note Block 更接近表达需求，也更需要维护

[v1.9.1](https://github.com/atemukesu/ExtendedNoteBlock/releases/tag/v1.9.1) 于2026-07-19发布，含1.21.1 Fabric文件；作者于2026-07-24归档并明确不再维护。发行说明要求 Fabric API ≥0.116.13+1.21.1，高于本包0.116.4。

它确实是红石上升沿触发单音的 [自定义实体方块](https://atemukesu.github.io/ExtendedNoteBlock/manual/extended_note_block.html)。支持按音高选择采样区和逐音力度/持续参数，比原版单采样变速更有表达空间；音乐仍可保留实体触发。

但是关键源文件与本包约束有冲突：

1. [方块逻辑](https://github.com/atemukesu/ExtendedNoteBlock/blob/v1.9.1/versions/1.21.1/main/java/com/atemukesu/extendednoteblock/block/ExtendedNoteBlockBlock.java) 在下降沿取消延迟并停音。本包目前只保证短脉冲起音，没有生成按源时值持续供电的门控线路，不能直接换块。
2. [ActiveSoundFader](https://github.com/atemukesu/ExtendedNoteBlock/blob/v1.9.1/src/main/java/com/atemukesu/extendednoteblock/sound/ActiveSoundFader.java) 设置的强制淡出状态未在主要更新计算中使用。这是需复现/修复的静态代码疑点，不能当作已确认的游戏现象或稳定停止保证。
3. [声音实例](https://github.com/atemukesu/ExtendedNoteBlock/blob/v1.9.1/src/client/java/com/atemukesu/extendednoteblock/sound/StoppablePositionalSoundInstance.java) 不自动循环；有限短样本不会因 sustain 参数自动变成无限长音。
4. 毫秒调度仍回到游戏线程，不保证独立音频时钟的精度；[开放 issue #3](https://github.com/atemukesu/ExtendedNoteBlock/issues/3) 与延迟后已断电不发声有关。
5. [声场 Mixin](https://github.com/atemukesu/ExtendedNoteBlock/blob/v1.9.1/src/client/java/com/atemukesu/extendednoteblock/mixin/client/SoundSystemMixin.java) 的 LINEAR 衰减修改未限定自己的命名空间，可能影响其他声音，需要实测。

值得借鉴多采样音区、每音力度、声音 UUID/停止控制和 [NBT接口](https://atemukesu.github.io/ExtendedNoteBlock/manual/generator_preparation.html)。若未来选它，应先承担维护或缩减 fork，再适配时钟、线路、声音与验证；不需要顺带采用无线红石等无关功能。代码 MIT 不自动证明随附默认音源包的逐个采样来源，本次未检查该包全部来源。

## 6. 默认依赖必须换来可验证的收益

候选升级为默认后端至少需要通过：

- 明确提升现有方案无法满足的能力：更多独立声音槽、少损失的音区、多采样、每音力度或可停止延音，不能只增加软件数量。
- 1.21.1客户端/服务端安装、资源重载、保存重进、完整播放、中止、重播及声音清理。
- 相同谱/相同机位的原版与扩展对照；低中高音、快速连奏、长音、密集和弦、静音/尾奏；实际声音而非只看服务端数字。
- 编译器、sound profile、世界/投影、追踪器、客户端与安装清单使用同一后端合同。没有模组或缺样本时明确失败，不能静默替换音色。
- 依赖和源代码可维护，声音来源明确，并具备可恢复的原版路线。

普通扩展模组不会修复错误扒谱、公式化伴奏或缺少听觉判断。当前《烟袋斜街》主旋律跨度本可容纳在25格中；统一样本根音和乐句配器已能解决部分问题，不需要先增加模组。

**因此：可以确定优先试验对象与能力边界，当前还不能负责任地指定一个新增第三方模组为整套集成包的默认必需依赖。** 将来若明确选择完整力度/时长后端，新增模组可以成为新版默认；那是需要完成适配和实测的后端升级，不是现在安装一个现成 JAR 即可。
