# 证据矩阵与交付

## 五种状态

| 证据 | 可以证明 | 不能替代 |
|---|---|---|
| 静态读回 | MIDI/事件/方块/ZIP与hash一致 | 实体实际发声、画面或听感 |
| 服务端正常速度运行 | 电路逐音、加载/复位和相机目标 | 客户端平滑、声音包真的启用 |
| 实际客户端 | 画面、声音、光影、清理与性能 | 用户艺术认可、录制编码负载 |
| 用户听看 | 指定版本/范围的主观认可或修改需求 | 其他版本、未看的段落 |
| 实际成片 | 录制文件音画、字幕和结尾正确 | 外部投稿成功 |

每条证据带输入hash、方法、覆盖范围、结果与局限。音频未传给模型就不能写它已审听；隐藏静音客户端可以是渲染测试，但听感仍待验证。

## 核对顺序

```shell
python run_pipeline.py status projects/my-song
python run_pipeline.py handoff projects/my-song
python run_pipeline.py run projects/my-song --until validate
```

确认独立回读的是实际导出字节。真实日志来自当前副本，不是旧缓存；完整播放、中止、重播、保存重进分开写。切片验证不得提升为全曲通过。

## 用户反馈记录

复制[review模板](../../../templates/review.example.json)，换成实际文件路径/hash和用户原意。`reviewer.kind=user`必须附真实`userFeedback`；不要推断用户没有说过的认可。

```shell
python run_pipeline.py review projects/my-song --file work/review.json
```

工具记录归属声明和有效性，不自动授予技术stage pass。改声音、时间、布局或视觉后，旧反馈只对未改变的输入/范围保留。

## 录制

把最终游戏设置、样本包、光影/纹理和客户端版本冻结。先录主读/密集段20–30秒，检查设备、真实音源、实际帧缓冲、字幕、掉帧和编码负载。使用OBS时WebSocket可控制录制，其他工具可导入实际文件；不依赖某个宿主的桌面插件。

完整录制后用ffprobe读取音/视频流、时长与编码；用FFmpeg检测疑似黑帧/静音，再人工检查疑点和头尾。这些检测可能把有意休止/黑场标出，按作品语义解释。

用户自行录剪时交付设置与检查清单，等收到实际成片后才能标“已审查成片”。没有拿到文件就写清交接状态。

## 成功与失败练习

原创demo完整构建、静态验证后尝试导入一份`method=static`的review：它不能成为用户听审。改动目标文件一个字节，再查看handoff，旧review应标过期。修复方式是重新验证/听看当前候选，不改旧hash掩盖变化。

另做一次中途停止和完整重播，检查音乐/粒子/字幕的残留。记录两个不同run的输入与结果，避免只选成功截图。

## 交付清单

媒体工具：`inspect-media movie.mp4 --out media.json` 读取真实流/时长/hash；`clip-media movie.mp4 --out sample.mp4 --begin 12 --end 20` 实际编码片段；`capture-evidence PROJECT movie.mp4 --out PROJECT/evidence/capture.json --kind full` 绑定当前候选与媒体。这些子命令均使用 `python run_pipeline.py` 前缀。它们不启动 OBS、不证明媒体来自游戏、不授艺术认可；实际来源与同步须听看核对。

世界与投影、辅助数据包、声音包、必要客户端JAR、使用/安装说明、版本与来源、文件hash、认可范围、实测/录制证据、已知问题。按明确白名单打包，不把来源录音、旧实验、凭据、缓存或整套游戏本体塞进交付。

退出时另一个agent或操作者应能按说明在独立实例开始/停止/重播。软件发布、作品录制和投稿是不同事实，分别记载。
