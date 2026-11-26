"""Music interchange tests use an original synthetic phrase, never song assets."""
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from redstone_music.midi import parse_midi
from redstone_music import music, sound


def vlq(value):
    values = [value & 127]
    value >>= 7
    while value:
        values.insert(0, (value & 127) | 128)
        value >>= 7
    return bytes(values)


def midi_bytes(tracks, ppq=480):
    chunks = []
    for events in tracks:
        raw = b''.join(vlq(delta) + payload for delta, payload in events)
        if not raw.endswith(b'\xff\x2f\x00'):
            raw += b'\x00\xff\x2f\x00'
        chunks.append(b'MTrk' + struct.pack('>I', len(raw)) + raw)
    return b'MThd' + struct.pack('>IHHH', 6, 1 if len(tracks) > 1 else 0, len(tracks), ppq) + b''.join(chunks)


def make_demo_midi(path):
    """Write an original eight-second C major test phrase (CC0)."""
    conductor = [(0, b'\xff\x51\x03\x07\xa1\x20'), (0, b'\xff\x06\x05INTRO'),
                 (3840, b'\xff\x06\x04TAIL'), (3840, b'\xff\x2f\x00')]
    melody = [(0, b'\xff\x03\x05Theme'), (0, bytes([0xC0, 80]))]
    for i, pitch in enumerate((60, 64, 67, 72, 71, 67, 64, 60)):
        melody.extend([(0 if i == 0 else 120, bytes([0x90, pitch, 92])),
                       (840, bytes([0x80, pitch, 0]))])
    melody.append((120, b'\xff\x2f\x00'))
    bass = [(0, bytes([0xC1, 33])), (0, bytes([0x91, 36, 75])),
            (3840, bytes([0x81, 36, 0])), (0, bytes([0x91, 43, 75])),
            (3840, bytes([0x81, 43, 0]))]
    Path(path).write_bytes(midi_bytes([conductor, melody, bass]))
    return Path(path)


class MidiTests(unittest.TestCase):
    def test_tempo_map_not_fixed_bpm(self):
        data = midi_bytes([[(0, b'\x90\x3c\x64'), (480, b'\xff\x51\x03\x0f\x42\x40'),
                            (480, b'\x80\x3c\x00')]])
        score = parse_midi(data)
        self.assertAlmostEqual(score['notes'][0]['sourceEndSeconds'], 1.5)
        self.assertEqual(score['tempoMap'][1]['tick'], 480)

    def test_pedal_extends_note_until_release(self):
        data = midi_bytes([[(0, b'\xb0\x40\x7f'), (0, b'\x90\x3c\x64'),
                            (480, b'\x80\x3c\x00'), (480, b'\xb0\x40\x00')]])
        note = parse_midi(data)['notes'][0]
        self.assertEqual(note['keyReleaseTick'], 480)
        self.assertEqual(note['endTick'], 960)
        self.assertEqual(note['sourceEndSeconds'], 1.0)

    def test_drum_roles(self):
        data = midi_bytes([[(0, bytes([0x99, 36, 100])), (60, bytes([0x89, 36, 0])),
                            (0, bytes([0x99, 42, 60])), (60, bytes([0x89, 42, 0]))]])
        self.assertEqual([n['family'] for n in parse_midi(data)['notes']], ['kick', 'hats'])

    def test_running_status(self):
        score = parse_midi(midi_bytes([[(0, b'\x90\x3c\x64'), (120, b'\x3c\x00')]]))
        self.assertEqual(len(score['notes']), 1)

    def test_bad_pairs_and_html_are_rejected(self):
        for data in (b'<html>Error</html>', midi_bytes([[(0, b'\x90\x3c\x64')]]),
                     midi_bytes([[(10, b'\x80\x3c\x00')]])):
            with self.subTest(data=data[:20]), self.assertRaises(ValueError):
                parse_midi(data)

    def test_unclosed_track_and_truncation_are_rejected(self):
        data = midi_bytes([[(0, b'\x90\x3c\x64'), (480, b'\x80\x3c\x00')]])
        with self.assertRaises(ValueError):
            parse_midi(data[:-1])


