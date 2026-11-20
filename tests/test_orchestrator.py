import json
import os
from pathlib import Path
import socket
import struct
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from redstone_music import core


def midi_bytes(key=60):
    track = bytes([0, 0x90, key, 90, 96, 0x80, key, 0, 0, 0xff, 0x2f, 0])
    return b'MThd' + struct.pack('>IHHH', 6, 0, 1, 96) + b'MTrk' + struct.pack('>I', len(track)) + track


class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        # Windows sandbox temp roots can already exceed 160 characters. Keep
        # fixture paths short enough for non-long-path-enabled Python builds.
        runtime = core.REPO_ROOT / '.runtime'
        runtime.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='core_test_', dir=runtime)
        self.base = Path(self.temp.name)
        self.project = self.base / 'test-song'
        self.midi = self.base / 'original.mid'
        self.midi.write_bytes(midi_bytes())
        core.initialize(self.project, 'Test Song', self.midi)
        self.calls = []

        def fake(ctx):
            stage = Path(ctx['out']).name.split('-')[0]
            self.calls.append(stage)
            core.atomic_json(Path(ctx['out']) / 'result.json', {'stage': stage, 'title': ctx['config']['title']})
            return {'candidate': True}

        self.fake = fake
        self.overrides = {stage: fake for stage in core.STAGES}

    def tearDown(self):
        self.temp.cleanup()

    def run_to(self, until='release', **kwargs):
        return core.run_pipeline(self.project, until, overrides=self.overrides, **kwargs)

    def update(self, change):
        path = self.project / 'project.json'
        data = core.read_json(path)
        change(data)
        core.atomic_json(path, data)

    def test_windows_sharing_conflict_does_not_rebuild_valid_staging(self):
        original_rename = Path.rename
        attempted = []

        def sharing_conflict_once(path, target):
            attempted.append(path)
            if len(attempted) == 1:
                error = PermissionError('directory briefly in use')
                error.winerror = 5
                raise error
            return original_rename(path, target)

        with patch.object(Path, 'rename', sharing_conflict_once):
            state = self.run_to('music')
        self.assertEqual(self.calls, ['music'])
        self.assertEqual(attempted, [attempted[0], attempted[0]])
        record = state['stages']['music']
        self.assertTrue(core.artifact_valid(self.project/record['artifact'], record))
        self.assertEqual(record['attempts'], 1)

    def test_resumes_and_reuses_verified_artifacts(self):
        first = self.run_to()
        self.assertEqual(first['status'], 'candidate_ready')
        self.assertEqual(self.calls, list(core.STAGES))
        self.calls.clear()
        second = self.run_to()
        self.assertEqual(self.calls, [])
        self.assertTrue(all(x['action'] == 'cached' for x in second['lastRun']))
        self.assertEqual(first['stages']['release']['fingerprint'], second['stages']['release']['fingerprint'])

    def test_visual_config_invalidates_only_visual_and_downstream(self):
        self.run_to()
        self.calls.clear()
        self.update(lambda c: c['visuals'].update(enabled=False))
        self.run_to()
        self.assertEqual(self.calls, ['visuals', 'validate', 'release'])

    def test_runtime_change_invalidates_machine_and_downstream(self):
        self.run_to()
        self.calls.clear()
        self.update(lambda c: c['runtime'].update(serverValidation=True))
        self.run_to()
        self.assertEqual(self.calls, ['machine', 'visuals', 'validate', 'release'])

    def test_input_file_content_invalidates_all_stages(self):
        self.run_to()
        self.calls.clear()
        self.midi.write_bytes(midi_bytes(64))
        self.run_to()
        self.assertEqual(self.calls, list(core.STAGES))

    def test_changed_stage_code_invalidates_only_descendants(self):
        self.run_to()
        self.calls.clear()

        def other(ctx):
            self.calls.append('sound')
            core.atomic_json(Path(ctx['out']) / 'result.json', {'changed': True})
            return {'candidate': True}

        self.overrides['sound'] = other
        self.run_to()
        self.assertEqual(self.calls, ['sound', 'machine', 'visuals', 'validate', 'release'])

    def test_corrupt_artifact_is_rebuilt_and_preserved_in_quarantine(self):
        first = self.run_to()
        music = self.project / first['stages']['music']['artifact']
        (music / 'result.json').write_text('corruption', encoding='utf-8')
        self.calls.clear()
        self.run_to()
        self.assertEqual(self.calls, ['music'])
        self.assertTrue(list((self.project / '.quarantine').glob('music-*')))
        self.assertEqual(core.read_json(music / 'result.json')['stage'], 'music')

    def test_extra_file_is_not_silently_accepted(self):
        first = self.run_to('music')
        music = self.project / first['stages']['music']['artifact']
        (music / 'injected.txt').write_text('untracked')
        self.calls.clear()
        self.run_to('music')
        self.assertEqual(self.calls, ['music'])
        self.assertFalse((music / 'injected.txt').exists())

    def test_corrupt_manifest_is_quarantined_and_rebuilt(self):
        first = self.run_to('music')
        music = self.project / first['stages']['music']['artifact']
        (music / 'stage_manifest.json').write_text('broken JSON', encoding='utf-8')
        self.calls.clear()
        self.run_to('music')
        self.assertEqual(self.calls, ['music'])
        self.assertEqual(core.read_json(music / 'stage_manifest.json')['stage'], 'music')

    def test_external_stage_asset_content_is_fingerprinted(self):
        asset = self.base / 'controls.mjs'
        asset.write_text('first', encoding='utf-8')
        module = SimpleNamespace(__file__=core.__file__, DEPENDENCY_FILES=[str(asset)])
        config = core.load_config(self.project)
        first = core.input_fingerprint(self.project, config, 'machine', {}, module)
        asset.write_text('second', encoding='utf-8')
        second = core.input_fingerprint(self.project, config, 'machine', {}, module)
        self.assertNotEqual(first, second)

    def test_loaded_module_source_change_requires_new_process(self):
        source = self.base / 'stage.py'
        source.write_text('first', encoding='utf-8')
        module = SimpleNamespace(__file__=str(source))
        config = core.load_config(self.project)
        with patch.object(core, '_module_sources', side_effect=[{'temporary_stage.py': 'hash-a'}, {'temporary_stage.py': 'hash-b'}]):
            key = str(Path(core.__file__).parent / 'temporary_stage.py')
            try:
                core.input_fingerprint(self.project, config, 'machine', {}, module)
                with self.assertRaisesRegex(core.PipelineError, 'restart the CLI'):
                    core.input_fingerprint(self.project, config, 'machine', {}, module)
            finally:
                core._IMPORTED_SOURCE_HASHES.pop(key, None)

    def test_midrun_input_change_is_not_certified(self):
        def mutate_input(ctx):
            self.midi.write_bytes(midi_bytes(67))
            (Path(ctx['out']) / 'result.json').write_text('{}', encoding='utf-8')
            return {'ok': True}
        self.overrides['music'] = mutate_input
        with self.assertRaisesRegex(core.PipelineError, 'changed during execution'):
            self.run_to('music')
        self.assertEqual(core.read_json(self.project / 'state.json')['stages']['music']['status'], 'failed')

    def test_failure_is_not_cached_and_creates_specialist_repair_task(self):
        def broken(ctx):
            (Path(ctx['out']) / 'diagnostic.txt').write_text('failed attempt')
            raise ValueError('bad sound routing')
        self.overrides['sound'] = broken
        with self.assertRaisesRegex(core.PipelineError, 'sound'):
            self.run_to()
        failed = core.read_json(self.project / 'state.json')
        self.assertEqual(failed['stages']['sound']['status'], 'failed')
        self.assertTrue((self.project / failed['stages']['sound']['diagnostics']).exists())
        task = core.list_tasks(self.project)[0]
        self.assertEqual(task['role'], 'sound')
        self.overrides['sound'] = self.fake
        self.calls.clear()
        self.run_to()
        self.assertNotIn('music', self.calls)
        self.assertIn('sound', self.calls)

    def test_live_lock_never_stolen_and_dead_lock_recovered(self):
        with core.project_lock(self.project):
            with self.assertRaisesRegex(core.PipelineError, 'locked'):
                with core.project_lock(self.project):
                    self.fail('second lock entered')
        core.atomic_json(self.project / '.pipeline.lock', {'pid': 123456789, 'host': socket.gethostname(), 'token': 'old'})
        with patch.object(core, 'pid_alive', return_value=False):
            with core.project_lock(self.project):
                self.assertNotEqual(core.read_json(self.project / '.pipeline.lock')['token'], 'old')
        self.assertFalse((self.project / '.pipeline.lock').exists())

    def test_failure_budget_is_bounded_for_unchanged_input(self):
        attempts = []

        def broken(ctx):
            attempts.append(1)
            raise ValueError('deterministic failure')

        self.overrides['music'] = broken
        for _ in range(3):
            with self.assertRaises(core.PipelineError):
                self.run_to('music')
        self.assertEqual(len(attempts), 2)

    def test_invalid_output_path_rejected(self):
        with self.assertRaises(core.PipelineError):
            core.owned(self.project, '../outside')
        with self.assertRaises(core.PipelineError):
            core.initialize(self.project, 'Cannot overwrite')
        for slug in ['../escape', 'CON', 'con', 'bad--name', 'a/b']:
            with self.assertRaises(core.PipelineError):
                core.validate_slug(slug)

    def test_missing_music_can_be_claimed_and_imported(self):
        self.update(lambda c: c['inputs'].update(midi=None))
        state = self.run_to()
        self.assertEqual(state['status'], 'awaiting_agent')
        task = core.claim_task(self.project, state['task'], 'music-specialist')
        output = self.project / 'tasks' / task['id'] / 'output' / 'master.mid'
        output.write_bytes(midi_bytes())
        result = output.parent.parent / 'result.json'
        core.atomic_json(result, {'outputs': {'midi': output.relative_to(self.project).as_posix()}})
        closed = core.complete_task(self.project, task['id'], result)
        self.assertEqual(closed['status'], 'completed')
        self.assertFalse(closed['stagePassGranted'])
        self.assertEqual(core.complete_task(self.project, task['id'], result)['status'], 'completed')
        self.assertEqual(self.run_to()['status'], 'candidate_ready')

    def test_task_stale_result_and_path_escape_rejected(self):
        task = core.create_task(self.project, 'sound', 'Improve clarity')
        review = self.project / 'tasks' / task['id'] / 'output' / 'review.json'
        core.atomic_json(review, {'summary': 'Test', 'evidence': [], 'limitations': []})
        result = review.parent.parent / 'result.json'
        core.atomic_json(result, {'outputs': {'review': str(review)}})
        self.update(lambda c: c.update(title='Changed'))
        with self.assertRaisesRegex(core.PipelineError, 'stale'):
            core.complete_task(self.project, task['id'], result)
        task2 = core.create_task(self.project, 'sound', 'Current review')
        result2 = self.project / 'tasks' / task2['id'] / 'result.json'
        core.atomic_json(result2, {'outputs': {'review': str(review)}})
        with self.assertRaisesRegex(core.PipelineError, 'within'):
            core.complete_task(self.project, task2['id'], result2)

    def test_role_patch_is_constrained_and_does_not_grant_pass(self):
        task = core.create_task(self.project, 'visuals', 'Reduce density')
        folder = self.project / 'tasks' / task['id']
        review = folder / 'output/review.json'
        core.atomic_json(review, {'summary': 'reduce decoration', 'evidence': [], 'limitations': ['not replayed']})
        result = folder / 'result.json'
        core.atomic_json(result, {'outputs': {'review': str(review)}, 'configPatch': {'runtime': {'java': 'evil.exe'}}})
        with self.assertRaises(core.PipelineError):
            core.complete_task(self.project, task['id'], result)
        core.atomic_json(result, {'outputs': {'review': str(review)}, 'configPatch': {'visuals': {'enabled': False}}})
        closed = core.complete_task(self.project, task['id'], result)
        self.assertFalse(closed['stagePassGranted'])
        self.assertFalse(core.load_config(self.project)['visuals']['enabled'])

    def test_truncated_midi_task_result_rejected(self):
        self.update(lambda c: c['inputs'].update(midi=None))
        task_id = self.run_to()['task']
        folder = self.project / 'tasks' / task_id
        midi = folder / 'output/master.mid'
        midi.write_bytes(b'MThd')
        result = folder / 'result.json'
        core.atomic_json(result, {'outputs': {'midi': str(midi)}})
        with self.assertRaises(ValueError):
            core.complete_task(self.project, task_id, result)
        self.assertIsNone(core.load_config(self.project)['inputs']['midi'])

    def test_demo_source_is_original_valid_and_resume_never_overwrites(self):
        from redstone_music.demo import initialize_demo, demo_midi_bytes
        from redstone_music.midi import parse_midi
        demo = self.base / 'demo'
        initialize_demo(demo)
        score = parse_midi(demo_midi_bytes())
        self.assertEqual(len(score['notes']), 10)
        self.assertEqual(score['durationSeconds'], 8)
        source = demo / 'sources/demo.mid'
        original = core.hash_file(source)
        initialize_demo(demo)
        self.assertEqual(core.hash_file(source), original)

    def test_run_summary_includes_release_paths_and_boundaries(self):
        result = self.run_to()
        summary = core.summarize_run(self.project, result)
        self.assertEqual(summary['status'], 'candidate_ready')
        self.assertTrue(summary['releasePath'].endswith('deliverables.zip'))
        self.assertEqual(len(summary['stages']), 6)
        self.assertEqual(summary['artisticApproval'], 'not_inferred_from_technical_checks')


if __name__ == '__main__':
    unittest.main()
