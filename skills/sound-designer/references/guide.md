# 声音设计、校准与路由

## 制作次序

先用拨弦、持续、低音和打击等不同角色测试，不一开始做整套128种GM音色。选择或合成样本后去无意义空头，保留有用攻击和释放，检查直流、削波、尾部点击和无意静音。

定位音效使用可解码的单声道OGG Vorbis。每个样本记录来源、加工、sha256、采样率、根音、时长、峰值及包络；替换同一个原版sound event会影响所有使用该事件的音符盒。

## 音高校准

当前 profile 接口只接受每种原版乐器的标准稳定底座，避免声明乐器与实体更新后的乐器不一致：harp/dirt、bass/oak_planks、guitar/white_wool、flute/clay、bell/gold_block、chime/packed_ice、xylophone/bone_block、iron_xylophone/iron_block、cow_bell/soul_sand、didgeridoo/pumpkin、bit/emerald_block、banjo/hay_block、pling/glowstone、basedrum/stone、snare/sand、hat/glass。标识均用 minecraft 命名空间。相同材质的其他方块没有自动视为受支持；扩展时先核对目标游戏注册与实际触发。

常见原版倍率为`2^((note-12)/12)`，`note=12`对应样本基准速度。有效音高还受样本根音、sounds.json附加pitch与模组偏移影响。先测单音再测低中高；升一八度时样本时长减半，降一八度加倍，检查持续策略是否仍适用。

SF2试听器的踏板、循环和note-off是参考音源行为，不是单音OGG自动支持的行为。持续样本太长会糊和声，太短或频繁再起音会颤动；在实际乐句上比较。

## 可执行例子

```shell
python run_pipeline.py build-soundpack templates/soundpack.example.json --out work/sounds
python run_pipeline.py plan-noteblocks input.mid --out work/adaptation --profile work/sounds/profile.json
python run_pipeline.py render-preview work/adaptation/events.json --out work/mix.wav --mode noteblock --profile work/sounds/profile.json
python run_pipeline.py compare-candidates work/baseline.wav work/mix.wav --out work/comparison
```

声音规格中的`synthesis`生成原创学习音色，也可按工具格式指定自己的样本。用户曲目最终音色应另做候选，学习合成音不自动符合其审美。

## 混音判断

先听主旋律自身，再听完整混合，最后检查移动跟拍。旋律不清可能是其采样缺乏起音、频段遮盖、共用槽、位置/距离或实际增益，不只有“加3dB”一种办法。

保持独奏采用完整混合中的同一增益；A/B在相同时间、相同音乐、相同位置与补触发下比较。响度匹配保留真峰值余量并记增益；不单独归一化每个stem破坏相对平衡。指标发现问题，听感决定取舍。

## 成功练习

运行上面的声音包例子，对lead、pad、bass、鼓分别渲染短句。检查ZIP根、sounds.json引用与replace、样本解码和根音；读回校准报告。独立角色可调整且其他角色不被连带修改。

## 故意失败练习

把一个槽的`rootMidi`误设高一个八度，渲染同段并测/听；应该定位为中心音/profile错误，不去改母版所有音符。另将旋律/pad映射同槽，确认路由联动后分离。每次修复保持未涉及文件hash不变。

## 退出条件

声音包能解码、所有引用存在、样本与profile一致；根音/持续策略和槽位路由有证据，混合不削波、主读可辨。服务器触发与实际启用资源包录音另验；尚未进入游戏时明确写采样近似。
