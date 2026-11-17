import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from redstone_music.stage_tools import evaluate_blueprint, preview_stage, compile_show, effect_points, validate_show
from redstone_music.game_tools import inspect_game, inspect_mod, import_game, plan_photon_comparison
from redstone_music import visuals


class StageToolsTests(unittest.TestCase):
    def test_fill_and_frame_are_deterministic_and_preserve_states(self):
        source={'operations':[{'op':'fill','min':[0,0,0],'max':[1,0,1],'block':'minecraft:cut_copper_slab[type=top]'},
                              {'op':'frame','min':[0,1,0],'max':[2,3,2],'block':'minecraft:glass'}]}
        a,report=evaluate_blueprint(source)
        b,_=evaluate_blueprint(source)
        self.assertEqual(a,b)
        self.assertEqual(report['blockCount'],24)
        self.assertTrue(any('type=top' in block['block'] for block in a))

    def test_note_headroom_and_base_are_protected_including_air_deletions(self):
        for y in (-1,0,1):
            _,report=evaluate_blueprint({'blocks':[{'pos':[4,y,6],'block':'minecraft:air'}]},
                                        {'noteBlocks':[[4,0,6]]})
            self.assertFalse(report['protected'])
            self.assertEqual(report['conflicts'][0]['reason'],'note-base-and-headroom')

    def test_nearby_circuit_and_camera_have_clearance(self):
        source={'blocks':[{'pos':[1,2,0],'block':'minecraft:stone'}]}
        self.assertFalse(evaluate_blueprint(source,{'circuitBlocks':[[0,0,0]]})[1]['protected'])
        self.assertFalse(evaluate_blueprint(source,{'cameraPath':[[2,2,0]]})[1]['protected'])
        self.assertTrue(evaluate_blueprint(source,{'circuitBlocks':[[20,20,20]]})[1]['protected'])

    def test_overlarge_and_executable_operations_rejected(self):
        for source in ({'operations':[{'op':'fill','min':[0,0,0],'max':[100,100,100]}]},
                       {'operations':[{'op':'python','code':'print(1)'}]},
                       {'blocks':[{'pos':[0,0,0],'block':'minecraft:stone[axis=bad]'}]}):
            with self.assertRaises(ValueError):evaluate_blueprint(source)

    def test_cpu_preview_contains_four_views_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'preview'
            report=preview_stage({'blocks':[{'pos':[0,0,0],'block':'minecraft:glass'}]},out)
            self.assertTrue(report['accepted'])
            from PIL import Image
            with Image.open(out/'contact_sheet.png') as im:self.assertEqual(im.size,(1280,920))
            with self.assertRaises(ValueError):preview_stage({'blocks':[{'pos':[0,0,0],'block':'minecraft:stone'}]},out)

    def test_retriggers_not_new_effects_and_long_notes_get_continuous_geometry(self):
        source={'durationSeconds':4,'notes':[
            {'id':'a','family':'voice','sourceStartSeconds':0,'sourceEndSeconds':2,'kind':'onset'},
            {'id':'a_r1','family':'voice','sourceStartSeconds':0,'sourceEndSeconds':2,'kind':'retrigger','gt':5},
            {'id':'b','family':'theme_attack','sourceStartSeconds':2,'sourceEndSeconds':2.1,'kind':'onset'}]}
        with tempfile.TemporaryDirectory() as tmp:
            result=compile_show(source,Path(tmp)/'show')
            show=json.loads(Path(result['showScore']).read_text())
            self.assertEqual(len(show['effects']),2)
            self.assertEqual(show['effects'][0]['kind'],'helix')
            self.assertEqual(show['effects'][1]['kind'],'node')
            self.assertFalse(result['clientVerified'])
            self.assertFalse(effect_points(show['effects'][0],40))

    def test_invalid_show_bounds_and_curves_rejected(self):
        base={'schemaVersion':1,'clock':'musicGT','lengthGT':40,'namespace':'song','effects':[
            {'id':'a','kind':'bezier','beginGT':0,'endGT':41,'position':[0,0,0],'color':'AABBCC'}]}
        with self.assertRaises(ValueError):validate_show(base)
        base['effects'][0]['endGT']=30
        with self.assertRaises(ValueError):validate_show(base)
        base['effects'][0]['kind']='node';base['effects'][0]['points']=100000
        with self.assertRaises(ValueError):validate_show(base)

    def test_parametric_curve_endpoints(self):
        e={'kind':'bezier','beginGT':0,'endGT':100,'position':[0,0,0],'points':10,
           'controlPoints':[[0,0,0],[0,1,0],[1,1,0],[1,0,0]]}
        self.assertEqual(effect_points(e,0)[0],(0,0,0))
        p=effect_points(e,50)[-1]
        self.assertAlmostEqual(p[0],.5)
        self.assertAlmostEqual(p[1],.75)

    def test_game_import_reads_only_metadata_and_copies_selected_base_mod(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'minecraft';root.mkdir();(root/'mods').mkdir()
            (root/'assets').mkdir();(root/'libraries').mkdir();(root/'versions/1.21.1').mkdir(parents=True)
            (root/'versions/1.21.1/1.21.1.json').write_text('{"id":"1.21.1"}')
            (root/'launcher_accounts.json').write_text('THIS IS NOT JSON AND MUST NEVER BE READ')
            for name,modid in [('api','fabric-api'),('other','unrelated')]:
                with zipfile.ZipFile(root/'mods'/f'{name}.jar','w') as z:
                    z.writestr('fabric.mod.json',json.dumps({'id':modid,'version':'1'}))
            report=inspect_game(root,java=Path(tmp)/'missing')
            self.assertFalse(report['credentialsRead'])
            self.assertEqual(len(report['versions']),1)
            dest=Path(tmp)/'runtime';result=import_game(root,dest,java=Path(tmp)/'missing')
            self.assertEqual(result['importedMods'],1)
            self.assertEqual([p.name for p in (dest/'game/mods').iterdir()],['api.jar'])
            with self.assertRaises(ValueError):import_game(root,dest)

    def test_oversized_mod_metadata_does_not_decode(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.jar'
            with zipfile.ZipFile(p,'w') as z:z.writestr('fabric.mod.json','x'*(1024*1024+1))
            self.assertEqual(inspect_mod(p)['loader'],'invalid')

    def test_excerpt_continuous_effect_end_uses_local_clock(self):
        source={'info':{'excerpt':{'musicGT':100,'startGT':200}},'notes':[
            {'id':'a','family':'voice','q':10,'sourceEndSeconds':11.5,'kind':'onset'}]}
        with tempfile.TemporaryDirectory() as tmp:
            result=compile_show(source,Path(tmp)/'show')
            show=json.loads(Path(result['showScore']).read_text())
            self.assertEqual(show['effects'][0]['endGT'],30)

    def test_explicit_client_jar_embeds_validated_show_and_preserves_captions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);machine=root/'machine';machine.mkdir();music=root/'music';music.mkdir();out=root/'out';out.mkdir()
            (machine/'expected_events.json').write_text(json.dumps({'info':{'namespace':'actual',
                'excerpt':{'musicGT':200},'fxSample':{'key':7}},'notes':[]}))
            (music/'score.json').write_text('{"sections":[]}')
            score={'schemaVersion':1,'clock':'musicGT','lengthGT':200,'namespace':'draft','effects':[],
                   'captions':[{'text':'Designed caption','begin':20,'end':40}]}
            (root/'show.json').write_text(json.dumps(score))
            jar=root/'client-base.jar'
            with zipfile.ZipFile(jar,'w') as z:
                z.writestr('dev/redstone/show/MusicShowClient.class',b'packaging fixture')
                z.writestr('assets/redstone_music/show_score.json','old')
            ctx={'project':str(root),'workspace':str(root),'out':str(out),'deps':{'machine':str(machine),'music':str(music)},
                 'config':{'slug':'fixture','runtime':{'clientJar':'client-base.jar'},'inputs':{'showScore':'show.json'}}}
            report=visuals.run(ctx)
            self.assertTrue(report['clientJarBuilt']);self.assertFalse(report['clientVerified'])
            with zipfile.ZipFile(out/'client.jar') as z:
                embedded=json.loads(z.read('assets/redstone_music/show_score.json'))
                self.assertEqual(embedded['namespace'],'actual');self.assertEqual(embedded['sampleKey'],7)
                self.assertEqual(embedded['captions'][0]['text'],'Designed caption')
                self.assertEqual(z.namelist().count('assets/redstone_music/show_score.json'),1)
            self.assertEqual(visuals.fingerprint_inputs(ctx),[jar.resolve()])
            self.assertIsNone(visuals.runtime_file({'config':{},'workspace':str(root)}))

    def test_photon_plan_inspects_explicit_jar_and_keeps_runtime_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);jar=root/'photon.jar';score=root/'show.json'
            with zipfile.ZipFile(jar,'w') as z:
                z.writestr('fabric.mod.json',json.dumps({'id':'photon','version':'1.6','depends':{'ldlib2':'*'},'license':'fixture'}))
                z.writestr('com/lowdragmc/photon/client/ClientCommands.class',b'photon_editor photon_client clear_particles clear_client_fx_cache')
            effects=[{'id':str(i),'kind':'node','beginGT':0,'endGT':10,'position':[0,0,0],'color':'FFFFFF','points':96} for i in range(13)]
            score.write_text(json.dumps({'schemaVersion':1,'clock':'musicGT','lengthGT':20,'namespace':'test-phrase','effects':effects}))
            result=plan_photon_comparison(score,root/'plan',jar)
            self.assertEqual(result['photon']['sha256'],hashlib.sha256(jar.read_bytes()).hexdigest())
            self.assertEqual(result['requestedPeakPointsPerTick'],1248)
            self.assertTrue(result['referenceBudgetClips'])
            self.assertFalse(result['photonRuntimeIntegrated']);self.assertFalse(result['clientLaunched'])
            self.assertFalse(list((root/'plan').glob('*.jar')))
            self.assertTrue(all(c['status']=='pending' for c in result['checks']))
            with self.assertRaises(ValueError):plan_photon_comparison(score,root/'plan',jar)


if __name__=='__main__':unittest.main()
