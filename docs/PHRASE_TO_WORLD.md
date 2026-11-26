# 从乐句到轨道、建筑与稳镜头

从已试听的 Minecraft 演奏谱开始。需要 `events.json`、生成它的母版与改编决策，以及试听用的声音 profile 和资源包。拿到的仍是音乐母版时，先做[游戏演奏谱](PERFORMANCE_AND_TRACK.md)。这篇会把可听的声部和乐句落实为空间位置、建筑轮廓和观看路线，再核对实体电路和原版跟拍。

## 1. 把乐句写成可以布置的表

在同一时间轴上并排看 `arrangement-report.json`、`events.json` 和采样试听。用事件的 `family`、起音位置和最密刻理解每段先后关系。`musicGT` 是演奏长度，20 GT 为 1 秒。涉及截段的谱使用局部 `q`，或者从绝对 `gt` 减去 `sourceOffsetGT`。段界按局部时间写入设计文件，前闭后开。

每段写四项：起止刻、观众先听和先看的声部、结构如何变化、从哪里观看。先确认分句真正跟音乐发展，再参考自动方案。单拍鼓点稀疏可能只是切分，适合做段界的位置要结合主题呼吸、和声与新段进场判断。

《烟袋斜街 · 灯巷》的四段源自实际 20.6 秒游戏谱。上半部放主题、声乐和轻声部，下半部主要放低音与鼓，机位从中间通过。

| 局部 GT | 重心 | 做成怎样的空间 |
|---|---|---|
| 0–96 | 主奏进入 | 低檐和暖色灯框收拢入口，左侧主奏首支路为 `[29,116]` |
| 96–192 | 短回声与主题轮答 | 主奏移到右上 `[51,124]`，回声在右侧较低的 `[51,108]`，第二层檐口让上下层能同时被看到 |
| 192–288 | 主题重新展开 | 中部加宽，压低桥廊地面，减少中间遮顶，留出更长视线 |
| 288–412 | 声乐与尾音 | 收窄门架、灯色逐步转浅，终门留在远处承接尾音 |

这些是具体作品的决定。新曲目优先按自己的主题与声部重心画截面。乐句换段可用轮廓、材质、光源和开合表达，镜头保持稳定。

## 2. 先做实体布轨，再画建筑

以下原创 16 秒练习自带素材、改编决策和三段设计，可逐步照做。命令在包根目录用制作环境运行，输出目录应为新目录。

```shell
python run_pipeline.py texture-study work/waterways
python run_pipeline.py arrange-game work/waterways/layered.mid --decisions examples/track-study/waterways-arrangement.json --profile work/waterways/sound-bank/bank/profile.json --out work/waterways/game
python run_pipeline.py plan-track work/waterways/game/events.json --out work/waterways/automatic
python run_pipeline.py plan-track work/waterways/game/events.json --design examples/track-study/three-waterways.json --out work/waterways/designed
```

打开两份 `track-plan.json`。对比 `sections[].focus/peakStarts/lanes`，逐段看每条支路的 `family`、`x/y`、`launchGT`、`lastGT`。设计稿应有三段，段界是 103、221 GT，游戏谱有 **105 个起音**。这些数字用于确认读到了同一份练习。然后对照哪一层是主奏、哪一层是伴奏、宽处是否真服务于声部交接。

想固定某角色第一条支路时，在该段的 `anchors` 写绝对 `[x,y]`。先摆主奏、重要回答与低声部，再让其余角色自动放置。预览命令给出初稿。若工程设置了自定义相机或全曲位置偏好，最终以实际机器阶段的 `track-plan.json` 为准。

### 报「no isolated lane」时怎么改

错误会指向乐句和声部。先把问题乐句与前一段摆在同一横截面查。新启动头约从 `beginGT + 11` 的纵向坐标开始，旧支路的保护可持续到约 `lastGT + 87`。所以音乐上两句已经交接时，两组线路在空间仍可能重叠。纵向重叠时，若横向差小于 11 格且高度差小于 8 格，当前规划器拒绝该位置。入口平台和相机附近还有独立保护。

《灯巷》初排在第 2 段的回答声部报错。实际修法是给相邻段安排交错的左右和高低层，把主奏、回答、回声、低音和打击一起明确分配，再检查同一截面。294 个起音完整保留。自己遇到这个问题时，先试移动锚点、垂直错层或改变前后段摆位，每次改完重看两段。只有空间确实无法容纳、且试听支持精简时，才回到游戏编配，说明删减或调整的音乐理由。

## 3. 从一榀构件开始搭场景

先选一个要解决的观看问题。例如“进入第一句时近处有屋檐，但能透过门架看到主奏”，画一张横截面和一段纵向草图，写清近景框架、中景音符盒、远景焦点。再用第一榀构件验证比例。练习的 [建筑蓝图](../examples/track-study/canal-stage.json) 使用 `fill` 铺设宽度不同的地面，用 `frame` 架出不同跨度的门架，再在檐下放灯，三段的轮廓与材料都发生变化。

```shell
python run_pipeline.py preview-stage examples/track-study/canal-stage.json --out work/waterways/stage-preview
```

