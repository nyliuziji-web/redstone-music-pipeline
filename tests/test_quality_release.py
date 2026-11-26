"""Semantic validation failures and artifact-bound release packaging."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import shutil
import re
import runpy
import unittest
import zipfile

from redstone_music import release, validate, world, music, sound, machine


class QualityReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="redstone_quality_")
        self.root = Path(self.temp.name)
        self.deps = {name: self.root / name for name in ("music", "sound", "machine", "visuals", "validate")}
        for folder in self.deps.values():
            folder.mkdir()
        self.config = {"slug": "original-test", "title": "Original Test", "inputs": {}, "sound": {"profile": "vanilla"}, "visuals": {"enabled": True}}
        master = self.deps["music"] / "master.mid"
        master.write_bytes(b"MThd-test-fixture")
        self.hash = hashlib.sha256(master.read_bytes()).hexdigest()
        source = {"id": "n0", "parentId": "n0", "family": "theme_attack", "sourceMidi": 60, "sourceStartSeconds": 0.0, "sourceEndSeconds": 0.5}
        self.save("music", "score.json", {"notes": [source]})
        first = {**source, "gt": 0, "q": 0, "kind": "onset", "instrument": "harp", "note": 6, "baseBlock": "minecraft:dirt"}
        second = {**first, "id": "n0r", "gt": 4, "q": 4, "kind": "retrigger"}
        self.events = {"sourceMidiSha256": self.hash, "musicGT": 10, "durationSeconds": 0.5, "candidates": [first, second]}
        self.save("sound", "events.json", self.events)
        notes = [{**first, "x": 2, "y": 2, "z": 10, "base": {"x": 2, "y": 1, "z": 10}}, {**second, "x": 2, "y": 2, "z": 14, "base": {"x": 2, "y": 1, "z": 14}}]
        self.save("machine", "expected_events.json", {"info": {"excerpt": {"startGT": 0}}, "notes": notes})
        blocks = []
        for note in notes:
            blocks.append({"x": note["x"], "y": note["y"], "z": note["z"], "state": "minecraft:note_block[instrument=harp,note=6,powered=false]"})
            blocks.append({**note["base"], "state": "minecraft:dirt"})
        info = {"origin": {"x": 0, "y": 0, "z": 0}, "bounds": {"width": 4, "height": 4, "length": 16}, "title": "Test"}
        self.save("machine", "placed_blocks.json", {"info": info, "blocks": blocks})
        self.save("machine", "build_manifest.json", {"namespace": "test_show"})
        world.write_litematic(self.deps["machine"] / "performance.litematic", blocks, info)
        world.write_world(self.deps["machine"] / "world", blocks, info)
        (self.deps["machine"] / "helper").mkdir()
        self.save("machine", "helper/pack.mcmeta", {"pack": {"pack_format": 48, "description": "test"}})
        functions = self.deps["machine"] / "helper/data/test_show/function"
        functions.mkdir(parents=True)
        tags = self.deps["machine"] / "helper/data/minecraft/tags/function"
        tags.mkdir(parents=True)
        for name in ("load", "tick", "start", "stop"):
            (functions / (name + ".mcfunction")).write_text("say test\n", encoding="utf-8")
        for name in ("load", "tick"):
            (tags / (name + ".json")).write_text(json.dumps({"values": ["test_show:" + name]}), encoding="utf-8")
        shutil.copytree(self.deps["machine"] / "helper", self.deps["machine"] / "world/datapacks/helper")
        self.save("visuals", "show_assets.json", {"notes": [{"id": "n0", "q": 0}], "sections": [], "transitions": [], "length": 10})
        self.save("visuals", "captions.json", {"cues": []})

    def tearDown(self):
        if validate.fs_path(self.root).exists():
            shutil.rmtree(validate.fs_path(self.root))
        self.temp.cleanup()

    def save(self, stage, name, data):
        (self.deps[stage] / name).write_text(json.dumps(data), encoding="utf-8")

    def load(self, stage, name):
        return json.loads((self.deps[stage] / name).read_text(encoding="utf-8"))

    def context(self, output):
        return {"project": str(self.root), "root": str(self.root), "config": self.config, "deps": {key: str(value) for key, value in self.deps.items()}, "out": str(output)}

    def run_validation(self):
        return validate.run(self.context(self.deps["validate"]))

    def test_static_candidate_never_claims_game_or_listening_verification(self):
        result = self.run_validation()
        self.assertEqual(result["status"], "static_validated")
        self.assertFalse(result["runtime"]["serverVerified"])
        self.assertFalse(result["runtime"]["clientVerified"])
        self.assertFalse(result["runtime"]["listeningVerified"])
        self.assertEqual(result["counts"]["physicalEvents"], 2)
        self.assertEqual(result["counts"]["logicalOnsets"], 1)

    def test_obstructed_note_rejected(self):
        placed = self.load("machine", "placed_blocks.json")
        placed["blocks"].append({"x": 2, "y": 3, "z": 10, "state": "minecraft:stone"})
        self.save("machine", "placed_blocks.json", placed)
        with self.assertRaisesRegex(ValueError, "Air above"):
            self.run_validation()

    def test_invalid_pitch_and_changed_physical_timing_rejected(self):
        data = self.load("machine", "expected_events.json")
        data["notes"][0]["note"] = 25
        data["notes"][1]["gt"] += 1
        self.save("machine", "expected_events.json", data)
        with self.assertRaisesRegex(ValueError, "range|clock|preserves"):
            self.run_validation()

    def test_missing_source_parent_rejected(self):
        events = copy.deepcopy(self.events)
        for note in events["candidates"]:
            note["parentId"] = "missing"
        self.save("sound", "events.json", events)
        with self.assertRaisesRegex(ValueError, "source"):
            self.run_validation()

    def test_retrigger_cannot_be_a_visual_impact(self):
        self.save("visuals", "show_assets.json", {"notes": [{"id": "n0", "q": 0}, {"id": "n0r", "q": 4}]})
        with self.assertRaisesRegex(ValueError, "excluding retriggers"):
            self.run_validation()

    def test_out_of_range_caption_rejected(self):
        self.save("visuals", "captions.json", {"cues": [{"id": "line", "begin": 5, "end": 11}]})
        with self.assertRaisesRegex(ValueError, "Captions"):
            self.run_validation()

    def test_custom_timbre_requires_resource_pack(self):
        self.config["sound"]["profile"] = "custom"
        with self.assertRaisesRegex(ValueError, "resource pack"):
            self.run_validation()

    def test_false_runtime_success_and_stale_report_rejected(self):
        self.save("machine", "runtime_validation.json", {"expectedEventsSha256": "bad", "server": {"passed": True, "actualCount": 2, "exactTimingPitchAndCamera": True}})
        with self.assertRaisesRegex(ValueError, "Runtime|Server"):
            self.run_validation()

    def test_full_event_runtime_evidence_can_upgrade_server_only(self):
        digest = validate.sha(self.deps["machine"] / "expected_events.json")
        self.save("machine", "runtime_validation.json", {"expectedEventsSha256": digest, "server": {"passed": True, "actualCount": 2, "exactTimingPitchAndCamera": True}})
        result = self.run_validation()
        self.assertEqual(result["status"], "server_verified")
        self.assertFalse(result["runtime"]["clientVerified"])

    def test_release_bound_to_validation_and_excludes_private_inputs(self):
        self.run_validation()
        output = self.root / "release"
        result = release.run(self.context(output))
        self.assertEqual(result["status"], "static_validated")
        with zipfile.ZipFile(output / "deliverables.zip") as archive:
            names = set(archive.namelist())
            self.assertIn("world/level.dat", names)
            self.assertIn("helper/pack.mcmeta", names)
            self.assertIn("performance.litematic", names)
            self.assertNotIn("master.mid", names)
            self.assertNotIn("project.json", names)
            self.assertNotIn(str(self.root), archive.read("release_manifest.json").decode())
            self.assertIn("test_show:start", archive.read("USAGE.md").decode())
        events = self.load("machine", "expected_events.json")
        events["notes"][0]["note"] = 7
        self.save("machine", "expected_events.json", events)
        with self.assertRaisesRegex(ValueError, "changed before release"):
            release.run(self.context(self.root / "other_release"))

    def test_corrupt_and_escaping_archives_rejected(self):
        resource = self.deps["sound"] / "resources.zip"
        resource.write_bytes(b"not zip")
        with self.assertRaises(zipfile.BadZipFile):
            self.run_validation()
        with zipfile.ZipFile(resource, "w") as archive:
            archive.writestr("pack.mcmeta", "{}")
            archive.writestr("../escape.ogg", "bad")
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            self.run_validation()

    def test_actual_export_corruption_rejected(self):
        region = self.deps["machine"] / "world/region/r.0.0.mca"
        region.write_bytes(region.read_bytes()[:8200])
        with self.assertRaisesRegex(ValueError, "truncated"):
            self.run_validation()

    def test_missing_embedded_controls_rejected(self):
        (self.deps["machine"] / "world/datapacks/helper/pack.mcmeta").unlink()
        with self.assertRaisesRegex(ValueError, "embeds identical"):
            self.run_validation()

    def test_changed_companion_refused_after_validation(self):
        self.run_validation()
        (self.deps["machine"] / "helper/pack.mcmeta").write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "companion changed"):
            release.run(self.context(self.root / "changed_release"))

    @unittest.skipUnless(shutil.which("node"), "Node.js required for control-pack integration")
    def test_original_song_compiles_and_packages_without_personal_paths(self):
        song = validate.fs_path(self.root / "independent_song")
        song.mkdir()
        make_midi = runpy.run_path(str(Path(__file__).with_name("test_music_sound.py")))["make_demo_midi"]
        make_midi(song / "original.mid")
        deps = {name: song / name for name in ("music", "sound", "machine", "visuals", "validate")}
        for path in deps.values():
            path.mkdir()
        config = {"slug": "integration", "title": 'Original "Phrase"', "inputs": {"midi": "original.mid"}, "sound": {"profile": "vanilla", "retrigger": True}, "visuals": {"enabled": False}}
        context = {"project": str(song), "root": str(Path(__file__).resolve().parents[1]), "config": config, "deps": {key: str(value) for key, value in deps.items()}}
        for name, module in (("music", music), ("sound", sound), ("machine", machine), ("validate", validate), ("release", release)):
            destination = song / name
            destination.mkdir(exist_ok=True)
            module.run({**context, "out": str(destination)})
        report = validate.read(song / "validate/report.json")
        self.assertEqual(report["counts"]["physicalEvents"], 10)
        self.assertTrue(report["exports"]["worldRoundtripPassed"])
        self.assertFalse(report["runtime"]["serverVerified"])
        info = validate.read(song / "machine/build_manifest.json")
        functions = song / "machine/helper/data" / info["namespace"] / "function"
        self.assertIn('subtitles int 1', (functions / 'fx_state.mcfunction').read_text(encoding='utf-8'))
        self.assertIn('#sub ' + info['objective'] + ' 1', (functions / 'scene/subtitles_on.mcfunction').read_text(encoding='utf-8'))
        for path in functions.rglob('*.mcfunction'):
            for line in path.read_text(encoding='utf-8').splitlines():
                if 'tellraw @a ' in line:
                    json.loads(line.split('tellraw @a ', 1)[1])
        with zipfile.ZipFile(song / "release/deliverables.zip") as archive:
            names = {Path(member).name for member in archive.namelist()}
            self.assertTrue({'game-performance.mid', 'arrangement-report.json'} <= names)
            for member in archive.namelist():
                if member.endswith((".json", ".md", ".mcfunction", ".mcmeta")):
                    text = archive.read(member).decode("utf-8")
                    self.assertNotIn(str(self.root), text, member)
                    self.assertIsNone(re.search(r"[A-Za-z]:[\\/]+(?:Users|Program)", text), member)


if __name__ == "__main__":
    unittest.main()
