"""Cross-module contracts that matter when a new agent takes over a project."""
import json
from pathlib import Path
import tempfile
import unittest

from redstone_music import core, kit
from redstone_music.demo import demo_midi_bytes
from redstone_music.machine import compile_blocks, merge_stage_module


class KitTests(unittest.TestCase):
    def setUp(self):
        root=core.REPO_ROOT/'.runtime'
        root.mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(prefix='kit_',dir=root)
        self.base=Path(self.tmp.name)
        midi=self.base/'source.mid';midi.write_bytes(demo_midi_bytes())
        self.project=self.base/'song'
        core.initialize(self.project,'Original song',midi)

    def tearDown(self):
        self.tmp.cleanup()

    def test_bundle_exports_only_public_material_and_resolves_links(self):
        self.assertTrue(kit.bundle_check()['valid'])
        exported=kit.export_bundle(self.base/'export')
        root=Path(exported['directory'])
        self.assertTrue(kit.bundle_check(root)['valid'])
        self.assertTrue((root/'client/build.gradle').exists())
        self.assertFalse((root/'projects').exists())
        self.assertFalse((root/'.git').exists())
        manifest=core.read_json(root/'bundle_manifest.json')
        self.assertEqual(manifest['files']['START_HERE.md']['sha256'],core.hash_file(root/'START_HERE.md'))

    def test_review_binds_real_bytes_and_expires_after_revision(self):
        media=self.project/'sources/sample.wav';media.write_bytes(b'candidate audio bytes')
        review=self.project/'review-input.json'
        document={'schemaVersion':1,'stage':'music','scope':'sample','verdict':'approved',
                  'reviewer':{'kind':'user','name':'user'},'method':'actual_listening',
                  'inputs':[{'path':'sources/sample.wav','sha256':core.hash_file(media)}],
                  'summary':'User preferred this candidate','userFeedback':'This version works.'}
        core.atomic_json(review,document)
        kit.record_review(self.project,review)
        self.assertEqual(kit.handoff(self.project)['currentUserArtisticReviews'],1)
        # Immutable old media survives a new candidate; that does not approve the new input.
        config=core.load_config(self.project)
        changed=dict(config);changed['title']='A revised candidate'
        core.atomic_json(self.project/'project.json',changed)
        self.assertEqual(kit.handoff(self.project)['currentUserArtisticReviews'],0)
        core.atomic_json(self.project/'project.json',config)
        self.assertEqual(kit.handoff(self.project)['currentUserArtisticReviews'],1)
        media.write_bytes(b'revised candidate')
        state=kit.handoff(self.project)
        self.assertEqual(state['currentUserArtisticReviews'],0)
        self.assertFalse(state['reviews'][0]['current'])
        self.assertFalse(state['artisticPassInferred'])
        with self.assertRaises(ValueError):kit.record_review(self.project,review)

    def test_decisions_and_brief_survive_handoff_without_granting_pass(self):
        kit.set_brief(self.project,'Quiet night; preserve silence between phrases.')
        kit.record_decision(self.project,'Reduce layers','Leave the lead phrase audible')
        handoff=kit.handoff(self.project)
        self.assertIn('Reduce layers',handoff['decisions'][0]['summary'])
        self.assertFalse(handoff['artisticPassInferred'])
        self.assertIn('Quiet night',(self.project/'brief.md').read_text(encoding='utf-8'))

    def test_typed_show_task_imports_real_result(self):
        created=core.create_task(self.project,'visuals','Create a bounded show score',kind='show_score')
        task_id=created['id']
        folder=self.project/'tasks'/task_id
        core.claim_task(self.project,task_id,'test-specialist')
        score={'schemaVersion':1,'clock':'musicGT','namespace':'rm_song','lengthGT':160,'effects':[]}
        core.atomic_json(folder/'output/showScore.json',score)
        core.atomic_json(folder/'output/review.json',{'summary':'Original proposal','evidence':[],'limitations':['No client run']})
        result=folder/'result.json'
        core.atomic_json(result,{'outputs':{'showScore':str(folder/'output/showScore.json'),
                                          'review':str(folder/'output/review.json')}})
        core.complete_task(self.project,task_id,result)
        self.assertTrue(core.load_config(self.project)['inputs']['showScore'])

    def test_nested_samples_make_inflight_task_stale(self):
        sample=self.project/'sources/tone.ogg';sample.write_bytes(b'original')
        profile=self.project/'sources/profile.json'
        core.atomic_json(profile,{'schemaVersion':1,'id':'test','slots':{'a':{'instrument':'harp',
            'baseBlock':'minecraft:dirt','rootMidi':66,'sample':'tone.ogg'}},'roles':{'voice':'a'}})
        config=core.load_config(self.project)
        config['inputs']['soundProfile']='sources/profile.json'
        before=core._request_signature(self.project,config)
        sample.write_bytes(b'new sample bytes')
        self.assertNotEqual(before,core._request_signature(self.project,config))

    def test_invalid_profile_still_creates_a_repair_task(self):
        bad=self.project/'sources/bad-profile.json'
        core.atomic_json(bad,{'schemaVersion':1,'slots':{}})
        config=core.load_config(self.project);config['inputs']['soundProfile']='sources/bad-profile.json'
        core.atomic_json(self.project/'project.json',config)
        with self.assertRaises(core.PipelineError):core.run_pipeline(self.project,until='sound')
        state=core.read_json(self.project/'state.json')
        task=core.read_json(self.project/'tasks'/state['task']/'task.json')
        self.assertEqual(task['role'],'sound')
        self.assertTrue(Path(task['skill']).is_file())

    def test_sound_profile_rejects_physically_wrong_instrument_base(self):
        from redstone_music.music_tools import validate_sound_profile
        profile={'schemaVersion':1,'id':'test','roles':{'voice':'voice'},'slots':{'voice':
            {'instrument':'harp','baseBlock':'minecraft:clay','rootMidi':66}}}
        with self.assertRaisesRegex(ValueError,'instrument/baseBlock mismatch'):
            validate_sound_profile(profile,require_samples=False)

    def test_legal_hyphen_namespace_works_in_visual_contract(self):
        from redstone_music.stage_tools import validate_show
        from redstone_music.contracts import validate_contract
        document={'schemaVersion':1,'clock':'musicGT','namespace':'rm_cold-start-night','lengthGT':20,'effects':[]}
        self.assertEqual(validate_show(document)['namespace'],'rm_cold-start-night')
        validate_contract(document,'show-score')


