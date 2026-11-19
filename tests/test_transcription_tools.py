"""Audio source/time preservation and real optional backend integration."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from redstone_music import transcription_tools as tt

HAS_AUDIO=all(importlib.util.find_spec(n) for n in ('numpy','soundfile','mido','scipy'))


class BackendContractTests(unittest.TestCase):
    def test_probe_discovers_installs_without_claiming_model_validation(self):
        result=tt.transcription_capabilities()
        self.assertFalse(result['networkUsed'])
        self.assertFalse(result['artisticApproval'])
        self.assertEqual(set(result['backends']),set(tt.BACKENDS))
        self.assertTrue(all(not r['inferenceVerified'] for r in result['backends'].values()))

    def test_unknown_backend_and_gated_remote_model_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'basic-pitch or muscriptor'):
            tt.transcribe_audio('not-opened','not-created',backend='shell')
        with self.assertRaisesRegex(ValueError,'local .safetensors'):
            tt.transcribe_audio('not-opened','not-created',backend='muscriptor')
        with self.assertRaisesRegex(ValueError,'never accepts gated'):
            tt.transcribe_audio('not-opened','not-created',backend='muscriptor',allow_download=True)
        with self.assertRaisesRegex(ValueError,'without path or shell'):
            tt.separate_audio('not-opened','not-created','x;invoke.exe','not-opened')

    def test_missing_checkpoint_does_not_start_implicit_download(self):
        with self.assertRaisesRegex(ValueError,'local Beat This'):
            tt.track_beats('not-opened','not-created',checkpoint='small0')
        with self.assertRaisesRegex(ValueError,'local Beat This'):
            tt.track_beats('not-opened','not-created',checkpoint='https://untrusted.invalid/model.ckpt',allow_download=True)

    def test_risks_are_localized_and_do_not_rewrite_candidate(self):
        notes=[{'id':'a','sourceTrack':1,'sourceMidi':60,'sourceStartSeconds':.5,'sourceEndSeconds':.54},
               {'id':'b','sourceTrack':1,'sourceMidi':84,'sourceStartSeconds':1,'sourceEndSeconds':3.3}]
        original=copy.deepcopy(notes)
        result=tt.candidate_uncertainties(notes,3)
        self.assertEqual(notes,original)
        self.assertEqual(set(result['counts']),{'short_note_or_fragment','extends_beyond_source','large_melodic_leap_or_octave_alias'})
        self.assertFalse(result['instrumentAndNoteAccuracyVerified'])
        self.assertTrue(all(x['reviewRequired'] and 'timeSeconds' in x for x in result['items']))


@unittest.skipUnless(HAS_AUDIO,'Install production audio libraries')
class AuditionTests(unittest.TestCase):
    def setUp(self):
        import mido,numpy as np,soundfile as sf
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.source=self.root/'source.wav';self.midi=self.root/'candidate.mid'
        t=np.arange(66150)/22050
        sf.write(self.source,np.sin(2*np.pi*261.625565*t)*.3,22050,subtype='PCM_16')
        mid=mido.MidiFile(type=1,ticks_per_beat=480)
        mid.tracks.append(mido.MidiTrack([mido.MetaMessage('set_tempo',tempo=500000)]))
        mid.tracks.append(mido.MidiTrack([mido.Message('note_on',note=60,velocity=83,time=480),
                                         mido.Message('note_off',note=60,velocity=0,time=480),
                                         mido.MetaMessage('end_of_track',time=1920)]))
        mid.save(self.midi)

    def tearDown(self):self.temp.cleanup()

    def test_pair_audio_keeps_original_zero_and_reports_disagreement_not_accuracy(self):
        import mido,numpy as np,soundfile as sf
        changed=self.root/'changed.mid';mid=mido.MidiFile(self.midi)
        for message in mid.tracks[1]:
            if message.type in ('note_on','note_off'):message.note=62
        mid.save(changed)
        original_hash=hashlib.sha256(self.source.read_bytes()).hexdigest()
        result=tt.compare_transcriptions(self.source,[self.midi,changed],self.root/'compare',begin=.25,end=2.25)
        original,sr=sf.read(self.source);pair,pair_rate=sf.read(result['candidates'][0]['pairedAudio'])
        self.assertEqual(sr,pair_rate)
        self.assertEqual(pair.shape,(44100,2))
        self.assertGreater(float(np.corrcoef(original[5512:49612],pair[:,0])[0,1]),.99)
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(),original_hash)
        self.assertFalse(result['accuracyMeasured'])
        self.assertFalse(result['listeningVerified'])
        self.assertEqual(result['candidates'][0]['onsetsInExcerpt'],1)
        self.assertAlmostEqual(result['candidates'][0]['excerptSecondsAfterLastNote'],1.25)
        disagreements=json.loads(Path(result['disagreements']).read_text(encoding='utf-8'))['items']
        self.assertEqual({n['midi'] for n in disagreements},{60,62})
        self.assertTrue(all(abs(n['timeSeconds']-.5)<.001 for n in disagreements))
        with self.assertRaises(FileExistsError):
            tt.compare_transcriptions(self.source,[self.midi],self.root/'compare',end=2)

    def test_audio_and_boundaries_are_checked_before_output_creation(self):
        bad=self.root/'login.mp3';bad.write_text('<html>Sign in</html>')
        with self.assertRaises(ValueError):tt._input(bad)
        with self.assertRaises(ValueError):tt._input(self.midi)
        out=self.root/'never-created'
        with self.assertRaises(ValueError):tt.compare_transcriptions(self.source,[self.midi],out,end=4)
        self.assertFalse(out.exists())

    @unittest.skipUnless(os.environ.get('REDSTONE_BASIC_PITCH_PYTHON'),'Explicit optional Basic Pitch environment not configured')
    def test_real_basic_pitch_writes_raw_predictions_and_editable_timed_midi(self):
        result=tt.transcribe_audio(self.source,self.root/'basic',python=os.environ['REDSTONE_BASIC_PITCH_PYTHON'],
                                   model=os.environ.get('REDSTONE_BASIC_PITCH_MODEL'))
        self.assertTrue(Path(result['midi']).is_file())
        self.assertTrue(Path(result['rawModelOutput']).is_file())
        self.assertTrue(Path(result['rawNotes']).is_file())
        self.assertGreater(result['noteCount'],0)
        self.assertTrue(any(n['sourceMidi']==60 for n in result['notes']))
        self.assertFalse(result['musicalAccuracyVerified'])
        self.assertEqual(result['model']['sha256'],tt._hash(result['model']['path']))

    @unittest.skipUnless(os.environ.get('REDSTONE_BEAT_THIS_PYTHON') and os.environ.get('REDSTONE_BEAT_THIS_MODEL'),
                         'Explicit optional Beat This environment/checkpoint not configured')
    def test_real_beat_this_keeps_timestamp_units_and_checkpoint_hash(self):
        result=tt.track_beats(self.source,self.root/'beats',python=os.environ['REDSTONE_BEAT_THIS_PYTHON'],
                              checkpoint=os.environ['REDSTONE_BEAT_THIS_MODEL'])
        self.assertEqual(result['beatsSeconds'],sorted(set(result['beatsSeconds'])))
        self.assertTrue(all(0<=t<=3.2 for t in result['beatsSeconds']))
        self.assertEqual(result['model']['sha256'],tt._hash(os.environ['REDSTONE_BEAT_THIS_MODEL']))
        self.assertFalse(result['musicalAccuracyVerified'])


if __name__=='__main__':unittest.main()
