# 外部能力接入与验证边界

`docs/TOOLING_RESEARCH.md` 记录选型和许可边界；接入工具不代表已经完成艺术验收。每个制作项目仍保存独立的声音、机器、视觉和录制证据。

## 已可调用的离线能力

`preview-stage` 使用固定提交的 MIT mcbuild `VoxelGrid`，在本项目的受限 JSON 蓝图接口中生成方块清单、材料统计、保护区冲突和四向 CPU 预览。代码及许可来源见 [mcbuild/provenance.json](mcbuild/provenance.json)。不会调用其托管模型主控、安装其 NeoForge 模组或分发 Minecraft 纹理。预览使用简色和部分台阶/楼梯轮廓；游戏注册表、实际光照、物理和红石行为须在客户端复核。

`architecture build` 通过指定的独立 Python 调用另一项目 lzif/mcbuilder，验证 Java 1.21.1 方块、生成原版模型预览和结构 NBT。`architecture assemble` 将原版 NBT 按保存的布局和朝向变成现有机器可读的阶段蓝图。组装可独立使用，无需安装外部构件程序。安装锁定版本、练习和兼容边界见[建筑模块教程](../docs/MINECRAFT_ARCHITECTURE.md)。

`compile-show` 将音符起音/延音或人工编写的 show score 编译为独立效果资产，支持 node、ring、helix、bezier 和固定屏幕字幕。效果与物理音乐机共用 `musicGT` 时钟，长音由持续几何表现，声音 retrigger 不额外制造起音效果。此接口允许 agent 编排乐句、空间和配色，不把默认参数当成审美结论。

`client/` 是标准 Fabric Loom/Gradle、Minecraft Java 1.21.1 的参照客户端源码。`build-client` 需要显式可用的 Java21 JDK；首次构建联网下载公开构建依赖，后续重用 Gradle 缓存。流水线通过 `runtime.clientJar` 引用构建产物并嵌入项目效果数据；旧 intermediary 编译入口仅接受显式 `runtime.clientRuntime`，不再从 Nevada 私有目录自动寻找环境。

`game inspect` 只读游戏版本/模组元数据和 Java 状态。`game import` 创建独立游戏目录、显式引用用户本地 assets/libraries，至多复制用户已安装的 Fabric API；不复制登录凭据、其他模组、原曲或第三方资源包。使用用户的正常 Minecraft 启动器启动所生成的 profile。环境导入、编译和打包报告均不等于成功启动或实际听看。

## Photon Fabric 1.6 对照实验

```shell
redstone-music photon-plan show_score.json --out comparisons/phrase-v01 --mod-jar /local/path/photon-1.6.jar
```

`plan_photon_comparison` 检查用户显式提供的 JAR 的 SHA256、Fabric 元数据、版本和依赖，并读取客户端命令类的常量。输出相同 show score、粒子预算以及环境、创作、同步、清理、性能、字幕、用户听看的待验证清单。不复制 JAR，不安装或运行 Photon，不声称已经实现 `.fx` 自动编译。原生参照每 tick 最多 1200 个粒子；计划会指出样段是否超出这一预算。

目前观察到的 [Photon Fabric 1.6 发行](https://modrinth.com/mod/photon-editor-fabric/version/1.6) 为 client 环境，需要 Fabric API、LDLib2 和 special-model-loader。`/photon_editor`、`/photon_client clear_particles`、`/photon_client clear_client_fx_cache` 的命令名可在本地发行类常量中核对；命令的实际执行和效果生命周期仍需在隔离实例记录。它与 [Photon 官方当前分支](https://github.com/Low-Drag-MC/Photon) 及其 NeoForge 发布不应混用。

本地 1.6 JAR 的许可声明与 [Fabric 移植仓库当前 README](https://github.com/ELBGG/Photon) 的许可说明存在差异。此仓库不捆绑 Photon；发布前核对确切版本的许可及依赖，模组生成的原创效果与模组代码分别记录授权。

完成比较的证据至少包括：同一音乐时钟和镜头的两段录屏、最终光影设置、同步误差、停止/重播/离开世界后的清理、录制负载下的性能数据，以及用户对代表样段的视觉决定。在这些记录到位之前，M3 保持未实测/待艺术验收；不能因为 CPU 图片、JAR 构建或接口检查成功而自动选择某个后端。
