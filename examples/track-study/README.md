# 三段水道

这个设计使用原创织体练习的 16 秒有织体 MIDI。前段的铜门收拢视线，中段把和声引到较开阔、斜向的潮纹，末段用稀疏的浅色月弧把视线交还主题。两个段界落在奇数刻，便于检查每段的局部奇偶与全曲时间是否一致。

[完整教程](../../docs/PHRASE_TO_WORLD.md)还会使用本目录的建筑蓝图与稳镜头配置，讲解如何处理施工冲突和实机复查。

```shell
python run_pipeline.py texture-study projects/waterways
python run_pipeline.py arrange-game projects/waterways/layered.mid --decisions examples/track-study/waterways-arrangement.json --profile projects/waterways/sound-bank/bank/profile.json --out projects/waterways/game-preview
python run_pipeline.py plan-track projects/waterways/game-preview/events.json --design examples/track-study/three-waterways.json --out projects/waterways/layout-review
```

把轨道设计与演奏谱编辑文件的实际路径填入 `projects/waterways/layered/project.json` 的 `inputs.trackDesign` 和 `inputs.gameArrangement`。练习文件删减一个底鼓、把一颗内声错开一刻。可另建对照目录，省略 `--decisions`，比较哪里听见回声或听清内声。修改 MIDI 后按[演奏谱教程](../../docs/PERFORMANCE_AND_TRACK.md)用新谱重新核对音符 ID 和 SHA-256。运行 `python run_pipeline.py run projects/waterways/layered` 得到可玩世界。

试着只改第二段的焦点、宽度或一个锚点，查看支路是否合理重排。若布局偏向高密度，检查相邻支路同时存在时的净空。最后在原版客户端实际对比两份世界，选一段录下俯视与跟拍的区别。
