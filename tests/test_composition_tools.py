"""Music workbench contracts: preserve evidence, revise deliberately, actually render differences."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from redstone_music.composition_tools import (import_composition,validate_composition,revise_composition,
    export_composition,review_composition,render_composition,plan_voicings,create_arrangement_study,_controls)
from redstone_music.music_tools import _hash
from redstone_music.midi import parse_midi

HAS_MIDO=importlib.util.find_spec('mido') is not None
HAS_AUDIO=importlib.util.find_spec('soundfile') is not None


@unittest.skipUnless(HAS_MIDO,'Install production extras for editable composition tests')
class CompositionTests(unittest.TestCase):
    def setUp(self):
        import mido
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.source=self.root/'master.mid'
        midi=mido.MidiFile(type=1,ticks_per_beat=960)
        meta=mido.MidiTrack([mido.MetaMessage('set_tempo',tempo=500000),
            mido.MetaMessage('time_signature',numerator=3,denominator=4),
            mido.MetaMessage('marker',text='START'),mido.MetaMessage('set_tempo',tempo=600000,time=3840),
            mido.MetaMessage('end_of_track',time=3840)])
        lead=mido.MidiTrack([mido.MetaMessage('track_name',name='Theme evidence'),
            mido.Message('program_change',channel=0,program=10),
            mido.Message('note_on',channel=0,note=69,velocity=96),
            mido.Message('control_change',channel=0,control=64,value=127,time=240),
            mido.Message('note_off',channel=0,note=69,velocity=0,time=240),
            mido.Message('control_change',channel=0,control=64,value=0,time=240),
            mido.Message('note_on',channel=0,note=72,velocity=83,time=240),
            mido.Message('note_off',channel=0,note=72,velocity=0,time=960),
            mido.MetaMessage('end_of_track',time=5760)])
        midi.tracks.extend([meta,lead]);midi.save(self.source)
        self.imported=import_composition(self.source,self.root/'work')
        self.project=Path(self.imported['composition'])

    def tearDown(self):self.tmp.cleanup()

    def patch(self,**values):
        return {'schemaVersion':1,'sourceProjectSha256':_hash(self.project),'beginTick':0,'endTick':7680,**values}

    def track(self,channel=1):
        return {'id':'new_harmony','name':'Chords','family':'chords','channel':channel,'program':4,
                'origin':'new_arrangement','notes':[{'id':'new:h1','channel':channel,'pitch':60,
                'startTick':960,'endTick':1920,'velocity':57,'origin':'new_arrangement'}]}

    def test_import_freezes_actual_source_and_keeps_tempo_and_pedal(self):
        d=json.loads(self.project.read_text(encoding='utf-8'))
        self.assertEqual((self.project.parent/'source.mid').read_bytes(),self.source.read_bytes())
        self.assertEqual(d['ppq'],960)
        self.assertEqual(len(d['tempoMap']),2)
        self.assertEqual(d['frozenSourceNoteIds'],['t1n0','t1n1'])
        self.assertEqual(d['tracks'][1]['notes'][0]['endTick'],480)
        self.assertTrue(validate_composition(self.project)['valid'])

    def test_frozen_note_revision_and_deletion_fail_before_output_creation(self):
        for op in ({'pitch':70},{'remove':True}):
            out=self.root/('bad-'+str(len(op)))
            with self.assertRaisesRegex(ValueError,'frozen'):
                revise_composition(self.project,self.patch(operations=[{'track':'source_1','note':'t1n0',**op}]),out)
            self.assertFalse(out.exists())

    def test_role_map_cannot_silently_weaken_default_or_partial_freeze(self):
        roles=self.root/'roles.json'
        roles.write_text('{"1":"special_lead"}',encoding='utf-8')
        report=import_composition(self.source,self.root/'labelled',roles=roles)
        self.assertEqual(report['frozenSourceNotes'],2)
        with self.assertRaisesRegex(ValueError,'missing_role'):
            import_composition(self.source,self.root/'wrong',('special_lead','missing_role'),roles)

    def test_appending_real_arrangement_preserves_all_original_control_events(self):
        import mido
        revised=revise_composition(self.project,self.patch(addTracks=[self.track()]),self.root/'candidate')
        out=self.root/'result.mid';report=export_composition(revised['composition'],out)
        self.assertTrue(report['frozenSourceNotesPreserved'])
        original=mido.MidiFile(self.source);new=mido.MidiFile(out)
        self.assertEqual(_controls(new)[:2],_controls(original))
        source_notes=parse_midi(self.source.read_bytes())['notes']
        actual=parse_midi(out.read_bytes())['notes']
        fields=('sourceTrack','sourceMidi','startTick','keyReleaseTick','endTick','velocity')
        self.assertEqual([tuple(n[k] for k in fields) for n in source_notes],
                         [tuple(n[k] for k in fields) for n in actual if n['sourceTrack']<2])

    def test_channel_collision_cannot_reprogram_the_frozen_lead(self):
        with self.assertRaisesRegex(ValueError,'unused MIDI channel'):
            revise_composition(self.project,self.patch(addTracks=[self.track(0)]),self.root/'collision')

    def test_editable_new_note_has_region_guard_and_parent_hash(self):
        first=revise_composition(self.project,self.patch(addTracks=[self.track()]),self.root/'first')
        path=Path(first['composition'])
        patch={'schemaVersion':1,'sourceProjectSha256':_hash(path),'beginTick':900,'endTick':2000,
               'operations':[{'track':'new_harmony','note':'new:h1','pitch':64}]}
        second=revise_composition(path,patch,self.root/'second')
        self.assertEqual(second['changed'],['new:h1'])
        d=json.loads(Path(second['composition']).read_text(encoding='utf-8'))
        self.assertEqual(d['tracks'][-1]['notes'][0]['pitch'],64)
        patch['operations'][0]['startTick']=800
        with self.assertRaisesRegex(ValueError,'escapes'):
            revise_composition(path,patch,self.root/'outside')
        patch['sourceProjectSha256']='0'*64
        with self.assertRaisesRegex(ValueError,'sourceProjectSha256'):
            revise_composition(path,patch,self.root/'stale')

    def test_direct_json_tampering_does_not_bypass_frozen_notes(self):
        d=json.loads(self.project.read_text(encoding='utf-8'));d['tracks'][1]['notes'][0]['pitch']=70
        self.project.write_text(json.dumps(d),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Frozen source note'):
            export_composition(self.project,self.root/'tampered.mid')
        d['frozenSourceNoteIds']=[]
        self.project.write_text(json.dumps(d),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'frozen contract'):
            validate_composition(self.project)

    def test_changed_source_bytes_are_rejected(self):
        with (self.project.parent/'source.mid').open('ab') as stream:stream.write(b'changed')
        with self.assertRaisesRegex(ValueError,'hash changed'):validate_composition(self.project)

    def test_pinned_upstream_voicing_is_actual_and_range_bounded(self):
        result=plan_voicings(['Am','F','C','G'],voices=3,low=48,high=67)
        self.assertEqual(len(result['voicings']),4)
        for notes,pcs in zip(result['voicings'],({9,0,4},{5,9,0},{0,4,7},{7,11,2})):
            self.assertTrue(all(48<=p<=67 and p%12 in pcs for p in notes))
            self.assertEqual(len(notes),3)
        self.assertFalse(result['artisticApproval'])
        self.assertEqual(len(result['upstreamCommit']),40)

    @unittest.skipUnless(HAS_AUDIO and shutil.which('ffmpeg'),'Audio/FFmpeg required for original study')
    def test_sixteen_bar_study_has_distinct_arrangements_and_identical_lead(self):
        result=create_arrangement_study(self.root/'study')
        self.assertEqual(result['bars'],16)
        a=parse_midi(Path(result['variants']['spacious']['midi']).read_bytes())
        b=parse_midi(Path(result['variants']['groove']['midi']).read_bytes())
        fields=('sourceMidi','startTick','keyReleaseTick','velocity')
        lead=lambda s:[tuple(n[k] for k in fields) for n in s['notes'] if n['sourceTrack']==1]
        self.assertEqual(lead(a),lead(b))
        self.assertNotEqual(len(a['notes']),len(b['notes']))
        for name in ('spacious','groove'):
            row=result['variants'][name]
            self.assertTrue(Path(row['mix']).stat().st_size>10000)
            self.assertTrue(row['solos'])
            self.assertFalse(row['actualMinecraftRecording'])
            gain=row['sharedMixAndSoloSafetyGain']
            for solo in row['solos']:
                metadata=json.loads(Path(solo['audio']+'.json').read_text(encoding='utf-8'))
                self.assertEqual(metadata['commonSafetyGain'],gain)
        self.assertFalse(result['artisticApproval'])


if __name__=='__main__':unittest.main()
