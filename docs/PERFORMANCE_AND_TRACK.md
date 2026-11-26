# Minecraft 演奏谱与随谱轨道

这条路线面向已经校对过的 MIDI。先解决听起来怎样，再决定电路和空间怎样表达。保留三份成果：原始母版、Minecraft 演奏谱、实体演出世界。

## 1. 先做一段游戏编曲

先用 `analyze-music` 看主奏、低音、和声、打击、乐句和起音密度。找出 MIDI 原声依赖音量、长音或高密度叠奏的地方，试着用分槽、区别包络、薄化叠音或移开冲突的起音来表达。为主题保留音高、节奏和识别性。很密的钢琴和弦应先听两版，再决定是否只保留低音、上声部和够用的内声。音区不够时先选槽、校准根音或设计明确分区。

```shell
python run_pipeline.py arrange-game master.mid --out work/game-preview
python run_pipeline.py arrange-game master.mid --decisions decisions.json --profile bank/profile.json --out work/game-revision
```

首轮运行生成的 `arrangement-report.json` 给出真实的 `sourceMidiSha256` 与逐音 ID。编辑文件形如：

```json
{
  "schemaVersion": 1,
  "sourceMidiSha256": "换成报告里的实际哈希",
  "protectedRoles": ["theme_attack", "voice"],
  "edits": [
    {"noteId":"t3n17", "omit":true, "reason":"为句尾回声腾出位置"},
    {"noteId":"t2n8", "shiftGT":1, "reason":"让主奏先清楚起音"},
    {"noteId":"t4n3", "midi":55, "role":"chords", "reason":"调整内声位置，保留和弦功能"}
  ]
}
```

以上 ID 是示意。使用报告里的真实 ID。选择 `--routing` 时，路由应覆盖编辑后的所有保留音符及其角色。编辑结果必须绑定原始 MIDI 字节。每个编辑都需要写明音乐目的。

- `game-performance.mid` 方便在 DAW 审查落地音高和起音。采用 50 毫秒网格，原始曲速和控制器仍保存在母版。MIDI 的时值和 GM 音色只用于提示。真实尾音由游戏采样决定。
- `events.json` 是进入实体世界的触发谱。源音符、编辑后的音高/时间和最终调音都有记录。
- `arrangement-report.json` 区分作曲者写入的变动和网格量化差，列出省略理由、复音峰值和发音槽。配好校准 profile 时，另生成 `sample-preview.wav` 做同段试听。

正式项目把确认的编辑文件放在 `inputs.gameArrangement`，配套的 profile、声音包和可选显式分槽分别使用旧有的 `soundProfile`、`soundPack`、`adaptationPlan`。继续用同一个母版作为 `inputs.midi`。可玩交付会附上演奏谱和改编报告。

## 2. 用乐句决定实体轨道

可从[三段水道原创练习](../examples/track-study/README.md)开始，完整重现一版三段轨道。

```shell
python run_pipeline.py plan-track work/game-revision/events.json --out work/track-plan
python run_pipeline.py plan-track work/game-revision/events.json --design track-design.json --out work/custom-track-plan
```

随谱模式优先利用源段落标记，缺标记时在起音较少处划段。每段只为实际出现的声部分配轨道；同刻更密就划分更多独立支路，短声部的末端随该支路最后一个音截止。自动初稿根据前景声部、低声活动与段间密度变化选择焦点和空间走向。设计者可以依据乐句的情绪修订。时钟支路使用已验证的 1 GT 基本触发单元；段首脉冲由控制包调度，段内每个音的触发由实体红石完成。

把草图中的音乐意图写进 `track-design.json`，下例假设触发谱的 `musicGT` 为 320。每段含起点、不含终点，连续覆盖全曲。先选择每段重点，再决定哪些空间需要收拢、抬高或展开。

```json
{
  "schemaVersion": 1,
  "sections": [
    {"beginGT":0,"endGT":103,"label":"窄门","focus":"theme_attack","style":"copper","spread":1,"terrace":0,"turn":-1},
    {"beginGT":103,"endGT":221,"label":"涨潮","focus":"chords","style":"tide","spread":3,"terrace":1,"turn":1},
    {"beginGT":221,"endGT":320,"label":"月弧","focus":"theme_attack","style":"moon","spread":2,"terrace":0,"turn":-1}
  ]
}
```

`spread` 为 0–3，`terrace` 为 -2–2，`turn` 为 -1、0 或 1。三种造型词汇分别使用铜色阶梯、斜向潮纹和浅色弧拱。可用 `anchors` 指定某角色第一条支路的精确世界坐标，例如 `{"theme_attack":[21,117]}`。编译器会报告相邻支路、启动头和相机的空间冲突。其他支路可以同场自动规划。进一步的作品美术可通过已有 `stageModule` 合入自定义静态建筑，原有线路和镜头保护仍生效。

正式项目在 `inputs.trackDesign` 提供设计文件。新工程默认 `machine.trackMode: "score"`，老项目没有设置时沿用固定轨道。相机参数位于 `layout.camera`。布局中 `families` 在随谱模式中作为位置偏好；必须精确摆到指定位置时使用每段锚点。

## 3. 验收两份成果

1. 听审改编前后同一乐句。确认主题仍清楚，少掉或移开的伴奏确实让出空间。预听过后再用原版游戏检验尾音和距离。
2. 检查 `track-plan.json` 中每段的摆位、复音和启动时刻。相邻段和弦最密处至少各抽一个小节，检查实际机位是否能看清主体。
3. 实机用逐音日志核对地理坐标、音高和游戏刻，覆盖普通起音、段边界、密集和弦、中途停止和重新开始。独立验收声音包、镜头和静态造型。

构建后可对机器阶段导出的方块坐标生成分段等轴图，用来对照造型、方块密度和段间变化。实机仍要检查视线遮挡、运行时灯光和镜头连续性。

```shell
python run_pipeline.py preview-track placed_blocks.json --out work/geometry-review
```

当前实现提供乐句级支路变化和可编辑建筑形状。连续电气支路仍沿统一轴向推进，相机使用共享时间轴。跨段折返、自由三维布线和非常高的复音仍需另外设计和实测。
