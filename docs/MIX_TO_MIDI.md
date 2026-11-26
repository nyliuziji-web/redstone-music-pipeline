# 从混音校出可信母版

手上只有一首 MP3 或 WAV 时，先完成一段可逐音核对的代表段。交付包括可继续编配的 MIDI、可对应原曲时间的听审文件，以及说明哪些音已校对、哪些声部是新写的记录。这里的母版保留音乐时间、时值和力度，游戏调音与触发另做。

有可核实的谱面、配套 MIDI 或局部改编时，先用[素材覆盖与重建教程](SCORE_FROM_REFERENCES.md)决定哪些段用读谱，哪些段需要回到录音。

## 1. 选一段能暴露问题的录音

从源码包根目录执行命令，`python` 使用 [START_HERE](../START_HERE.md) 的制作环境。以下占位路径替换成自己的文件，`work/mix/...` 用于新候选。

```shell
python run_pipeline.py inspect-source "input/song.mp3" --out work/mix/intake.json
python run_pipeline.py clip-media "input/song.mp3" --begin 7.22 --end 27.82 --out work/mix/excerpt.wav
python run_pipeline.py analyze-audio work/mix/excerpt.wav --out work/mix/audio-analysis.json
```

打开 `intake.json` 检查文件确实是录音、时长符合版本。自己选段时，优先包含一次完整主题、重复或变体、一个影响判断的密集处和句尾。原曲绝对秒和截段局部秒都要保存。上例的局部 0 秒就是原曲 7.22 秒。第一个起音前的静音也保留。分轨和候选一律使用同一零点。

**复查。** 用原曲前后两个辨识度高的起音与截段对照。若始终相差同一时间，先查截段零点、分轨延迟或编码前导。偏差随时间增长时，查拍速、速度图或半速/倍速误判。修正时间轴后再动单个音。波形和节拍分析可以定位疑点，句末的呼吸与尾音用对应录音判断。

## 2. 生成互相补充的候选

按[音频后端安装与路径示例](../integrations/transcription/README.md)准备 Basic Pitch 的独立环境。只有混音时先跑一个直转候选。某条声音确实被其他声部盖住，再按同一教程分轨，读取分离结果实际列出的文件名。

```shell
python run_pipeline.py audio transcribe work/mix/excerpt.wav --python .audio-venv/Scripts/python.exe --out work/mix/direct
python run_pipeline.py audio transcribe "work/mix/实际分离出的人声.wav" --python .audio-venv/Scripts/python.exe --out work/mix/voice
python run_pipeline.py audio compare work/mix/excerpt.wav work/mix/direct/result.json work/mix/voice/result.json --begin 0 --end 20.6 --out work/mix/compare-v1
```

Linux 的解释器路径改成 `.audio-venv/bin/python`。只跑了直转时省略第二个候选。已有可靠分轨可跳过模型分离。明显为单线的主唱或贝斯，可按[环境教程](ENVIRONMENT.md)安装 `.[pitch]`，用 `transcribe-melody` 作频率轨迹参考。确定强拍有歧义时，再按音频后端教程加一份 Beat This! 候选。

1. 在 `direct/result.json` 中找到输出 MIDI、原始预测和候选疑点。幅度与置信度只用于排查。混音候选里的高音可能是和声、泛音或镲片泄漏。
2. 在 `comparison.json` 看每份候选是否完整覆盖所选时间。打开 `disagreements.json`，用 `timeSeconds` 和 `noteId` 找出分歧。左原录音、右重建的试听适合找时差。音色不同会影响主观响度，必要时交替播放单独的 `original.wav` 和 `candidate_1.wav`。
3. 分轨后听同一小段的原混音和目标轨。若分离改变起音或把伴奏带进目标轨，保留原混音作交叉核对。在只有频谱、没有实际听审的环境，记下依据和仍需听的时间点。

**实测对照。** 一段有真值 MIDI 的 20 秒原创混合测试里，直转得到 197 个候选音，121 个能与参考的 130 个有音高音一对一匹配（同音高、起音差不超过 50 毫秒）。这只能说明那次混合测试的表现。实际曲目通常没有真值谱，候选同意也只能帮助缩小检查范围。

## 3. 用原声把每个分歧处理掉

按乐句建一张表，每行写原曲时间、局部时间、声部、候选、依据和决定。先校主旋律的音高、起音和呼吸，再校低音、和声与鼓。遇到小节断点时把片段前后多听一拍，确认先后关系。

下面是《烟袋斜街》实际校对的节选。时间是原曲绝对秒，公开练习使用下节的原创素材。