class LayoutAndStageTests(unittest.TestCase):
    def events(self):
        return {'candidates':[{'id':'n1','parentId':'n1','family':'voice','gt':0,'q':0,
                 'note':12,'baseBlock':'minecraft:dirt','instrument':'harp','kind':'onset'}],
                'musicGT':20,'durationSeconds':1}

    def test_custom_layout_changes_physical_and_camera_contract(self):
        options={'families':[{'id':'voice','x':8,'y':-8}],
                 'camera':{'x':38.5,'eyeY':113.5,'teleportDuration':2}}
        info,blocks,notes,*_=compile_blocks(self.events(),'Test','rm_test','rm_test',False,options)
        self.assertEqual(notes[0]['clockLane']['x'],43)
        self.assertEqual(info['camera']['targetLeadBlocks'],1)
        self.assertEqual(info['camera']['x'],38.5)
        with self.assertRaises(ValueError):
            compile_blocks(self.events(),'Test','rm_test','rm_test',False,{'camera':{'speed':2}})

    def test_passive_module_merges_but_circuit_and_camera_remain_protected(self):
        info,blocks,notes,*_=compile_blocks(self.events(),'Test','rm_test','rm_test',False)
        module={'schemaVersion':1,'blocks':[{'pos':[2,90,40],'block':'minecraft:stone_bricks'}]}
        merged,report=merge_stage_module(info,blocks,notes,module)
        self.assertEqual(len(merged),len(blocks)+1)
        self.assertTrue(info['stageModule']['clearanceChecked'])
        self.assertFalse(info['stageModule']['physicsVerified'])
        note=notes[0]
        for pos in ([note['x'],note['y']+1,note['z']],[37,112,85]):
            with self.assertRaises(ValueError):
                merge_stage_module(info,blocks,notes,{'blocks':[{'pos':pos,'block':'minecraft:glass'}]})
        with self.assertRaises(ValueError):
            merge_stage_module(info,blocks,notes,{'blocks':[{'pos':[1,90,1],'block':'minecraft:redstone_block'}]})


if __name__=='__main__':unittest.main()
