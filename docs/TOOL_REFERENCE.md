# 可执行工具与交接合同

所有命令前缀为 `python run_pipeline.py`；安装 wheel 后用 `python -m redstone_music`。每个子命令用 `--help` 查看参数。工具输出 JSON，异常返回非零码；媒体/目录产出通常拒绝覆盖。源文件保持不变，修改写入新候选。

## 专业音乐与声音

| 命令 | 输入与产出 |
|---|---|
| `inspect-source SOURCE [--out FILE]` | 检查真实 MIDI/音频字节，不把 HTML 登录页当音乐 |
| `analyze-music SOURCE [--backend builtin|music21|auto] [--out FILE]` | 角色、复音、段落、速度/时长与乐理候选；默认 builtin 避免隐式重依赖 |
| `analyze-audio SOURCE [--out FILE]` | librosa 能量、色度、起音与 tempo 候选；不是已听过作品 |
| `transcribe-melody SOURCE --out DIR` | SwiftF0 本地单旋律候选 MIDI、逐帧音高/置信度，需音乐校对 |
| `edit-music-region MIDI --patch FILE --out MIDI` | 绑定母版哈希与时间区间，修改指定音符；验证其他音符和控制事件不变 |
| `audio capabilities/transcribe/beats/separate/compare …` | 本机后端检查、可核对原始输出的转写/分轨/节拍候选、同一时间轴试听 |
| `composition import/revise/export/review/render/study/voicelead …` | 冻结可信主题，写局部音符、声部和段落，听实际音源的独奏和混合 |
| `plan-noteblocks SOURCE --out DIR [--profile FILE] [--consistency role\|phrase] [--adaptation-plan FILE]` | 默认整条声部统一声音；报告选槽和移调，产出 events.json / adaptation_plan.json |
| `design-timbre RECIPE --out DIR` / `build-palette SPEC --out DIR` | 调整起音、音体、根音与包络，生成采样和可进入实体编配的声音包 |
| `audit-palette PROFILE [--events FILE] [--out FILE]` | 测全部 25 格变速音高和尾音，定位持续和重叠疑点 |
| `compare-timbres SOURCE --palette FILE --out DIR` / `timbre-study NEW_DIR` | 固定 MIDI 和事件决策，对照三种配方与同增益独奏 |
| `texture-study NEW_DIR` | 生成原创 16 秒基线和织体候选、同增益混合和新增层独奏，以及可用 `run` 构建的两个项目 |
| `build-soundpack SPEC --out DIR` | 原创合成或显式提供的采样，生成 profile、样本、校准报告、resources.zip |
| `calibrate-profile PROFILE [--out FILE]` | 实际解码、频谱中心候选与声明根音比较；噪声/复杂采样仍需听审 |
| `render-preview SOURCE --out WAV --mode MODE [--profile FILE] [--soundfont FILE] [--fluidsynth PATH] [--begin S] [--end S]` | 结构参考、真实 SoundFont 或音符盒采样预听。GM 可用 FluidSynth 或 TinySoundFont |
| `compare-candidates A B --out DIR` | FFmpeg 实测响度、共同目标的 A/B，不分别归一化同一混音中的声部 |

学习素材与失败练习用 `learn NEW_DIR` 生成。声音 spec 示例在 `templates/soundpack.example.json`；完整音色/延音方法见 sound-designer / noteblock-arranger Skill。

自定义声音进入流水线时同时提供 `inputs.soundProfile` 与 `inputs.soundPack`；可选 `inputs.adaptationPlan` 必须完整覆盖当前源音符，源哈希、角色、profile、音高和时序均检查，实际驱动选槽与延音策略。原样批准事件输入不能被新 profile 静默重编。改 profile 引用的采样也会使 sound 及后续缓存、未完成任务失效。

## 世界与演出

| 命令 | 输入与产出 |
|---|---|
| `preview-stage BLUEPRINT --out DIR [--protection FILE]` | 声明式 set/fill/frame/stairs/blocks，材料/保护冲突与四视图；几何不等于游戏物理 |
| `compile-show SCORE --out DIR [--style FILE]` | 音符或显式 show score，节点/环/螺旋/贝塞尔与字幕，统一 musicGT |
| `game inspect INSTANCE [--java PATH]` | 只读版本/模组/JDK 元数据，不读取账号文件 |
| `game import INSTANCE --out DIR [--java PATH]` | 新独立 profile，显式引用合法本地依赖，不复制登录凭据 |
| `game build-client client --out DIR --java PATH [--gradle PATH]` | 标准 Loom/Yarn/Gradle 源码构建、日志与 remapped client.jar |
| `photon-plan SHOW --out DIR --mod-jar FILE` | 检查确切 Photon 发行，准备同样段对照；不编译 .fx、不假称已运行 |

建筑蓝图以世界绝对坐标通过 `inputs.stageModule` 合入机器。50,000 方块、2,000 操作、单轴跨度 512 限制；合入拒绝覆盖、线路邻域、音符盒头顶/基座、相机通道和主动/不稳定方块，限制总体导出体积。真实游戏仍需复核。

机器配置支持：

```json
{"layout":{"families":[{"id":"voice","x":0,"y":-8}],"camera":{"x":37.5,"eyeY":112.5,"teleportDuration":3}}}
```

声部 x/y 是相对模板中心的整数偏移；几何碰撞/复音/边界均会拒绝。当前物理架构固定每 GT 前进一格与 80 格核心走廊，相机跟随速度固定 20 格/秒，插值可选 1/2/3 GT；不是任意线路、朝向或速度编辑器。镜头移动或布局改变后必须重新做实际触发与视听验收。

`inputs.showScore` 进入 visuals，`runtime.clientJar` 指向标准构建的客户端；流水线嵌入作品 score，验证/发布绑定其字节。该客户端支持本地集成服务器的时钟；远程多人同步未实现。

## 主控、媒体与恢复

`brief PROJECT --text TEXT` 更新需求；`decision PROJECT --summary TEXT --reason TEXT` 追加决策。`review PROJECT --file FILE` 使用 `templates/review.example.json`，保留真实反馈、审阅者、方法和输入哈希。文件改动后 `handoff PROJECT` 标记旧认可过期，不自动授予艺术通过。

`create-task PROJECT --role ROLE --kind KIND --objective TEXT` 创建文件任务；claim / complete-task 和旧 review 模式兼容。角色包含 producer、music、arrangement、sound、machine、stage、visuals、quality；任务类型包含 review、music_import、arrangement、sound_profile、show_score、stage_module、engine_change。task.json 给出对应 Skill、输入、允许范围与必需输出；专业 agent 只写自己的 output。任务中的 `review` 是技术提案审阅；用户媒体反馈另用 `review` 命令，不混作同一合同。

`handoff PROJECT` 派生 STATUS.md/handoff.json，不覆盖 brief/plan/决策。不要把 stdout 重定向到 handoff.json 本身；工具会写该文件。主 agent 或单 agent 完成相同合同，Python 不要求宿主有子 agent API。

`inspect-media SOURCE [--out FILE]`、`clip-media SOURCE --out FILE --begin S --end S`、`capture-evidence PROJECT SOURCE --out PROJECT/evidence/FILE.json --kind sample|full` 使用真实 FFprobe/FFmpeg；录制来源、同步和听看需要另行验收，不由流元数据证明。

`bundle-check [--root DIR]` 验证资源结构、技能和本地链接；不接受 ZIP。`bundle-export NEW_DIR` 按白名单导出源码/技能/教程与哈希清单，不带游戏、账号、项目缓存或私人音乐。ZIP CRC 用标准 zipfile 检查，不能代替内容验证。
