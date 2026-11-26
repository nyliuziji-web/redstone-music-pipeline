"""Real sample/range/solo checks; no game or artistic pass is inferred."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import soundfile as sf

from redstone_music.music_tools import plan_noteblocks, validate_soundpack
from redstone_music.timbre_tools import design_timbre, build_palette, audit_palette, compare_timbres, create_timbre_study


class TimbreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)

    def tearDown(self):self.tmp.cleanup()

    def recipe(self,**kwargs):
        return {'schemaVersion':1,'kind':'pluck','rootMidi':72,'seconds':.7,'gain':.18,**kwargs}

    def spec(self):
        return {'schemaVersion':1,'id':'tone_test','slots':{
            'lead':{'rootMidi':72,'instrument':'banjo','baseBlock':'minecraft:hay_block',
                    'recipe':self.recipe(),'sustain':{'mode':'natural'}},
            'foundation':{'rootMidi':42,'instrument':'bass','baseBlock':'minecraft:oak_planks',
                    'recipe':self.recipe(kind='bass',rootMidi=42,seconds=.8,gain=.12),
                    'sustain':{'mode':'natural'}}},'roles':{'theme_attack':'lead','sub_bass':'foundation'}}

    def score(self):
        notes=[]
        for i,pitch in enumerate([61,68,73,82]):
            notes.append({'id':f'l{i}','parentId':f'l{i}','family':'theme_attack','sourceTrack':1,
                          'sourceMidi':pitch,'sourceStartSeconds':i*.5,'sourceEndSeconds':i*.5+.4,'velocity':90})
        notes.append({'id':'b0','parentId':'b0','family':'sub_bass','sourceTrack':2,
                      'sourceMidi':37,'sourceStartSeconds':0,'sourceEndSeconds':1.3,'velocity':70})
        return {'schemaVersion':1,'sourceMode':'midi','sourceMidiSha256':'a'*64,
                'notes':notes,'durationSeconds':2.2,'sections':[],'tempoMap':[]}

    def test_recipe_is_actual_mono_audio_with_end_fades_and_honest_origin(self):
        result=design_timbre(self.recipe(kind='vowel',seconds=1),self.root/'tone')
        data,rate=sf.read(result['sample'])
        self.assertEqual(rate,22050);self.assertEqual(data.ndim,1)
        self.assertGreater(np.sqrt(np.mean(data**2)),.015)
        self.assertLess(np.max(np.abs(data)),.23)
        self.assertLess(np.max(np.abs(data[:12])),.015)
        self.assertLess(np.max(np.abs(data[-12:])),.015)
        self.assertEqual(result['sourceKind'],'original-Minecraft-inspired-synthesis')
        self.assertFalse(result['actualMinecraftRecording'])
        with self.assertRaises(ValueError):design_timbre(self.recipe(),self.root/'tone')

    def test_explicit_sample_is_retuned_without_mutating_original_or_claiming_stock(self):
        rate=22050;t=np.arange(rate//2)/rate
        original=self.root/'explicit.wav';sf.write(original,.2*np.sin(2*np.pi*440*t),rate)
        frozen=original.read_bytes()
        recipe=self.recipe(kind='sustain',rootMidi=72,attackWeight=0,bodyWeight=1,
            bodySample={'path':str(original),'rootMidi':69,'license':'CC0-1.0'})
        result=design_timbre(recipe,self.root/'retuned')
        self.assertEqual(original.read_bytes(),frozen)
        self.assertEqual(result['sources'][0]['declaredRootMidi'],69)
        self.assertFalse(result['externalAttackSampleUsed'])
        self.assertEqual(result['sourceKind'],'explicit-local-sample-hybrid')
        recipe['bodySample'].pop('license')
        with self.assertRaisesRegex(ValueError,'license'):design_timbre(recipe,self.root/'bad')

    def test_calibrated_palette_covers_61_to_82_on_one_slot_and_all_25_rates(self):
        bank=build_palette(self.spec(),self.root/'bank')
        validate_soundpack(bank['soundPack'],bank['profile'])
        plan=plan_noteblocks(self.score(),profile=bank['profile'])
        lead=[n for n in plan['candidates'] if n['family']=='theme_attack']
        self.assertEqual({n['instrument'] for n in lead},{'banjo'})
        self.assertEqual([n['note'] for n in lead],[1,8,13,22])
        self.assertEqual({n['transpose'] for n in lead},{0})
        report=audit_palette(bank['profile'],plan)
        notes=report['slots'][0]['notes'];self.assertEqual(len(notes),25)
        self.assertAlmostEqual(notes[0]['decodedSeconds']/notes[24]['decodedSeconds'],4,delta=.02)
        self.assertTrue(all(abs(n['centsCandidateError'])<15 for n in notes))
        self.assertFalse(report['listeningVerified'])

    def test_same_gain_solos_sum_to_mix_and_variants_do_not_rewrite_notes(self):
        score=self.score();before=deepcopy(score)
        result=compare_timbres(score,self.spec(),self.root/'comparison')
        self.assertEqual(score,before);self.assertTrue(result['noteDecisionsIdentical'])
        self.assertTrue(result['soloGainMatchesMix']);self.assertFalse(result['loudnessMatched'])
        hashes=[]
        for variant,row in result['variants'].items():
            mix,rate=sf.read(row['mix']);solo_sum=np.zeros_like(mix)
            for path in row['solos'].values():solo_sum+=sf.read(path)[0]
            np.testing.assert_allclose(solo_sum,mix,atol=7e-7)
            self.assertEqual(rate,22050);self.assertLess(np.max(np.abs(mix)),.9)
            hashes.append(row['mixSha256'])
        self.assertEqual(len(set(hashes)),3)
        self.assertEqual(result['variants']['native']['referenceKind'],'original-Minecraft-inspired-synthesis')

    def test_audit_flags_underfilled_long_note_instead_of_claiming_noteoff(self):
        bank=build_palette(self.spec(),self.root/'bank')
        score=self.score();score['notes'][0]['sourceEndSeconds']=2
        plan=plan_noteblocks(score,profile=bank['profile'])
        audit=audit_palette(bank['profile'],plan)
        self.assertTrue(any(r['kind']=='sustain-underfill-candidate' and r['event']=='l0' for r in audit['risks']))

    def test_unknown_recipe_fields_and_wrong_root_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'Unknown timbre'):design_timbre(self.recipe(typo=.3),self.root/'typo')
        spec=self.spec();spec['slots']['lead']['recipe']['rootMidi']=66
        with self.assertRaisesRegex(ValueError,'disagree'):build_palette(spec,self.root/'bad')
        self.assertFalse((self.root/'bad').exists())

    def test_original_study_keeps_same_samples_for_natural_and_retrigger_comparison(self):
        result=create_timbre_study(self.root/'study')
        report=json.loads(Path(result['sustainComparison']).read_text(encoding='utf-8'))
        natural=report['variants']['natural'];repeat=report['variants']['retrigger']
        self.assertEqual(natural['onsets'],repeat['onsets'])
        self.assertEqual(natural['retriggers'],0);self.assertGreater(repeat['retriggers'],0)
        a=Path(natural['profile']).parent/'samples/voice.ogg'
        b=Path(repeat['profile']).parent/'samples/voice.ogg'
        self.assertEqual(a.read_bytes(),b.read_bytes())
        self.assertNotEqual(sf.read(natural['voice_solo'])[0].tobytes(),sf.read(repeat['voice_solo'])[0].tobytes())


if __name__=='__main__':unittest.main()
