# 母版制作与局部修订

## 参考体检

```shell
python run_pipeline.py inspect-source input.mid --out work/intake.json
python run_pipeline.py analyze-music input.mid --out work/music-analysis.json --backend builtin
```

读取实际文件、时长、MIDI轨道/音域、tempo/meter与控制事件；检查前奏到尾奏覆盖，数个远隔段落的速度与偏移。文件扩展名、网页标题或同长度音频不能证明版本一致。音频分轨保留统一零点，不把各轨首音裁成0。

music21后端可以提供调性、和声与声部候选；它的调性置信不是“全曲正确概率”。流行音乐中的调外音、平行运动、重复动机可能是有效选择，结合参考与听感判断。

## 转写路线

主唱和单音贝斯先考虑F0，保留帧置信、能量与分割前结果。清理八度跳变、滑音/颤音碎片、句尾与呼吸；有伴奏泄漏时，静音段的音高不一定来自主唱。

单乐器复音可用Basic Pitch等候选，再用参考声部与和声核对。缺失声部可有依据地补写，标为新增编配。一次模型失败不等于无法制作：保留可信谱、旋律和人工校正路线。

## 怎样让编曲有结构

1. 写出全曲段落和功能角色，不先追求轨道数量。
2. 保住主题旋律与可辨节奏；低音支撑和声，鼓建立律动。
3. 回答放在主读的空隙；和声不持续挤占主旋律音区。
4. 主歌、过渡、高潮在密度、音区、节奏和音色上有发展，重复段保留动机但作有目的变化。
5. 结尾写真实收束，不能把短循环复制到目标时长冒充全曲。

这不是强制音乐规则。每次修改说明希望改善的具体听感，保留原版做同段比较。

## 编辑与试听

```shell
python run_pipeline.py edit-music-region input.mid --patch edit.json --out work/candidate.mid
python run_pipeline.py inspect-source work/candidate.mid --out work/candidate-check.json
python run_pipeline.py render-preview work/candidate.mid --out work/reference.wav --mode reference
python run_pipeline.py render-preview work/candidate.mid --out work/gm.wav --mode gm --soundfont /path/to/bank.sf2
```

patch格式以学习例子及CLI帮助为准。先校验源hash与目标范围，再比较目标外事件：tempo、program、CC、踏板、音符应保持。reference模式用于基础音符审查，听感以明确音源或实际游戏为准。

## 成功与失败练习

```shell
python run_pipeline.py learn work/music-lesson
python run_pipeline.py analyze-music work/music-lesson/master.mid --out work/music-lesson/analysis.json
python run_pipeline.py analyze-music work/music-lesson/bad_octave.mid --out work/music-lesson/bad-analysis.json
python run_pipeline.py edit-music-region work/music-lesson/bad_octave.mid --patch work/music-lesson/fix_octave.patch.json --out work/music-lesson/fixed.mid
```

先不看标准答案，比较短句音区、跳进和实际试听，定位故意错八度。按范围修订，确认原来有意的跳进和目标外事件没有被“自动清理”。

学习包还提供`sound_spec.json`、`bad_shared_slot.sound_spec.json`、`sound_bank/profile.json`、`sound_bank/bad_center.profile.json`和`adaptation/events.json`，分别支持声音与编配练习。`lesson.json`记录素材事实与学习问题。

局部patch包含`schemaVersion:1`、`sourceSha256`、`beginSeconds/endSeconds`及`operations`。操作用源音符`id`并可设`pitch/velocity/startTick/endTick/remove`；新增音符由`addNotes`明确轨道、通道和tick。`endTick`是物理键释放，不是踏板延长后的声音结束。操作须落在指定范围内，工具核对控制/元事件与范围外音符未变。

另一失败是MIDI时值长但拨弦样本很快衰减。先对照源note-off，再听同段基础/GM渲染；不要只把note-off拉得更长而声称持续问题已解决。

## 退出条件

全曲结构与来源明确，note配对/控制事件无意外，冻结区未变；关键旋律、低音、长音与密集段可试听。用户认可的是具体候选和范围；结构分析通过不自动提升为艺术认可。
