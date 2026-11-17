"""Package explicit deliverables, preserving provenance and verification boundaries."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import zipfile

from .validate import fs_path, read, sha, write


def run(ctx):
    deps = {key: fs_path(value) for key, value in ctx["deps"].items()}
    out = fs_path(ctx["out"])
    out.mkdir(parents=True, exist_ok=True)
    report = read(deps["validate"] / "report.json")
    if not report.get("staticValidated") or report.get("errors"):
        raise ValueError("Release requires successful validation")
    bound = report.get("bindings", {})
    for key, path in (("expectedEvents", deps["machine"] / "expected_events.json"), ("placedBlocks", deps["machine"] / "placed_blocks.json"), ("adaptedEvents", deps["sound"] / "events.json"), ("score", deps["music"] / "score.json")):
        if bound.get(key) != sha(path):
            raise ValueError(f"Validated input changed before release: {key}")
    exports = report.get("exports", {})
    if not exports.get("worldRoundtripPassed") or not exports.get("schematicRoundtripPassed"):
        raise ValueError("Release requires independent world and schematic readback")
    for name, expected_sha in exports.get("filesSha256", {}).items():
        if sha(deps["machine"] / name) != expected_sha:
            raise ValueError(f"Validated export changed before release: {name}")
    for record in report.get("deliveryBindings", []):
        base = deps[record["stage"]].resolve()
        file = (base / record["path"]).resolve()
        if not file.is_relative_to(base) or not file.is_file() or sha(file) != record["sha256"]:
            raise ValueError(f"Validated companion changed before release: {record['stage']}/{record['path']}")
    config = ctx["config"]
    slug = config.get("slug", "performance")
    title = config.get("title", slug)
    package = out / "package"
    package.mkdir()
    machine = deps["machine"]
    excluded = {"session.lock", "usercache.json", "latest.log"}

    def copy_tree(source, destination):
        source = source.resolve()
        for file in sorted(source.rglob("*")):
            if file.is_symlink():
                raise ValueError("Symlinks cannot enter a release package")
            if not file.is_file() or file.name in excluded or any(part in {"logs", "crash-reports", "playerdata", "advancements", "stats"} for part in file.relative_to(source).parts):
                continue
            target = destination / file.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(file, target)

    copy_tree(machine / "world", package / "world")
    copy_tree(machine / "helper", package / "helper")
    shutil.copyfile(machine / "performance.litematic", package / "performance.litematic")
    resource = deps["sound"] / "resources.zip"
    if resource.exists():
        shutil.copyfile(resource, package / "resources.zip")
        shutil.copyfile(resource, package / "world/resources.zip")
    visuals = deps.get("visuals")
    if visuals:
        for name in ("client.jar", "show_assets.json", "captions.json", "show_score.json"):
            if (visuals / name).exists():
                shutil.copyfile(visuals / name, package / name)
    # Export concise facts only; project config can contain local/private paths.
    metadata = {"schemaVersion": 1, "slug": slug, "title": title, "minecraft": "Java 1.21.1", "fabricLoaderMinimum": "0.18.2" if (package / "client.jar").exists() else None, "musicSeconds": read(deps["sound"] / "events.json")["durationSeconds"], "counts": report["counts"], "sourceHashes": report["bindings"], "audioMode": "physical_note_blocks", "status": report["status"], "runtime": report["runtime"], "artisticReview": report.get("artisticReview", "not_performed"), "captureStatus": "not_recorded", "publishingStatus": "not_uploaded"}
    write(package / "project_summary.json", metadata)
    write(package / "validation.json", report)
    has_client = (package / "client.jar").exists()
    has_sound = (package / "resources.zip").exists()
    manifest_info = read(machine / "build_manifest.json")
    namespace = manifest_info.get("namespace", "nevada_full")
    usage = f"""# {title}

本包为自动生成的候选演出，验证状态：`{report['status']}`。

1. 使用 Minecraft Java 1.21.1 与 Java 21；需要粒子/字幕时使用匹配的 Fabric 环境。
2. 游戏关闭时，将本包 `world` 文件夹复制到专用实例的 `saves`，使用一个新的世界目录名。
3. {('将 client.jar 放入该实例 mods，只保留一个相同 mod ID 的构建。' if has_client else '本包未包含客户端演出模组，视觉 JSON 仅为可继续制作的资源。')}
4. {('接受世界资源包；独立 resources.zip 与 world/resources.zip 内容相同。' if has_sound else '本包使用原版声音；不包含自定义声音包。')}
5. 进入世界等待就绪，然后执行 `/function {namespace}:start`；停止复位执行 `/function {namespace}:stop`。等待重新就绪后可以再次开始。

投影 `performance.litematic` 是方块结构，单独导入还需要配套 helper 数据包，且须保持 build manifest 规定的原点与方向。完整世界优先。

技术边界：生成 Anvil 区域和投影不等于已通过真实游戏演奏。请查看 validation.json 中 serverVerified / clientVerified。静音或截图测试也不等于实际听审。首次录制前检查声音、镜头平滑、中止重播和编码开启后的性能。

此包不包含参考原曲/分轨、完整 MIDI 母版、个人路径或第三方游戏运行库。声音包如来自外部素材，其分发范围需由项目使用者核对来源许可。
"""
    (package / "USAGE.md").write_text(usage, encoding="utf-8")
    files = {str(file.relative_to(package)).replace("\\", "/"): {"bytes": file.stat().st_size, "sha256": sha(file)} for file in sorted(package.rglob("*")) if file.is_file()}
    manifest = {**metadata, "files": files}
    write(package / "release_manifest.json", manifest)
    write(out / "release_manifest.json", manifest)
    shutil.copyfile(package / "USAGE.md", out / "USAGE.md")
    archive = out / "deliverables.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for file in sorted(package.rglob("*")):
            if file.is_file():
                z.write(file, str(file.relative_to(package)).replace("\\", "/"))
    summary = {"status": report["status"], "archive": archive.name, "archiveSha256": sha(archive), "files": len(files) + 1, "runtime": report["runtime"], "captureStatus": "not_recorded", "publishingStatus": "not_uploaded"}
    write(out / "report.json", summary)
    return summary
