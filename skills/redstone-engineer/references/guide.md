# 物理时序、运行与验证

## 构建前

先读当前输入、声音profile与事件。每个发声需要来源、绝对GT、音色/基底、方块note和坐标；声音变化可能要求同时改变机器，不能只给世界换一个ZIP。

```shell
python run_pipeline.py run projects/my-song --until sound
python run_pipeline.py status projects/my-song
python run_pipeline.py run projects/my-song --until machine
```

路径以status返回的不可变artifact为准。模板可能有明确的宽度、原点和容量边界；超出时调整profile或生成开发任务，不删除断言强行生成。

## 时序与容量

绝对秒统一量化到GT，禁止逐间隔取整。奇偶双路通过已验证相位头实现1GT分辨率；修改朝向、相邻模块、线长和启动延迟都可能改变实际结果。

峰值复音、补触发、轨道层数、全曲长度与加载窗口分别统计。样段未达到全曲密度时，不能用样段运行成功推断全曲容量。沙子/重力方块要有支持，音符盒上方空气、音色基底和导电邻域保留。

## 相机与加载

相机目标点正确不代表逐帧平滑。检查显示实体同步/绑定顺序、插值跨度、预运行、演奏波前与观察者渲染中心。移动加载窗口覆盖未来触发区域，结尾和维护分段不遗漏。

配置应声明布局与相机坐标，不把某首作品的中心点复制到另一布局。保存重进后看实体、scoreboard、storage和控制按钮是否仍对应当前作品。

## 运行环境

```shell
python run_pipeline.py game inspect /path/to/instance --java /path/to/jdk21/bin/java
python run_pipeline.py game import /path/to/instance --out work/game-runtime --java /path/to/jdk21/bin/java
python run_pipeline.py doctor projects/my-song
```

在project的runtime中按实际schema配置服务端与观察器。运行完整测试前确认world-root是任务副本，测试队列、端口与进程不和另一个项目共享。详细入口见[环境教程](../../../docs/ENVIRONMENT.md)与命令帮助。

## 成功练习

用原创8秒demo完整构建并解码世界/投影；配置真实服务端后比较实际音高、乐器、GT和相机目标。中途停止，确认之后无新事件，再完整重播并保存重进。每个证据对应明确输入hash。

## 故意失败练习

在专用测试副本中将一个基底换成不受支撑的重力方块，或把装饰放在音符盒上方；静态保护或实际日志应暴露问题。原始音乐计划保持不变，修复生成规则再导出，不只编辑期望列表。

## 退出条件

独立回读一致，原始事件变换可解释，实际正常速度触发通过，中止/重播与保存重进范围清楚。报告若只有服务器坐标，客户端插值、听感和录制仍待验证。

开发模组API时可读[上游模组技能快照](../../_upstream/minecraft-agent-skills/minecraft-modding.txt)和[测试快照](../../_upstream/minecraft-agent-skills/minecraft-testing.txt)，以固定1.21.1实际源码为依据。