先看俯视与侧视，对照地面宽度和门架错落。这个预览只读蓝图，未自动合入实际机器。把蓝图写进 `inputs.stageModule` 后，构建器才用实际机器检查同格覆盖、音符盒基座和头顶空气、红石邻域与相机净空。读机器阶段的 `stage_module_report.json` 及报出的冲突坐标。碰撞时先移动、升高或重画整榀，避免删掉几块承重边缘留下破碎门架。只搭一榀时缩小视距看近景，确认停拍时也看得清，然后再跨段重复或变化。

## 4. 接入稳镜头和世界工程

打开 `work/waterways/layered/project.json`。保留样例已有的 MIDI、声音 profile 与资源包设置，只合并下面各项。路径以 **project.json 所在目录** 为基准，也可以写绝对路径。示例路径假定工作目录正是 `work/waterways/layered`。

```json
{
  "inputs": {
    "gameArrangement": "../../../examples/track-study/waterways-arrangement.json",
    "trackDesign": "../../../examples/track-study/three-waterways.json",
    "stageModule": "../../../examples/track-study/canal-stage.json"
  },
  "machine": {"trackMode": "score", "decorate": false},
  "visuals": {"enabled": false}
}
```

把 [稳镜头完整配置](../examples/track-study/steady-camera-layout.json) 的整个 JSON 对象作为顶层 `layout`。这条轨中央向前，朝向与俯仰始终一致，中段仅缓升再回落 1.5 格。关键帧从 -20 GT 到 `musicGT+20`，相邻至少 12 GT。换曲时重算终点与乐句时间，先定统一的朝向与俯仰。跟拍整体沿 +Z 前进。要换景别，优先用场景开合和少量平移，避免逐句摇头、点头或反复回正。

两侧音符盒出画时，可在有关键帧的 `layout.camera` 中填写 `followBack`，让镜头相对演奏线后移 0–16 格。音乐时间和镜头速度照常。后移会改变距离与近景关系，要重新检查净空、实际画面和音量平衡。

```shell
python run_pipeline.py run work/waterways/layered
python run_pipeline.py status work/waterways/layered
```

从 `state.json` 的 `stages.machine.artifact` 取得当前机器产物目录。用里面的 `placed_blocks.json` 运行 `preview-track PLACED_BLOCKS --out work/waterways/assembled-view`，检查组装后的段落，不用建筑单件图替代。读 `build_manifest.json` 的 `camera.rail`，确认关键帧和预期一致。若报 `Camera clearance conflict`，按报出的刻和方块坐标找到障碍。先修构件位置或机位高度，再预览整段。

在 Windows 上，若错误指向临时文件替换 `state.json` 并报 `WinError 5`，先等其他读取程序关闭，再重跑同一 build 命令。已保存的阶段可复用。若重复出现，按[诊断路线](TROUBLESHOOTING.md)保留错误和最小复现。

**故意失败练习。** 在蓝图副本的 `operations` 末尾加 `{"op":"set","pos":[37,112,145],"block":"minecraft:smooth_quartz"}`，将 `inputs.stageModule` 指向这个副本再构建。这个位置在跟拍通道内，应被拒绝。移除测试块、恢复原蓝图后复查组装成功。单件预览成功仍可能在机器合入时失败。

## 5. 在游戏内检查三个层面

1. **现场构图。** 从构建输出的 `releasePath` 取 ZIP，按其 `USAGE.md` 把 `world` 作为新世界复制到 Java 1.21.1 的 `saves`。确认声音包已加载，按说明开始。在每个乐句看最近构件有没有切进画面、主奏是否被上一层支路遮住、远处主体是否可辨。尤其看连续播放有没有左右摆头或高度突然跳变。单帧和服务端坐标都无法反映移动观感。
2. **实际演奏。** 有服务端工具时，按 [PIPELINE 的服务端重播部分](../PIPELINE.md) 接入独立 Java、服务端与观察器，用当前工程核对 `expected_events.json` 和 `runtime_validation.json`。原版客户端检查声音没被空间距离压没、停止后没有新声音、等待复位后能再播。建筑或机位改变后重听原机位和新机位的主奏/伴奏比例。
3. **可交接的结果。** 代表段交付存档、资源包、开始和停止方式、校对过的轨道/相机配置，以及哪些阶段实际看过或听过。若只能离线预览，记录几何检查范围与仍需实机验证的问题。用户确认轨道与跟拍后，再用同一设计原则扩展所需长度。

需要把机位反馈交给别人时，用 OBS 或现有录屏器录一条连续跟拍，先试录确认实际游戏画面和声音都进轨。保留同一视距、视野角和资源包。用 `python run_pipeline.py inspect-media take.mp4 --out work/waterways/capture-check.json` 检查流和时长，再回放标记出现问题的秒数。例如近处拱架遮住主奏时，先把构件移出视轴，或缓慢向外移机位，再录同一段比较。仅验证坐标或导出构图时，将证据记为几何预览。

需要判断半格偏移、停播残留、休止段暗或录屏掉帧时，查[制作判断与复查](PRODUCTION_DECISIONS.md#4-世界静态检查通过后看完整的移动镜头)，那里列了这几种问题的实战排查。
