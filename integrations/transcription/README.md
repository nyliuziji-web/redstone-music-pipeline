# 本机音频后端

把音频模型装进单独的 Python 3.12 环境。主环境以 `audio … --python PATH` 运行固定的后端命令。先选择最短能暴露问题的 20–30 秒，已有可信 MIDI 就直接进入编曲。

以下是 Windows 路径。Linux 将 `Scripts/python.exe` 换成 `bin/python`。首先创建环境，装单乐器复音候选工具。

```shell
python -m venv .audio-venv
.audio-venv/Scripts/python.exe -m pip install "basic-pitch[onnx]==0.4.0" "soundfile>=0.13,<0.15"
python run_pipeline.py audio capabilities --python .audio-venv/Scripts/python.exe
python run_pipeline.py audio transcribe work/sample.mp3 --python .audio-venv/Scripts/python.exe --out work/basic
```

[Basic Pitch](https://github.com/spotify/basic-pitch) 可从混音提出复音音符，但无法说明哪个乐器发出哪个音。结果目录有未经合并的预测、MIDI、时间定位疑点以及模型版本和哈希。幅值字段是模型输出的幅值，不能当作正确概率。单声部人声或贝斯可另跑 `transcribe-melody`，比较起音、尾音、跨八度和伴奏泄漏。

## 节拍和分轨

如需节拍，把 CPU 版 PyTorch 装到音频环境，再装 [Beat This!](https://github.com/CPJKU/beat_this)。

```shell
.audio-venv/Scripts/python.exe -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.9.1 torchaudio==2.9.1
.audio-venv/Scripts/python.exe -m pip install "beat-this==1.1.0"
python run_pipeline.py audio beats work/sample.mp3 --python .audio-venv/Scripts/python.exe --checkpoint small0 --model-dir work/models --allow-download --out work/beats
```

后续使用首次结果里给出的本地 checkpoint 路径，省略 `--allow-download`。查看强拍位置、半速/倍速、拍号和段尾是否合理。时间戳从输入录音的零点计算。录音若截自全曲，另记起始秒数。候选 BPM 用于判断节拍，制作母版须保留实际节奏和出处。

混音中人声与伴奏互相干扰时，另用独立环境安装 [audio-separator](https://github.com/nomadkaraoke/python-audio-separator) 的 CPU 版，并准备 FFmpeg。Windows CPU 用户可查阅上游的 PyTorch 安装说明，避免顺带安装 GPU 构建。

```shell
python -m venv .separation-venv
.separation-venv/Scripts/python.exe -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.9.1 torchaudio==2.9.1 torchvision==0.24.1
.separation-venv/Scripts/python.exe -m pip install "audio-separator[cpu]==0.44.2"
python run_pipeline.py audio capabilities --python .separation-venv/Scripts/python.exe
python run_pipeline.py audio separate work/sample.wav --python .separation-venv/Scripts/python.exe --model UVR-MDX-NET-Inst_HQ_3.onnx --model-dir work/models --out work/stems
```

`work/models` 事先建立。选择并准备有明确使用条款的权重。若决定由上游下载指定模型，显式加 `--allow-download`。离线复用需保留同目录的 `download_checks.json`、`mdx_model_data.json`、`vr_model_data.json` 和权重等上游实际下载文件，另一个架构可能需要额外配置。示例的 Windows CPU 路线已分别实测首次下载和缓存离线分离。两轨模型只尝试区分人声与伴奏。核对两轨时长、零点、分离延迟及漏音，再只对需要恢复的声部转写。已提供原始分轨时优先使用原分轨。

MuScriptor 接口接受操作者提供的本地 `.safetensors`，并通过 `--backend muscriptor --model PATH` 启用。需按[上游项目](https://github.com/muscriptor/muscriptor)配置环境，权重受单独的非商业条款限制。此后端未纳入已验收的默认链路。

## 对照

```shell
python run_pipeline.py audio compare work/sample.mp3 work/basic/result.json work/revised.mid --begin 0 --end 20 --soundfont work/bank.sf2 --out work/check
```

按同一时间轴播放 `original.wav`、各 `candidate_N.wav`，也可在左右声道同时定位差异。可加 `--fluidsynth PATH` 指定独立程序。优先核对旋律、低音与强拍，比较候选间音高/起音分歧。短于参考的候选会把后段留在原时间轴，报告中标出末音位置和谱面时长差。参考录音没有对应的真值谱时不报告准确率。
