"""Validate stage contracts without conflating generated files with game playback."""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import zipfile
import zlib


def fs_path(path):
    """Support deep artifact trees on Windows without changing serialized paths."""
    path = Path(path).resolve()
    value = str(path)
    if os.name == "nt" and not value.startswith("\\\\?\\"):
        value = "\\\\?\\UNC\\" + value[2:] if value.startswith("\\\\") else "\\\\?\\" + value
        return Path(value)
    return path


def read(path):
    return json.loads(fs_path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    value = hashlib.sha256()
    with fs_path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def write(path, value):
    fs_path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def position(value):
    return tuple(value[key] for key in ("x", "y", "z"))


def state_parts(value):
    name, _, props = value.partition("[")
    return name, dict(item.split("=", 1) for item in props.rstrip("]").split(",") if "=" in item)


def archive_check(path, required=None):
    """Read every member's CRC, reject ambiguous or escaping archive members."""
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError(f"Duplicate archive member in {Path(path).name}")
        for name in names:
            normalized = name.replace("\\", "/")
            if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized) or ".." in normalized.split("/"):
                raise ValueError(f"Unsafe archive member in {Path(path).name}")
        broken = archive.testzip()
        if broken:
            raise ValueError(f"Corrupt archive member in {Path(path).name}: {broken}")
        if required and required not in names:
            raise ValueError(f"{Path(path).name} must contain {required} at archive root")


