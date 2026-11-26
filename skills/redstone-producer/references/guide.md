# 作品组织与决策

## 开始与接手

新曲以[brief模板](../../../templates/brief.md)记录参考版本、范围、音乐/画面目标、可用素材与用户反馈方式。输入是可信MIDI可直接体检；输入是音频或不完整改编，先用音乐Skill判断恢复与新增编配的边界。

```shell
python run_pipeline.py capabilities --probe
python run_pipeline.py init projects/my-song --title "我的作品"
python run_pipeline.py brief projects/my-song --text "完整曲目；实体红石；先做旋律/长音与密集高潮样段。"
python run_pipeline.py run projects/my-song
python run_pipeline.py tasks projects/my-song
```

先读取工具返回的任务路径，不猜固定任务ID。专业任务读该目录`task.json`和当前输入；输出写入其允许目录，主控用`complete-task`导入。导入资源不授予阶段通过。

```shell
python run_pipeline.py create-task projects/my-song --role sound --kind sound_profile --objective "诊断主旋律被pad遮盖；给出同段同增益比较及可集成候选。"
python run_pipeline.py handoff projects/my-song
```

## 创作阶段怎么分

按需要解决的问题分任务，而不是机械按乐器数创建agent。先有全曲角色/段落表，再分别修订主题、低频、长音或声部关系。建筑与效果可以在同一时间基准下做小样，但不要让两名执行者同时改共享产物或同一个运行实例。

给专业角色的是作品目标、相关原始输入、当前候选及需回答的问题；不用传入整个旧聊天。不要提前给出你希望它得出的结论。质量角色应能反驳候选；工具检查以实际导出/运行结果为准。

## 样段与反馈

选择3–5个风险覆盖点而非同一种高潮重复试听：主旋律与伴奏、低频/鼓、长音、角色交接、休止/结尾。每份试听注明母版/采样近似/实际游戏录音，位置与音量匹配。

用户说“主唱听不清”时，先让声音角色分解：本身太弱、共享槽连带变化、频段遮盖、距离过远还是音色不易辨认。不要一次改掉音高、音色、全部增益和镜头，导致无法解释改善来自哪里。

## 成功练习

运行`learn`生成原创素材，初始化一个新项目，做到可导入的MIDI、声音样段和机器候选。让另一个无旧上下文的agent只读brief、`handoff`和当前产物接手；它应能找到下一操作而不问“旧版在哪里”。

## 失败练习

更改一个已登记输入后，提交之前版本的专业结果或review。应拒绝过期导入，或在交接中将旧认可标为stale。正确做法是对比输入差异，把有效创意重新绑定新任务，而不是篡改fingerprint。

## 退出条件

作品目标清楚；当前阶段有实际产物/证据；反馈绑定具体版本；下一操作可执行。缺能力时保留已完成范围和替代路线，不制造假完成或无限等待。