class AdaptationTests(unittest.TestCase):
    def context(self, project, out, config, deps=None):
        return {'project': str(project), 'root': str(Path(__file__).resolve().parents[1]),
                'config': config, 'deps': deps or {}, 'out': str(out)}

    def test_default_sound_rejects_timbre_switches_and_uses_measured_slot_only(self):
        from redstone_music.music_tools import plan_noteblocks
        source = midi_bytes([[
            (0,b'\xff\x03\x05Theme'), (0,b'\x90\x3d\x55'), (960,b'\x80\x3d\x00'),
            (960,b'\x90\x52\x55'), (960,b'\x80\x52\x00'),
        ]])
        score = parse_midi(source)
        with self.assertRaisesRegex(ValueError, 'MIDI 61..82.*rootMidi=72'):
            plan_noteblocks(score)
        profile = {'schemaVersion':1,'id':'study','roles':{'theme_attack':'lead'},
                   'slots':{'lead':{'instrument':'harp','baseBlock':'minecraft:dirt','rootMidi':72}}}
        events = plan_noteblocks(score, profile=profile)['candidates']
        self.assertEqual([(n['slot'],n['note'],n['transpose'],n['kind']) for n in events],
                         [('lead',1,0,'onset'),('lead',22,0,'onset')])

    def test_independent_phrase_master_unchanged_and_sources_accounted(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            source = make_demo_midi(p / 'demo.mid')
            original = source.read_bytes()
            config = {'inputs': {'midi': 'demo.mid'}, 'sound': {'profile': 'vanilla', 'retrigger': True}}
            music.run(self.context(p, p / 'music', config))
            result = sound.run(self.context(p, p / 'sound', config, {'music': str(p / 'music')}))
            score = json.loads((p / 'music/score.json').read_text(encoding='utf-8'))
            events = json.loads((p / 'sound/events.json').read_text(encoding='utf-8'))
            self.assertAlmostEqual(score['durationSeconds'], 8)
            self.assertEqual({n['id'] for n in score['notes']}, {n['parentId'] for n in events['candidates']})
            self.assertTrue(all(0 <= n['note'] <= 24 for n in events['candidates']))
            self.assertEqual((p / 'music/master.mid').read_bytes(), original)
            self.assertEqual(source.read_bytes(), original)
            self.assertFalse(result['listeningVerified'])

    def test_explicit_legacy_voice_long_note_produces_tagged_retriggers(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / 'voice.mid').write_bytes(midi_bytes([[(0, b'\xc0\x35'), (0, b'\x90\x3c\x64'), (1920, b'\x80\x3c\x00')]]))
            config = {'inputs': {'midi': 'voice.mid'}, 'sound': {'retrigger': True,'adapter':'legacy-vanilla'}}
            music.run(self.context(p, p / 'music', config))
            sound.run(self.context(p, p / 'sound', config, {'music': str(p / 'music')}))
            events = json.loads((p / 'sound/events.json').read_text(encoding='utf-8'))['candidates']
            self.assertEqual(sum(n['kind'] == 'onset' for n in events), 1)
            self.assertGreater(sum(n['kind'] == 'retrigger' for n in events), 1)
            self.assertTrue(all(n['parentId'] == 't0n0' for n in events))

    def test_low_role_gets_one_disclosed_octave_shift(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / 'low.mid').write_bytes(midi_bytes([[(0, b'\xc0\x21'), (0, b'\x90\x18\x64'), (480, b'\x80\x18\x00'),
                                                   (0, b'\x90\x24\x64'), (480, b'\x80\x24\x00')]]))
            config = {'inputs': {'midi': 'low.mid'}}
            music.run(self.context(p, p / 'music', config))
            sound.run(self.context(p, p / 'sound', config, {'music': str(p / 'music')}))
            data = json.loads((p / 'sound/events.json').read_text(encoding='utf-8'))
            self.assertEqual({n['transpose'] for n in data['candidates']}, {12})
            report = json.loads((p / 'sound/sound_report.json').read_text(encoding='utf-8'))
            self.assertEqual(report['transformations'][0]['type'], 'whole-role-octave-transpose')

    def test_custom_profile_needs_explicit_pack(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            make_demo_midi(p / 'demo.mid')
            config = {'inputs': {'midi': 'demo.mid'}, 'sound': {'profile': 'unknown-custom'}}
            music.run(self.context(p, p / 'music', config))
            with self.assertRaises(ValueError):
                sound.run(self.context(p, p / 'sound', config, {'music': str(p / 'music')}))

    def test_nevada_approved_events_remain_exact(self):
        root = Path(__file__).resolve().parents[1]
        baseline = root / 'nevada/build/scene_full_v01/expected_events.json'
        if not baseline.exists():
            self.skipTest('Private regression assets are not distributed')
        original = baseline.read_bytes()
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            config = {'inputs': {'approvedEvents': str(baseline)}}
            music.run(self.context(p, p / 'music', config))
            sound.run(self.context(p, p / 'sound', config, {'music': str(p / 'music')}))
            events = json.loads((p / 'sound/events.json').read_text(encoding='utf-8'))
            self.assertEqual(events['candidates'], json.loads(original)['notes'])
            self.assertEqual(len(events['candidates']), 6604)
            self.assertEqual(baseline.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()