def verify_exports(machine, placed):
    """Independent decoding of Anvil padded arrays and Litematic continuous arrays."""
    try:
        import nbtlib
    except ImportError as error:
        raise RuntimeError("Export validation requires nbtlib") from error
    machine = fs_path(machine)
    blocks, info = placed["blocks"], placed["info"]
    schematic = nbtlib.load(str(machine / "performance.litematic"))
    if int(schematic["MinecraftDataVersion"]) != 3955:
        raise ValueError("Schematic DataVersion does not match Java 1.21.1")
    regions = schematic["Regions"]
    if len(regions) != 1:
        raise ValueError("Expected one schematic region")
    region = next(iter(regions.values()))
    size = {axis: int(region["Size"][axis]) for axis in ("x", "y", "z")}
    origin = info["origin"]
    expected_size = dict(zip(("x", "y", "z"), (info["bounds"][k] for k in ("width", "height", "length"))))
    if size != expected_size:
        raise ValueError("Schematic bounds do not match build manifest")
    palette = region["BlockStatePalette"]
    bits = max(2, (len(palette) - 1).bit_length())
    mask = (1 << bits) - 1
    words = [int(word) & ((1 << 64) - 1) for word in region["BlockStates"]]

    def palette_state(entry):
        return str(entry["Name"]), {str(k): str(v) for k, v in entry.get("Properties", {}).items()}

    def schematic_at(x, y, z):
        x, y, z = x - origin["x"], y - origin["y"], z - origin["z"]
        index = (y * size["z"] + z) * size["x"] + x
        word, offset = divmod(index * bits, 64)
        if word >= len(words):
            raise ValueError("Truncated schematic state array")
        value = words[word] >> offset
        if offset + bits > 64:
            value |= words[word + 1] << (64 - offset)
        return palette_state(palette[value & mask])

    region_cache, chunk_cache = {}, {}

    def chunk(cx, cz):
        if (cx, cz) not in chunk_cache:
            rx, rz = cx // 32, cz // 32
            filename = machine / "world/region" / f"r.{rx}.{rz}.mca"
            if (rx, rz) not in region_cache:
                region_cache[rx, rz] = filename.read_bytes()
            content = region_cache[rx, rz]
            index = cx % 32 + 32 * (cz % 32)
            record = int.from_bytes(content[index * 4:index * 4 + 4], "big")
            offset = (record >> 8) * 4096
            if offset < 8192 or offset + 5 > len(content):
                raise ValueError("Missing or truncated Anvil chunk")
            length = int.from_bytes(content[offset:offset + 4], "big")
            if content[offset + 4] != 2 or offset + 4 + length > len(content):
                raise ValueError("Unsupported or truncated Anvil compression")
            value = nbtlib.File.parse(io.BytesIO(zlib.decompress(content[offset + 5:offset + 4 + length])))
            if int(value["DataVersion"]) != 3955 or int(value["xPos"]) != cx or int(value["zPos"]) != cz:
                raise ValueError("Anvil chunk version or position mismatch")
            chunk_cache[cx, cz] = value
        return chunk_cache[cx, cz]

    section_cache = {}

    def anvil_at(x, y, z):
        key = x // 16, y // 16, z // 16
        if key not in section_cache:
            section = next((s for s in chunk(x // 16, z // 16)["sections"] if int(s["Y"]) == y // 16), None)
            section_cache[key] = section
        section = section_cache[key]
        if section is None:
            return "minecraft:air", {}
        states = section["block_states"]
        palette = states["palette"]
        if len(palette) == 1:
            return palette_state(palette[0])
        width = max(4, (len(palette) - 1).bit_length())
        entries_per_word = 64 // width
        index = (y % 16) * 256 + (z % 16) * 16 + x % 16
        word = int(states["data"][index // entries_per_word]) & ((1 << 64) - 1)
        return palette_state(palette[(word >> ((index % entries_per_word) * width)) & ((1 << width) - 1)])

    for block in blocks:
        xyz = position(block)
        expected = state_parts(block["state"])
        if schematic_at(*xyz) != expected:
            raise ValueError(f"Schematic state mismatch at {xyz}")
        if anvil_at(*xyz) != expected:
            raise ValueError(f"Anvil state mismatch at {xyz}")
        if expected[0] == "minecraft:note_block":
            above = xyz[0], xyz[1] + 1, xyz[2]
            if schematic_at(*above)[0] != "minecraft:air" or anvil_at(*above)[0] != "minecraft:air":
                raise ValueError(f"Exported note is obstructed at {xyz}")
        if "nbt" in block:
            tile = next((t for t in chunk(xyz[0] // 16, xyz[2] // 16)["block_entities"] if position(t) == xyz), None)
            if tile is None or str(tile.get("id")) != block["nbt"]["id"]:
                raise ValueError(f"Missing Anvil block entity at {xyz}")
            if "Command" in block["nbt"] and str(tile.get("Command")) != block["nbt"]["Command"]:
                raise ValueError(f"Changed Anvil command block at {xyz}")
    files = {"performance.litematic": sha(machine / "performance.litematic"), "world/level.dat": sha(machine / "world/level.dat")}
    files.update({str(file.relative_to(machine)).replace("\\", "/"): sha(file) for file in sorted((machine / "world/region").glob("*.mca"))})
    return {"checkedBlocks": len(blocks), "worldRoundtripPassed": True, "schematicRoundtripPassed": True, "checkedChunks": len(chunk_cache), "filesSha256": files}


def run(ctx):
    out = fs_path(ctx["out"])
    out.mkdir(parents=True, exist_ok=True)
    dependencies = {key: fs_path(value) for key, value in ctx["deps"].items()}
    config = ctx["config"]
    checks, problems, warnings = [], [], []

    def require(condition, name):
        (checks if condition else problems).append(name)

    music, sound, machine = (dependencies[key] for key in ("music", "sound", "machine"))
    score, adapted = read(music / "score.json"), read(sound / "events.json")
    expected = read(machine / "expected_events.json")
    placed = read(machine / "placed_blocks.json")
    notes = expected["notes"]
    candidates = adapted["candidates"]
    require(bool(notes) and len(notes) == len(candidates), "All adapted events have physical note blocks")
    require(len({note["id"] for note in notes}) == len(notes), "Physical event IDs are unique")
    require(len({note["id"] for note in candidates}) == len(candidates), "Adapted event IDs are unique")
    planned = {note["id"]: note for note in candidates}
    require(set(planned) == {note["id"] for note in notes}, "Machine preserves all adapted event IDs")
    source_ids = {note["id"] for note in score["notes"]}
    source_parents = {note.get("parentId", note["id"]) for note in score["notes"]}
    require(all(note.get("parentId", note["id"]) in source_ids | source_parents for note in candidates), "Adapted parents refer to source score")
    represented = {note.get("parentId", note["id"]) for note in candidates}
    represented.update(item["id"] for item in adapted.get("merged", []) if "id" in item)
    omitted = adapted.get("omitted", [])
    if omitted:
        reasons = {row.get("id"):row.get("reason") for row in omitted}
        authored = sound/"game-arrangement.json"
        allow = ({row["noteId"]:row["reason"] for row in read(authored).get("edits",[])
                  if row.get("omit") is True} if authored.is_file() else {})
        require(len(omitted)==len(reasons) and reasons==allow and reasons.keys()<=source_ids
                and not (reasons.keys() & represented), "Omissions match unique source IDs and authored reasons")
        represented.update(reasons)
    require(source_parents <= represented, "Every source parent is represented, merged or explicitly omitted")
    block_positions = [position(block) for block in placed["blocks"]]
    require(len(block_positions) == len(set(block_positions)), "Placed blocks have no coordinate collisions")
    grid = {position(block): block for block in placed["blocks"]}
    require(len({position(note) for note in notes}) == len(notes), "Physical notes have unique coordinates")
    require(all(all(integer(note.get(k)) for k in ("x", "y", "z")) for note in notes), "Physical note positions are integers")
    require(all(integer(note.get("note")) and 0 <= note["note"] <= 24 for note in notes), "Tuning values fit note-block range")
    require(all(integer(note.get("gt")) and note["gt"] >= 0 and integer(note.get("q")) and note["q"] >= 0 for note in notes), "Absolute and local trigger ticks are nonnegative integers")
    offset = expected.get("info", {}).get("excerpt", {}).get("startGT", 0)
    require(all(note["q"] == note["gt"] - offset for note in notes), "Local q uses one absolute clock and excerpt offset")
    preserved = ("parentId", "family", "gt", "kind", "sourceMidi", "sourceStartSeconds", "sourceEndSeconds", "instrument", "note", "baseBlock")
    require(all(note["id"] in planned and all(note.get(key) == planned[note["id"]].get(key) for key in preserved) for note in notes), "Machine preserves adapted timing, pitch, timbre and source fields")
    require(all(isinstance(note.get("sourceStartSeconds"), (int, float)) and math.isfinite(note["sourceStartSeconds"]) and isinstance(note.get("sourceEndSeconds"), (int, float)) and math.isfinite(note["sourceEndSeconds"]) and note["sourceEndSeconds"] > note["sourceStartSeconds"] for note in notes), "Source duration and onset are finite and ordered")
    require(all(grid.get(position(note), {}).get("state", "").startswith("minecraft:note_block[") for note in notes), "Every physical event is backed by a note block")
    for note in notes:
        block = grid.get(position(note), {})
        _, props = state_parts(block.get("state", ""))
        require(props.get("instrument") == note["instrument"] and props.get("note") == str(note["note"]) and props.get("powered") == "false", f"Note state matches event {note['id']}")
        base = note.get("base", {"x": note["x"], "y": note["y"] - 1, "z": note["z"]})
        require(grid.get(position(base), {}).get("state") == note["baseBlock"], f"Instrument base matches event {note['id']}")
        above = grid.get((note["x"], note["y"] + 1, note["z"]))
        require(above is None or above.get("state") == "minecraft:air", f"Air above event {note['id']}")
    master = music / "master.mid"
    source_hash = adapted.get("sourceMidiSha256")
    if master.exists() and source_hash:
        require(sha(master) == source_hash, "Sound adaptation binds the frozen MIDI")
    resource = sound / "resources.zip"
    resource_required = config.get("sound", {}).get("profile", "vanilla") != "vanilla"
    if (sound / "report.json").exists():
        resource_required |= bool(read(sound / "report.json").get("resourcePackRequired"))
    require(not resource_required or resource.is_file(), "Custom timbre profile has its resource pack")
    if resource.exists():
        archive_check(resource, "pack.mcmeta")
        checks.append("Sound resource archive CRC and root")
    require((machine / "performance.litematic").is_file(), "Litematic exported")
    require((machine / "world/level.dat").is_file(), "World metadata generated")
    require((machine / "helper/pack.mcmeta").is_file(), "Playback control data pack generated")
    require(any((machine / "world/region").glob("*.mca")), "World contains generated region data")
    manifest = read(machine / "build_manifest.json")
    track_path = machine/'track-plan.json'
    if track_path.is_file():
        track = read(track_path)
        require(track == manifest.get('trackPlan') and track.get('musicGT')==adapted.get('musicGT'),
                'Phrase design matches the exported build and event clock')
        sections = track.get('sections',[])
        phrase_ids = {row['beginGT']:row for row in sections}
        require(all(note.get('clockLane',{}).get('launchGT') in phrase_ids
                    and phrase_ids[note['clockLane']['launchGT']]['beginGT']<=note['q']<
                        phrase_ids[note['clockLane']['launchGT']]['endGT']
                    and note['clockLane']['parity']==(note['q']-note['clockLane']['launchGT'])%2
                    and note['z']==80+note['q'] for note in notes),
                'Each physical strike uses its own phrase clock and preserves the global performance tick')
    namespace = manifest.get("namespace")
    require(isinstance(namespace, str) and bool(re.fullmatch(r"[a-z0-9_.-]+", namespace)), "Valid data-pack namespace")
    metadata = read(machine / "helper/pack.mcmeta")
    require(metadata.get("pack", {}).get("pack_format") == 48, "Data pack targets Java 1.21.1 format 48")
    if isinstance(namespace, str) and re.fullmatch(r"[a-z0-9_.-]+", namespace):
        for name in ("load", "tick", "start", "stop"):
            require((machine / f"helper/data/{namespace}/function/{name}.mcfunction").is_file(), f"Control function exists: {name}")
        for name in ("load", "tick"):
            tag = machine / f"helper/data/minecraft/tags/function/{name}.json"
            require(tag.exists() and f"{namespace}:{name}" in read(tag).get("values", []), f"Data-pack entrypoint registered: {name}")
    helper_files = [file for file in (machine / "helper").rglob("*") if file.is_file()]
    require(all((machine / "world/datapacks/helper" / file.relative_to(machine / "helper")).is_file() and sha(file) == sha(machine / "world/datapacks/helper" / file.relative_to(machine / "helper")) for file in helper_files), "Playable world embeds identical control data pack")

    visuals = dependencies.get("visuals")
    if visuals and (visuals / "show_assets.json").exists():
        show = read(visuals / "show_assets.json")
        wanted = {note["id"] for note in notes if note["kind"] != "retrigger"}
        visual_notes = show.get("notes", [])
        require(len(visual_notes) == len(wanted) and {note["id"] for note in visual_notes} == wanted, "Visual impacts correspond exactly to onsets, excluding retriggers")
        actual_by_id = {note["id"]: note for note in notes}
        require(all(note["id"] in actual_by_id and note["q"] == actual_by_id[note["id"]]["q"] for note in visual_notes), "Visual event ticks agree with physical events")
        length = adapted.get("musicGT", math.ceil(adapted["durationSeconds"] * 20))
        captions_data = read(visuals / "captions.json") if (visuals / "captions.json").exists() else {"cues": []}
        captions = captions_data.get("cues", []) if isinstance(captions_data, dict) else captions_data
        require(len({cue["id"] for cue in captions}) == len(captions), "Caption IDs are unique")
        require(all(integer(cue.get("begin")) and integer(cue.get("end")) and 0 <= cue["begin"] < cue["end"] <= length for cue in captions), "Captions use bounded music-tick intervals")
        if (visuals / "client.jar").exists():
            archive_check(visuals / "client.jar", "fabric.mod.json")
            checks.append("Client mod archive CRC and metadata")
        elif config.get("visuals", {}).get("enabled", True):
            warnings.append("Visual assets exist, but no client.jar was produced; particle/caption playback is not installed")

    export_report = verify_exports(machine, placed) if not problems else {"worldRoundtripPassed": False, "schematicRoundtripPassed": False}
    if not problems:
        checks.append("Independent Anvil and Litematic readback matches every placed block")
    bindings = {"score": sha(music / "score.json"), "adaptedEvents": sha(sound / "events.json"), "expectedEvents": sha(machine / "expected_events.json"), "placedBlocks": sha(machine / "placed_blocks.json")}
    runtime = {"serverVerified": False, "clientVerified": False, "listeningVerified": False}
    runtime_file = machine / "runtime_validation.json"
    if runtime_file.exists():
        evidence = read(runtime_file)
        bound = evidence.get("expectedEventsSha256") == bindings["expectedEvents"]
        require(bound, "Runtime evidence binds current expected events")
        server = evidence.get("server", {})
        client = evidence.get("client", {})
        runtime["serverVerified"] = bool(bound and server.get("passed") and server.get("actualCount") == len(notes) and server.get("exactTimingPitchAndCamera"))
        runtime["clientVerified"] = bool(bound and runtime["serverVerified"] and client.get("passed") and client.get("cleanupVerified") and client.get("fullSongVerified"))
        if server.get("passed"):
            require(runtime["serverVerified"], "Server success includes complete exact event evidence")
        if client.get("passed"):
            require(runtime["clientVerified"], "Client success includes full-song and cleanup evidence")
    if not runtime["serverVerified"]:
        warnings.append("Static checks passed does not establish actual redstone playback; server replay is pending")
    if not runtime["clientVerified"]:
        warnings.append("Client rendering, interpolation and cleanup remain unverified")
    delivery_bindings = []
    for stage, folders, filenames in (("machine", ("world", "helper"), ("performance.litematic","track-plan.json")), ("sound", (), ("resources.zip","game-performance.mid","arrangement-report.json")), ("visuals", (), ("client.jar", "show_assets.json", "captions.json", "show_score.json"))):
        if stage not in dependencies:
            continue
        base = dependencies[stage]
        files = [file for folder in folders for file in (base / folder).rglob("*") if file.is_file()]
        files += [base / name for name in filenames if (base / name).is_file()]
        for file in sorted(files):
            if file.is_symlink():
                raise ValueError("Symlink cannot enter a validated release")
            delivery_bindings.append({"stage": stage, "path": str(file.relative_to(base)).replace("\\", "/"), "sha256": sha(file)})
    report = {"schemaVersion": 1, "staticValidated": not problems, "status": "failed" if problems else "client_verified" if runtime["clientVerified"] else "server_verified" if runtime["serverVerified"] else "static_validated", "counts": {"physicalEvents": len(notes), "logicalOnsets": sum(note["kind"] != "retrigger" for note in notes), "placedBlocks": len(grid)}, "bindings": bindings, "deliveryBindings": delivery_bindings, "exports": export_report, "runtime": runtime, "checks": checks, "errors": problems, "warnings": warnings, "artisticReview": "not_performed"}
    write(out / "report.json", report)
    if problems:
        raise ValueError("Validation failed: " + "; ".join(problems[:8]))
    return {key: report[key] for key in ("status", "staticValidated", "counts", "runtime", "warnings")}
