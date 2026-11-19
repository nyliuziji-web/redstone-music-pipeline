# 可调音色、资源包与声音路由

## 先把听感目标写成可比较的变量

对每个角色写一行：它承担什么音乐信息、必须听清什么、用哪个独立声音槽、目标音域、短起音或持续、谁要让位。例如主题保留音高/节奏轮廓，木质短攻击保留MC颗粒，圆润音体避免高音变尖；pad降低起音锐度并缩短跨和弦尾巴。不能用“所有音色都更真实”代替角色设计。

先做3个方向：偏原版/MC-inspired、混合、音体主导。在相同音符、机位与声部增益下听差异，再决定方向。现成示例只证明工具能力，不自动成为用户作品的音色。

## 直接可运行的练习

命令前缀均为`python run_pipeline.py`，使用项目生产依赖环境：

```shell
python run_pipeline.py design-timbre examples/timbre-study/vowel_recipe.json --out work/vowel-v01
python run_pipeline.py build-palette examples/timbre-study/palette_spec.json --out work/palette-v01
python run_pipeline.py plan-noteblocks examples/timbre-study/master.mid --profile work/palette-v01/bank/profile.json --out work/planned
python run_pipeline.py audit-palette work/palette-v01/bank/profile.json --events work/planned/events.json --out work/range-audit.json
python run_pipeline.py compare-timbres examples/timbre-study/master.mid --palette examples/timbre-study/palette_spec.json --out work/timbre-comparison
python run_pipeline.py timbre-study work/full-timbre-study
```

输出目录必须是新目录。`build-palette`返回实际`profile`和`soundPack`路径，先读返回值，不推断哈希目录。工具不会安装模组、下载音源或寻找Nevada文件。

20秒练习的主旋律范围61–82、统一根音72，调音值为1–22；不是逐音换乐器。包含独立主旋律、元音长音、和声、低音与鼓。`comparison/`有三套完整预听和每个声部独奏；`sustain_comparison.json`另比较同一短持续样本的自然尾音与补触发。原始MIDI与声音样本都保留。

## 配方格式与可调参数

一个独立单音配方：

```json
{"schemaVersion":1,"kind":"vowel","rootMidi":72,"seconds":2.8,"gain":0.17,
 "attackSeconds":0.018,"releaseSeconds":0.12,"brightnessHz":6500,
 "formants":[700,1220,2600],"attackWeight":0.16,"bodyWeight":0.84}
```

支持wood、pluck、sustain、bass、vowel、bell、kick、snare、hat。参数作用：

| 问题/目标 | 先试的变量 | 不能据此推断 |
|---|---|---|
| 主题起音不易辨 | attackWeight、attackSeconds、短木质/拨弦攻击 | 越尖越好；原曲旋律错误可由起音掩盖 |
| 类元音持续音 | formants、持续音体、释放与音区 | 有歌词、复刻原唱或真实无限循环 |
| 高音刺耳 | brightnessHz、谐波构成、音体/攻击比例 | 简单低通一定优于重新配器 |
| 低音糊 | decaySeconds、低音/底鼓分工、槽位增益 | 单独归一化低音就解决混音 |
| 尾音跨和声 | seconds、releaseSeconds、织体稀疏度 | 延长MIDI note-off会改变原版声音尾音 |

`gain`是配方的目标单音峰值；合成阶段在混音前按这个目标烘焙。它不是游戏逐音velocity。配方层会去DC、首尾淡入淡出，并输出来源、参数与哈希；整个混音/独奏组才共享一个安全增益，不会分别抬高弱声部的独奏。

可显式加入本地单音，而非只能使用内置合成：

```json
{"schemaVersion":1,"kind":"sustain","rootMidi":72,"seconds":1.4,
 "gain":0.18,"attackWeight":0.2,"bodyWeight":0.8,
 "attackSample":{"path":"local/attack.wav","rootMidi":66,"license":"operator-recorded source rights"},
 "bodySample":{"path":"local/body.wav","rootMidi":72,"license":"CC0-1.0"}}
```

路径相对于配方文件；每层注明实际采样根音与来源权利。可以设startSeconds、seconds和gain选择单音区域。工具按声明根音重采样，不替用户证明声明正确；立体声显式下混并在报告记录。不把一整段原曲塞进一次触发的样本冒充逐音还原。

## 从角色配方到资源包

palette在原有profile的slots里使用`recipe`，其余仍是instrument/baseBlock/rootMidi与sustain。角色→槽位用roles表。`build-palette`先保存每个配方及来源，再生成能被现有`plan-noteblocks`、`sound`阶段和采样试听使用的profile/resources.zip。

同一声音事件不能承担两个独立增益/包络目标。主旋律与pad共用flute时，改flute样本会同时改两者；先分槽，再讨论提升哪一层。槽位不必与GM program一一对应。

当前标准稳定底座：harp/dirt、bass/oak_planks、guitar/white_wool、flute/clay、bell/gold_block、chime/packed_ice、xylophone/bone_block、iron_xylophone/iron_block、cow_bell/soul_sand、didgeridoo/pumpkin、bit/emerald_block、banjo/hay_block、pling/glowstone、basedrum/stone、snare/sand、hat/glass；方块使用minecraft命名空间。其他同材料方块没有自动视为已验证。

## 25格校准和长音策略

倍率为`2^((note-12)/12)`，note=12为样本原速。根音72的样本覆盖60–84；最低音比中心音慢一倍，最高音快一倍，样本长度同步变化。`audit-palette`实际解码并重采样全部25格，给出音高候选、长度与95%能量时间；强泛音/共振峰可使频谱最高峰不是基音，不能只凭一个cents数判错。

长音短缺时，分开比较：换更长/更平稳的样本；增加独立持续层；少量补触发。补触发间隔参考实际音区和包络，不抄固定5/6GT。示例按根音95%能量时间派生一个候选间隔，明确不是全音区最优值；实际检查新起音颤动、幅度堆积与机器事件成本。

工具会把持续不足、相邻样本尾音重叠列为疑点。和弦重叠有时有意，短拨弦本来就应衰减，不能把每条风险都当自动修复指令。原版不按note-off停音，SF2的loop、踏板和释放也不会自动进入一次性OGG。

## 怎样听审和定位问题

先听相同增益的主旋律独奏，再听完整混合，再检查实际移动跟拍。旋律不清可能是攻击弱、频段遮盖、共用槽或距离；不是只有“加3dB”。同时保留相同谱/增益组与另行等响A/B，避免只选更响版本。

`compare-timbres`不自动做LUFS匹配。其所有solo与mix共用一个安全系数，可以检验solo相加是否等于mix。没有明确提供原版单音时，native标签下是原创MC-inspired合成，不是stock Minecraft。三套音色都不是真实游戏录音或空间声场证明。

优先覆盖：主旋律长音、复杂高潮、低音/鼓、角色交接与结尾。每轮说明改变哪些参数、预期听到什么、哪些声部保持不变。完成游戏录音后绑定准确profile/资源包/hash与机位，再记录用户意见。

## 退出条件

音色、音高/尾音与角色关系有可听对照；资源包可解码且槽位清楚；源与新增材料可追溯；未涉及声部没有被连带修改。工具检查不授予艺术认可；实际游戏资源加载、移动声音、补触发与停止重播分别验收。
