# 环境准备与能力核对

## 支持主线

集成包以Windows x64、Python3.12、Node24 LTS、Minecraft Java1.21.1、JDK21、Fabric为制作基线。离线工具也在Linux测试；平台或模组标签不能替代本机实际探测。

```shell
python --version
node --version
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[production]"
.venv\Scripts\python.exe run_pipeline.py capabilities --probe
```

以实际`pyproject.toml`和`--help`为准；可选能力未安装时，报告应给出原因与下一步。不要在使用中的游戏实例里试装新依赖。

Linux使用`.venv/bin/python`。其余教程中的`python`表示这个独立环境的解释器，不要求激活脚本或改动全局安装。若系统Python仅是商店占位符，先使用操作者已安装的实际Python3.12路径创建环境。

也可使用 `uv venv --python 3.12 .venv` 与 `uv pip install --python .venv/Scripts/python.exe -e ".[production,pitch]"`。uv 创建的环境可能没有 pip，这是正常情况；继续用 uv pip，或显式执行 `python -m ensurepip`。开发包构建另装 `.[dev]`；Skill 官方格式校验另需 PyYAML 并在 Windows 使用 `python -X utf8`。首次 librosa 分析可能进行本地 JIT 编译。

## 能力等级

| 等级 | 需要什么 | 能证明什么 |
|---|---|---|
| 离线核心 | Python、Node、NBT/数组依赖 | 解析MIDI，构建与独立回读世界/投影 |
| 音乐/声音工具 | 分析、音频库、FFmpeg；GM模式另需SoundFont | 分析、局部编辑、合成/采样试听、比较与声音包检查 |
| 服务端验证 | 合法服务端、JDK21、明确测试副本/观察器 | 实体电路实际触发、停止和重播 |
| 客户端验证 | 可运行的合法客户端/账号、图形与音频、Fabric和本项目模组 | 画面、相机、资源加载、真实听感与录制 |
| 可选后端 | 具体模组/模型和它的依赖profile | 只证明已探测的能力；不提升其他等级 |

模块能import不等于后端能正常渲染。记录探测的输入、可执行路径、工具/资源版本、hash和局限。

## 游戏目录与Java

```shell
python run_pipeline.py game inspect /path/to/isolated-instance --java /path/to/jdk21/bin/java
python run_pipeline.py game import /path/to/isolated-instance --out projects/game-runtime --java /path/to/jdk21/bin/java
```

路径使用操作者实际位置。Windows可加双引号，不把示例路径当作固定目录。检查同JDK的`javac`和`jar`；PATH可能仍指向旧Java。

导入已有合法实例不代表自动完成登录或同意游戏条款。用操作者正常启动器确认最小实例能进入独立测试世界，再接作品。运行器只管理本任务创建的进程和副本。

客户端源码按标准Gradle/Loom项目构建，先读该目录的实际帮助与配置：

```shell
python run_pipeline.py game build-client client --out projects/client-build --java /path/to/jdk21
```

编译通过只说明产出JAR，仍需实际客户端播放、关闭、重播和卸载检查。缺少游戏环境时保留离线成果，状态写到已完成层。

## 声音资源

GM 试听使用显式指定的 SoundFont，本项目以 SF2 实测。首次加载要检查程序音色、鼓组、踏板和尾音。生产依赖可直接安装；GM 支持独立 FluidSynth 程序，也可另装 `.[render-tiny]` 使用 TinySoundFont。Windows 上如果后者缺 wheel 或要求 C 编译器，使用 FluidSynth 预编译版。

- Windows x64 可解压到作品外的自管工具目录。验证过 [FluidSynth 2.6.2 Win10 x64 cpp11](https://github.com/FluidSynth/fluidsynth/releases/download/v2.6.2/fluidsynth-v2.6.2-win10-x64-cpp11.zip)，ZIP SHA-256 为 `808295345d43c9c428f3fa87d29fbf97a9926f356df95559ff2689f3bd4072d7`。保留 bin 下的配套 DLL。
- Linux 可以使用发行版的 FluidSynth 命令。已在 PATH 时，`--gm-engine fluidsynth` 即可选择它。
- 可用音源为 [GeneralUser GS 的固定版本](https://github.com/mrbumpy409/GeneralUser-GS/tree/684543d5e5efaef08d02be50dcda8d552478fa60)，`GeneralUser-GS.sf2` SHA-256 为 `9575028c7a1f589f5770fccc8cff2734566af40cd26ed836944e9a5152688cfe`。保留上游独立许可证。此音源供 GM 试听，游戏采样另选来源。

```shell
python run_pipeline.py render-preview examples/demo.mid --out work/gm.wav --mode gm --soundfont work/GeneralUser-GS.sf2 --fluidsynth work/FluidSynth/bin/fluidsynth.exe
```

转写环境按[本机音频后端](../integrations/transcription/README.md)单独配置。报告 `audio capabilities` 用于检查包和解释器。模型是否已成功运行以实际候选和运行记录为准。

音符盒模式使用profile中声明的单音样本；样本根音、声音事件、基底和方块note共同决定实际音高。MC原版资源从合法本地实例取得，第三方音源按各自条款使用；原创学习样本单独声明来源。

## 可选组件

有合格MIDI就不安装转写模型；有分轨就先使用分轨。Basic Pitch、分离模型、扩展音符盒、Photon等放独立环境或profile。锁定具体JAR元数据与传递依赖，不对整个工作包执行“全部升级到latest”。

Iris/Sodium、光影和材质属于作品呈现profile。先同机位抽测无光影/目标光影，再测试录制负载；不凭显卡型号承诺帧率。

## 第三方技能参考

包内保存了[固定提交的Minecraft技能参考](../skills/_upstream/minecraft-agent-skills/provenance.json)，四份原始文本与MIT许可证一起提供。它们是只读学习资料，未注册到全局宿主；正文可能包含26.x示例和指向上游仓库的相对路径。按1.21.1选择内容，使用当前API查证后再实施。
