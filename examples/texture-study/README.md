# 轻声部织体原创练习

```shell
python run_pipeline.py texture-study projects/texture
python run_pipeline.py run projects/texture/base
python run_pipeline.py run projects/texture/layered
```

第一条命令生成 16 秒原创乐谱、七槽声音包、两个项目和试听。使用 `.[production]` 即可离线生成，构建两份世界还需 Node 24。谱与合成采样为 CC0-1.0。

- `base.wav` 是旋律、和声、低音和底鼓。
- `layered.wav` 保留这四层，再放入换和声时起的底色、句尾的弱答与后半段的刷声颗粒。
- `texture-only.wav` 只播放新声部，沿用同一增益。三份 WAV 是离线采样预听。混合对照能检查新层是否喧宾夺主，独奏对照能查出是哪一层在影响它。

`study.json` 报告保留的音符、同刻起音峰值和各试听文件。后两条命令生成可以在 Minecraft Java 1.21.1 打开的两个世界。各自的 `USAGE.md` 提供开始和重置命令。若要判断实际空间和响度，请在同一机位录两个世界。普通音符盒试听可使用原版客户端，资源包内生效的样本随世界提供。

练习目标是让背景有流动感，仍能轻松追踪旋律。可以试听后在副本里移动一个回声、缩短一个拖尾或调整一个槽，保留基线供下一轮比较。
