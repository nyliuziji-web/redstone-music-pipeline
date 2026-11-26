# 从参考图到可走进的 Minecraft 街道

建筑模块接收曲目主题、现有轨道、玩法路径和实际镜头。它应交付场地方案、可改的构件、两种布置的对照，以及能经过机器保护检查的阶段蓝图。此处以北方砖木胡同为练习，其他风格可换参考、柱网、屋面和材质。

## 1. 看参考，画街道，再画房子

1. 找同一地区的两类参考。用街道照片看街宽、檐高和铺面收放，用侧面或背面看屋坡、山墙、柱网与门窗深度。《烟袋斜街》可以从青砖灰瓦、连续小铺和折向银锭桥的街巷关系入手。先拟代表段的空间焦点，再选零件。把来源和可再分发许可写进项目记录。[西城区修缮记录](https://xcszb.bjxch.gov.cn/xxxq/pnidpv347124.html) · [实景照片目录](https://commons.wikimedia.org/wiki/Category:Yandai_Xiejie)
2. 从机器产物取 `placed_blocks.json`、`expected_events.json` 和 `build_manifest.json`。按[布轨教程](PHRASE_TO_WORLD.md)写三处关键帧，通常选街口、独奏和密集交接。在俯视图标记街面对镜头的入画方向、音轨、维护范围、路中心和门朝向；同时画一张横切面，找出路面、屋檐、屋脊、主奏音符和眼高的关系。
3. 先做一小段走得通的铺面组合。参考《胡同》练习的窄铺、宽铺和院门，再按空间缩浅或后退。深度、开间和檐高可独立变化。街口可以宽、院门处收窄，转角通过地块退界和路缘错位表现。主体灰墙和屋面控制反差，木构和灯只强调门口。先读出哪间在营业、哪间是院门，再补道具。

## 2. 用实际方块模型搭一个构件

开源 [lzif/mcbuilder](https://github.com/lzif/mcbuilder/tree/b0b24621a7ea6bd7cfd13659b11327cac3899e09) 独立安装。下例在仓库根目录运行，`python` 指集成包的 Python。Windows PowerShell 示例：

```powershell
python -m venv .architecture-env
$builder = ".architecture-env/Scripts/python.exe"
& $builder -m pip install "mcbuilder @ git+https://github.com/lzif/mcbuilder.git@b0b24621a7ea6bd7cfd13659b11327cac3899e09"
python run_pipeline.py architecture assets --tool-python $builder --cache projects/hutong-practice/build-assets
```

Linux/macOS 使用 `.architecture-env/bin/python`。首次准备工具和原版预览素材需要 Git 和网络。集成包通过 `architecture build` 调用这个独立解释器，用精确的 1.21.1 方块注册表验证，使用原版模型渲染，然后验证导出的 NBT。作者写的 Python 源码是本地可执行设计，第三方蓝图优先走下面的纯数据导入。

```powershell
foreach ($kind in @("narrow", "wide", "courtyard")) {
  python run_pipeline.py architecture build "examples/hutong-study/$kind.py" --tool-python $builder --cache projects/hutong-practice/build-assets --out "projects/hutong-practice/hutong/modules/$kind"
}
Copy-Item examples/hutong-study/street.json,examples/hutong-study/road.json projects/hutong-practice/hutong/
```

每件读 `run-001/report.json`，再看 `previews_faithful/` 的两张斜视和俯视。构件的本地原点是最低处的零坐标，正面朝北（-Z），宽度沿 +X。练习源文件在 `examples/hutong-study/frontage.py`。铺面用阶梯和半砖做灰瓦起伏，有基座、梁柱、格栅、照明和可进入的开口。前看柱脚和入口比例，背看屋坡连续和山墙，俯视看屋面与地块边界。若灰瓦两层之间能看见天光，先补接合处的实体厚度并重新从背面渲染。窄处用浅铺 `shallow.py`，保留入口和檐下光源。想换位置或朝向，优先改布置；想换柱距、屋面和材质，改构件源文件，以新输出目录保留上一版。需要看街口方向可传 `--views "az135_el015;az315_el015;top"`。

## 3. 组装、保护检查和存档生成

```powershell
python run_pipeline.py demo --project projects/hutong-practice/hutong-demo --until machine
$state = Get-Content projects/hutong-practice/hutong-demo/state.json -Raw | ConvertFrom-Json
$machine = "projects/hutong-practice/hutong-demo/$($state.stages.machine.artifact)"
python run_pipeline.py architecture assemble projects/hutong-practice/hutong/street.json --machine $machine --out projects/hutong-practice/hutong/assembled
python run_pipeline.py preview-stage projects/hutong-practice/hutong/assembled/stage.json --out projects/hutong-practice/hutong/preview
```

Linux/macOS 从 `state.json` 读取同一个 `stages.machine.artifact`，以前缀 `projects/hutong-practice/hutong-demo/` 解析其相对路径。命令返回 `stage.json`、`architecture-report.json`。报告记录每次放置的原点、朝向、块数和 NBT 哈希。练习摆在原创演奏机的侧边。场景里可在允许命令的创作副本使用 `/tp @s -16.5 105 88.5 0 0` 去街上观察。

- **布置规则。** `street.json` 的 `modules` 带名称和本地相对 NBT 路径，`placements` 带模块、世界坐标 `origin` 和 `quarterTurns`（0–3，俯视顺时针）。向东的门面用 1，向西用 3。围绕本地零点旋转，可能出现负坐标偏移。另可用 `baseStage` 保留道路或原来的装饰。两个模块格子重叠会直接报坐标，先移开轴线、缩屋檐或扩大地块再试。
- **数据约束。** 接入原版结构 NBT，目标 `DataVersion=3955`。楼梯朝向、木材轴、栏杆侧面和旋转属性按朝向一并变换。输入的空气格被当作留空。带方块实体数据、实体或交替调色板的结构要先拆出可复核的纯方块部分。告示牌文字和类似状态可在游戏副本里单独验证。旧 `.schem` 或 `.litematic` 可以在匹配版本的独立创作实例读入，再导出原版结构。建筑尺度分段控制，当前阶段蓝图上限为 50,000 格、每轴跨度 512 格。
- **合入。** `--machine` 使用加景前的机器，且机器中没有已由 `baseStage` 再次导入的方块。检查依据包含实体占用、音符盒头顶和基底、线路邻域、镜头通道。发现冲突时重排整个构件，保留完整的入口和屋顶。把生成的阶段蓝图路径写到制作项目 `project.json` 的 `inputs.stageModule`，再跑 `python run_pipeline.py run projects/hutong-practice/hutong-demo`。字段按项目目录解析，本练习用 `../hutong/assembled/stage.json`。查看新机器的 `stage_module_report.json` 与 `roundtrip.json`。已有粒子演出的作品用原参数重新应用[原版粒子示例](VANILLA_RAIL_PARTICLES.md)，再比音符序列、资源包与粒子文件。

## 4. 实机判定，决定下一版

先到街上走，从路面不跳跃进入一个铺面，确认门槛与路面接得上、头顶够高、屋檐与灯具可见。复看同一段跟拍，用关闭粒子确认建筑层次和远侧音轨，逐音档验一处主奏和一处低轨，完整档验乐句动画。若屋檐挡住远轨，先降檐、后撤一格或空出一块地，再重新建。把问题记为“时间、构件或声部、观察方向、改法”；改几何时保留音乐和镜头作为对照。复跑停止／重播并核对事件，最后请用户看代表段。

记录设计图、离线渲染、服务端触发和客户端画面的各自证据。离线渲染能检查建筑模型，游戏截图用于判断原版亮度、粒子和遮挡。录制外观在代表段通过后再试[材质与光影](SCENE_FINISH_AND_LOOK.md)。公开包自带原创练习源和布置样例，外部成品蓝图采用前按文件记录作者、来源、版本与许可。
