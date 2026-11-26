"""Behavioral checks for source preservation, calibration, phrase plans and media evidence."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from redstone_music import music, sound
from redstone_music.midi import parse_midi
from redstone_music.music_tools import (analyze_music, build_soundpack, compare_candidates,
    edit_music_region, inspect_source, plan_noteblocks, render_preview, sound_profile_dependencies,
    validate_sound_profile, validate_soundpack, analyze_audio, transcribe_melody, calibrate_sound_profile)
from redstone_music.toolkit_examples import create_learning_example, learning_midi_bytes, learning_sound_spec

HAS_AUDIO = all(importlib.util.find_spec(n) for n in ('mido', 'numpy', 'soundfile'))


@unittest.skipUnless(HAS_AUDIO, 'Install the music tool extras to run professional music integration checks')
class ProfessionalMusicTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.master = self.root / 'master.mid'
        self.master.write_bytes(learning_midi_bytes())

    def tearDown(self):
        self.tmp.cleanup()

    def bank(self):
        path = self.root / 'bank'
        if not path.exists():
            build_soundpack(learning_sound_spec(), path)
        return path

    def patch(self, **changes):
        score = parse_midi(self.master.read_bytes())
        voice = next(n for n in score['notes'] if n['family'] == 'voice')
        patch = {'schemaVersion': 1, 'sourceSha256': hashlib.sha256(self.master.read_bytes()).hexdigest(),
                 'beginSeconds': voice['sourceStartSeconds'], 'endSeconds': voice['sourceEndSeconds'],
                 'operations': [{'id': voice['id'], **changes}]}
        return patch, voice

    def test_original_example_has_structure_tempo_pedal_and_risk_lessons(self):
        result = create_learning_example(self.root / 'lesson')
        self.assertEqual(result['durationSeconds'], 36)
        self.assertEqual(result['notes'], 314)
        score = parse_midi(Path(result['master']).read_bytes())
        self.assertEqual(len(score['tempoMap']), 2)
        self.assertEqual(len(score['sections']), 4)
        self.assertTrue(any(n['keyReleaseTick'] < n['endTick'] for n in score['notes']))
        self.assertTrue((self.root / 'lesson/sound_bank/bad_center.profile.json').is_file())
        with self.assertRaises(FileExistsError):
            create_learning_example(self.root / 'lesson')

    def test_inspection_uses_real_bytes_and_rejects_login_html(self):
        self.assertEqual(inspect_source(self.master)['kind'], 'midi')
        fake = self.root / 'download.mid'
        fake.write_text('<html>Sign in first</html>')
        with self.assertRaisesRegex(ValueError, 'HTML'):
            inspect_source(fake)
        evil = self.root / 'bad.zip'
        with zipfile.ZipFile(evil, 'w') as z:
            z.writestr('../escape', 'bad')
        with self.assertRaisesRegex(ValueError, 'unsafe'):
            inspect_source(evil)

    def test_local_patch_changes_only_selected_pitch_and_retains_master(self):
        raw = self.master.read_bytes()
        voice_pitch = 70
        patch, voice = self.patch(pitch=voice_pitch)
        report = edit_music_region(self.master, patch, self.root / 'candidate.mid')
        before = parse_midi(raw)
        after = parse_midi((self.root / 'candidate.mid').read_bytes())
        changed = [(a, b) for a, b in zip(before['notes'], after['notes']) if a != b]
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0][0]['id'], voice['id'])
        self.assertEqual(changed[0][1]['sourceMidi'], voice_pitch)
        self.assertEqual(before['tempoMap'], after['tempoMap'])
        self.assertTrue(report['frozenControlsPreserved'])
        self.assertTrue(report['outsideRegionPreserved'])
        self.assertEqual(self.master.read_bytes(), raw)

    def test_patch_rejects_stale_source_outside_note_and_control_injection(self):
        patch, _ = self.patch(pitch=70)
        patch['sourceSha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'hash'):
            edit_music_region(self.master, patch, self.root / 'bad.mid')
        patch, _ = self.patch(pitch=70)
        patch['operations'][0]['id'] = 't1n0'
        with self.assertRaisesRegex(ValueError, 'outside'):
            edit_music_region(self.master, patch, self.root / 'bad.mid')
        patch, _ = self.patch(program=5)
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            edit_music_region(self.master, patch, self.root / 'bad.mid')
        self.assertFalse((self.root / 'bad.mid').exists())

    def test_patch_preserves_track_end_after_adding_earlier_note(self):
        score = parse_midi(self.master.read_bytes())
        patch = {'schemaVersion': 1, 'sourceSha256': hashlib.sha256(self.master.read_bytes()).hexdigest(),
                 'beginSeconds': 0, 'endSeconds': 2, 'operations': [],
                 'addNotes': [{'track': 2, 'channel': 1, 'pitch': 64, 'velocity': 70, 'startTick': 0, 'endTick': 100}]}
        edit_music_region(self.master, patch, self.root / 'added.mid')
        self.assertEqual(parse_midi((self.root / 'added.mid').read_bytes())['durationSeconds'], score['durationSeconds'])

    def test_calibrated_pack_references_exact_profile_sample_bytes(self):
        bank = self.bank()
        profile = validate_sound_profile(bank / 'profile.json')
        self.assertEqual(len(profile['slots']), 7)
        self.assertEqual(validate_soundpack(bank / 'resources.zip', bank / 'profile.json')['eventsVerified'], 7)
        self.assertEqual(len(sound_profile_dependencies(bank / 'profile.json')), 8)
        calibration = json.loads((bank / 'calibration.json').read_text())
        row = calibration['slots'][0]
        self.assertAlmostEqual(row['durationAtNotesSeconds']['0'], row['durationAtNotesSeconds']['24'] * 4)

    def test_independent_roles_cannot_hide_a_shared_vanilla_sound_event(self):
        spec = learning_sound_spec()
        spec['slots']['voice']['instrument'] = spec['slots']['harmony']['instrument']
        with self.assertRaisesRegex(ValueError, 'share vanilla event'):
            build_soundpack(spec, self.root / 'bad_bank')
        self.assertFalse((self.root / 'bad_bank').exists())

    def test_modified_sample_invalidates_profile_and_pack(self):
        bank = self.bank()
        sample = bank / 'samples/voice.ogg'
        sample.write_bytes(sample.read_bytes() + b'changed')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            validate_sound_profile(bank / 'profile.json')

    def test_phrase_planner_keeps_one_timbre_and_discloses_transposition(self):
        profile = self.bank() / 'profile.json'
        planned = plan_noteblocks(self.master, self.root / 'plan', profile)
        self.assertEqual(len({n['parentId'] for n in planned['candidates']}), 314)
        self.assertTrue(all(0 <= n['note'] <= 24 for n in planned['candidates']))
        self.assertTrue(all(len({n['slot'] for n in planned['candidates'] if n['parentId'] in d['noteIds']}) == 1 for d in planned['phraseDecisions']))
        self.assertTrue(any(d['role'] == 'sub_bass' and d['transpose'] == 12 for d in planned['phraseDecisions']))
        voice = [n for n in planned['candidates'] if n['family'] == 'voice']
        self.assertTrue(any(n['kind'] == 'retrigger' for n in voice))
        for n in voice:
            if n['kind'] == 'retrigger':
                onset = next(x for x in voice if x['id'] == n['parentId'])
                self.assertEqual((n['gt'] - onset['gt']) % 18, 0)

    def test_explicit_plan_drives_timbre_and_retrigger_policy(self):
        profile = self.bank() / 'profile.json'
        automatic = plan_noteblocks(self.master, profile=profile)
        decisions = json.loads(json.dumps(automatic['phraseDecisions']))
        for d in decisions:
            if d['role'] == 'voice':
                d['slot'], d['transpose'] = 'lead', 0
        plan = {'schemaVersion': 1, 'profileId': 'original_learning', 'decisions': decisions}
        explicit = plan_noteblocks(self.master, profile=profile, adaptation_plan=plan)
        self.assertTrue(explicit['explicitAdaptationApplied'])
        self.assertEqual({n['instrument'] for n in explicit['candidates'] if n['family'] == 'voice'}, {'banjo'})
        self.assertFalse(any(n['kind'] == 'retrigger' for n in explicit['candidates'] if n['family'] == 'voice'))
        plan['decisions'].pop()
        with self.assertRaisesRegex(ValueError, 'every source onset'):
            plan_noteblocks(self.master, profile=profile, adaptation_plan=plan)

    def test_actual_sample_spectrum_detects_false_declared_center(self):
        bank = self.bank()
        profile = json.loads((bank / 'profile.json').read_text())
        profile['slots']['voice']['rootMidi'] += 12
        bad = bank / 'bad_center.json'
        bad.write_text(json.dumps(profile))
        validate_sound_profile(bad)  # Format/hash checks alone cannot identify it.
        calibration = calibrate_sound_profile(bad)
        finding = next(f for f in calibration['findings'] if f['slot'] == 'voice')
        self.assertAlmostEqual(finding['cents'], -1200, delta=2)

    def test_sound_fingerprints_include_all_referenced_samples(self):
        bank = self.bank()
        deps = sound.fingerprint_inputs({'project': str(self.root), 'config': {'inputs': {'soundProfile': str(bank / 'profile.json')}}})
        self.assertEqual(len(deps), 8)
        self.assertIn((bank / 'samples/voice.ogg').resolve(), deps)

    def test_custom_sound_stage_imports_profile_pack_and_self_contained_samples(self):
        bank = self.bank()
        config = {'inputs': {'midi': str(self.master), 'soundProfile': str(bank / 'profile.json'), 'soundPack': str(bank / 'resources.zip')},
                  'sound': {'profile': 'original_learning'}}
        ctx = {'project': str(self.root), 'root': str(Path(__file__).resolve().parents[1]), 'config': config,
               'out': str(self.root / 'music'), 'deps': {}}
        music.run(ctx)
        ctx.update(out=str(self.root / 'sound'), deps={'music': str(self.root / 'music')})
        report = sound.run(ctx)
        self.assertEqual(report['profileId'], 'original_learning')
        validate_sound_profile(self.root / 'sound/sound_profile.json')
        self.assertEqual((self.root / 'sound/resources.zip').read_bytes(), (bank / 'resources.zip').read_bytes())

    def test_preview_is_real_audio_and_reports_approximation(self):
        import numpy as np
        import soundfile as sf
        profile = self.bank() / 'profile.json'
        events = plan_noteblocks(self.master, profile=profile)
        preview = render_preview(events, self.root / 'sample_preview.wav', mode='noteblock', profile=profile, begin=8, end=12)
        audio, sr = sf.read(preview['output'])
        self.assertEqual(len(audio) / sr, 5)
        self.assertGreater(float(np.max(np.abs(audio))), .01)
        self.assertFalse(preview['actualMinecraftRecording'])
        self.assertFalse(preview['listeningVerified'])
        with self.assertRaisesRegex(ValueError, 'new'):
            render_preview(events, self.root / 'sample_preview.wav', mode='noteblock', profile=profile)

    def test_analysis_returns_evidence_without_artistic_score(self):
        report = analyze_music(self.master)
        self.assertEqual(report['notes'], 314)
        self.assertGreaterEqual(report['peakPolyphony'], 4)
        self.assertFalse(report['artisticQualityScored'])
        self.assertFalse(report['listeningVerified'])

    def test_excerpt_tail_does_not_include_later_onsets(self):
        import numpy as np
        import soundfile as sf
        profile = self.bank() / 'profile.json'
        events = plan_noteblocks(self.master, profile=profile)
        events['candidates'] = [dict(events['candidates'][0], gt=22, q=22)]
        result = render_preview(events, self.root / 'silent_before_onset.wav', mode='noteblock', profile=profile, end=1)
        audio, _ = sf.read(result['output'])
        self.assertEqual(float(np.max(np.abs(audio))), 0)

    @unittest.skipUnless(importlib.util.find_spec('librosa'), 'Install audio extras for real feature analysis')
    def test_real_audio_features_are_explicit_candidates(self):
        render_preview(self.master, self.root / 'reference.wav', end=4)
        result = analyze_audio(self.root / 'reference.wav')
        self.assertEqual(result['backend'], 'librosa')
        self.assertEqual(len(result['meanPitchClassEnergy']), 12)
        self.assertGreater(result['analysisFrames'], 0)
        self.assertFalse(result['artisticQualityScored'])

    @unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg executable is optional')
    def test_matched_ab_does_not_change_originals_or_within_mix_balance(self):
        import numpy as np
        import soundfile as sf
        rate = 22050
        t = np.arange(rate * 4) / rate
        a = np.column_stack([.1 * np.sin(2 * np.pi * 440 * t), .05 * np.sin(2 * np.pi * 440 * t)])
        sf.write(self.root / 'a.wav', a, rate)
        sf.write(self.root / 'b.wav', a * 2, rate)
        before = [(self.root / n).read_bytes() for n in ('a.wav', 'b.wav')]
        result = compare_candidates(self.root / 'a.wav', self.root / 'b.wav', self.root / 'ab')
        after_a, _ = sf.read(result['candidates'][0]['output'])
        after_b, _ = sf.read(result['candidates'][1]['output'])
        self.assertLess(float(np.max(np.abs(after_a - after_b))), .001)
        self.assertAlmostEqual(float(np.sqrt(np.mean(after_a[:, 0] ** 2)) / np.sqrt(np.mean(after_a[:, 1] ** 2))), 2, places=2)
        self.assertEqual(before, [(self.root / n).read_bytes() for n in ('a.wav', 'b.wav')])

    @unittest.skipUnless(importlib.util.find_spec('swift_f0'), 'Install pitch extras for real local F0 test')
    def test_local_f0_transcription_records_confidence_and_candidate_pitch(self):
        import numpy as np
        import soundfile as sf
        sr = 22050
        y = np.zeros(sr * 3)
        t = np.arange(round(.8 * sr)) / sr
        for i, key in enumerate((69, 72)):
            y[round((.2 + i * 1.2) * sr):round((.2 + i * 1.2) * sr) + len(t)] = .2 * np.sin(2 * np.pi * 440 * 2 ** ((key - 69) / 12) * t)
        sf.write(self.root / 'line.wav', y, sr)
        result = transcribe_melody(self.root / 'line.wav', self.root / 'transcribed')
        self.assertEqual([n['midi'] for n in result['notes']], [69, 72])
        self.assertTrue(Path(result['pitchFrames']).is_file())
        self.assertFalse(result['polyphonicTranscription'])


if __name__ == '__main__':
    unittest.main()