| 原曲位置 | 观察与决定 | 怎么复查 |
|---|---|---|
| 9.305 / 9.604 秒，11.698 / 12.003 秒 | 模型拉成长 C♯5，但录音在后一个时点有新的起音。把长音拆成两个同音 | 跟着录音数两个起音，和重复句对比。保留需要的间隙，不凭音高相同合并 |
| 约 13.57 秒 | 单线频率估计偏低。依据原混音的频带与前后动机，采用 D♯5 | 同时把低八度与 D♯5 渲染作短 A/B。无法区分时保留疑点，别给整轨移八度 |
| 18.00–19.21 秒与 22.81–23.11 秒 | 前者保留低区的上行引子，后者保留确实出现的高音 A♯5、G♯5 | 分别听低到高的衔接和高点回落。避免用“所有大跳都纠正”的规则抹掉句形 |
| 11.10、15.90 秒附近 | 两颗较轻的起音主要依据重复句推定，置信度低于前景旋律 | 在交接里保留疑点，比较保留和省略后的节奏，听审后再定 |

**常见修法。** 同音有清晰新起音就拆音。只有颤动没有重新发音时合并碎音。漏掉确定的音时补入原来的时间位置。删掉疑似泄漏前先在原混音核对它是否属于另一条实际声部。录音证据不足时，可做合理的新编配并说明出处。保留未确认的弱音；优先解决错拍、主奏八度、缺段等会改变音乐的分歧。

## 4. 局部编辑并证明没有误改别处

在实际候选上运行 `inspect-source` 取文件 SHA-256，用 `analyze-music` 或 `audio compare` 找疑点。再用 `python run_pipeline.py composition import work/mix/direct/candidate.mid --out work/mix/note-index` 读出完整的音符索引。在生成的 `composition.json` 内看 `tracks[].sourceTrack`、具体音符的 `id/channel/startTick/endTick` 和 `tempoMap`。`beginSeconds/endSeconds` 以该 MIDI 的局部零点计，覆盖需要改动的完整音符。改音高用 `operations[].pitch`。拆分时用 `operations[].endTick` 缩短原音，再用 `addNotes` 提供同轨同通道的 `track/channel/pitch/velocity/startTick/endTick`。用原音轨道与速度图转换编辑位置，避免用固定 BPM 换算变速段。字段也可对照[局部编辑格式](../skills/music-director/references/guide.md#成功与失败练习)。

可以离线练一次“错谱 → 定位 → 局部修正 → 与真值比对”。练习从一首原创分轨谱合成参考混音，故意错八度的 MIDI 充当候选。

```shell
python run_pipeline.py learn work/mix-lesson/lesson
python run_pipeline.py render-preview work/mix-lesson/lesson/master.mid --mode reference --out work/mix-lesson/known-mix.wav
python run_pipeline.py audio compare work/mix-lesson/known-mix.wav work/mix-lesson/lesson/bad_octave.mid work/mix-lesson/lesson/master.mid --begin 0 --end 10 --out work/mix-lesson/before
python run_pipeline.py edit-music-region work/mix-lesson/lesson/bad_octave.mid --patch work/mix-lesson/lesson/fix_octave.patch.json --out work/mix-lesson/fixed.mid
python run_pipeline.py audio compare work/mix-lesson/known-mix.wav work/mix-lesson/fixed.mid work/mix-lesson/lesson/master.mid --begin 0 --end 10 --out work/mix-lesson/after
```

先看 `before/disagreements.json`。实际会标出候选一在 **8.000 秒**的 `t2n0`，MIDI 91。标准修复把这一颗音改为 MIDI 67，其余音符与控制事件保持。对照报告按时间和音高匹配，其他声部已在同刻奏出 67，所以它没有另列一条「67 缺失」。诊断漏音时也要看对应轨和声部。修正后 `after/disagreements.json` 的 `items` 为空，编辑命令报告 `frozenControlsPreserved` 与 `outsideRegionPreserved` 都为 true。真实曲目仍要复查时值、力度、速度图和踏板。这个练习专练校谱，可选把 `known-mix.wav` 再送入 Basic Pitch 体验原始候选的噪声。

## 5. 冻结可信线条，再补写缺失声部

把已校对的主旋律标清角色，用 `composition import` 冻结可信轨。写伴奏时先标强拍、和声骨架与主奏空隙。先试低音和少量内声，再决定在哪个句尾加回答、在哪一段让鼓进入。主旋律可靠但和声模糊时，可以比较两份伴奏，并把新增轨的 `origin` 写成 `new_arrangement`。

```shell
python run_pipeline.py composition study work/arrangement-lesson
```

练习生成同一冻结主题的 `spacious` 和 `groove`。先看各自的 `*.patch.json`、`voicing-plan.json`，再听两份 `*-audition` 目录中的 `mix.wav`，以及原主题 `solo-source_1.wav` 和低音 `solo-new_bass.wav`。比较第 5–8 小节与第 9–12 小节，指出是哪条声部让空间变密，主句是否仍清楚。实际曲目按[编曲编辑教程](../skills/music-director/references/guide.md#编辑与试听)使用 `composition revise/render/export`，先只改一个造成问题的变量。

**母版可交付时。** 能逐段对应原录音，调性与和声取舍可追溯，主题、低音与段尾都有可听对照。留下冻结的源文件、`master.mid`、校对表、疑点、对照音频和试听结论。助听的合成音色只用于谱面判断。下一步按[游戏演奏谱](PERFORMANCE_AND_TRACK.md)制作独立改编，再进入[轨道、建筑与稳镜头](PHRASE_TO_WORLD.md)。
