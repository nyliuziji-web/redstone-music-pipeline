import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from redstone_music.demo import demo_midi_bytes
from redstone_music.game_arrangement import arrange, create_game_arrangement
from redstone_music.machine import compile_blocks
from redstone_music.midi import parse_midi
from redstone_music.music_tools import _score
from redstone_music.core import atomic_json
from redstone_music.track_design import design_track


class GameArrangementTests(unittest.TestCase):
    def test_midi_is_bound_to_an_authored_performance_with_audit_trail(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            master = root/'master.mid'
            raw = demo_midi_bytes()
            master.write_bytes(raw)
            score = _score(master)
            bass = [n for n in score['notes'] if n['family']=='sub_bass']
            rules = {'schemaVersion':1,'sourceMidiSha256':score['sourceMidiSha256'],'edits':[
                {'noteId':bass[0]['id'],'omit':True,'reason':'Clear the first phrase.'},
                {'noteId':bass[1]['id'],'midi':45,'shiftGT':1,'reason':'Release the melody onset.'},
            ]}
            atomic_json(root/'decisions.json',rules)
            report = create_game_arrangement(master,root/'preview',decisions_path=root/'decisions.json')
            self.assertEqual(master.read_bytes(),raw)
            self.assertEqual(report['omissions'],1)
            rows = parse_midi(Path(report['midi']).read_bytes())['notes']
            observed = [n for n in rows if n['family']=='sub_bass']
            self.assertEqual(len(observed),1)
            changed = next(n for n in report['notes'] if n['noteId']==bass[1]['id'])
            self.assertEqual(observed[0]['sourceMidi'],changed['mappedMidi'])
            self.assertAlmostEqual(observed[0]['sourceStartSeconds'],changed['triggerGT']/20)
            self.assertEqual(changed['onsetDeltaMs'],50)

    def test_protected_role_and_stale_score_stop_before_arranging(self):
        raw = demo_midi_bytes()
        score = parse_midi(raw)
        score['sourceMidiSha256'] = hashlib.sha256(raw).hexdigest()
        lead = next(n for n in score['notes'] if n['family']=='theme_attack')
        edit = {'noteId':lead['id'],'omit':True,'reason':'Check protection.'}
        data = {'schemaVersion':1,'sourceMidiSha256':score['sourceMidiSha256'],'edits':[edit]}
        with self.assertRaisesRegex(ValueError,'protected'):
            arrange(score,decisions=data)
        data['sourceMidiSha256'] = '0'*64
        with self.assertRaisesRegex(ValueError,'exact MIDI'):
            arrange(score,decisions=data)


def event(tick, index, role='theme_attack'):
    return {'id':f'n{index}','parentId':f'n{index}','family':role,'gt':tick,
            'sourceMidi':60+index%12,'sourceStartSeconds':tick/20,'sourceEndSeconds':tick/20+.1,
            'kind':'onset','note':index%25,'instrument':'harp','baseBlock':'minecraft:dirt'}


class TrackBankTests(unittest.TestCase):
    def test_automatic_track_reacts_to_score_activity(self):
        events = {'musicGT':280,'sections':[{'beginGT':140,'name':'Expansion'}],'candidates':[
            event(0,0,'sub_bass'), event(60,1,'sub_bass'),
            *[event(140,i+2) for i in range(7)], event(180,9,'chords'),
        ]}
        plan, _ = design_track(events,{'theme_attack','chords','sub_bass'})
        first, second = plan['sections']
        self.assertEqual(first['focus'],'sub_bass')
        self.assertEqual(first['turn'],-1)
        self.assertEqual(second['beginGT'],140)
        self.assertEqual(second['focus'],'theme_attack')
        self.assertEqual((second['spread'],second['terrace'],second['turn']),(3,1,1))

    def test_dense_odd_boundary_preserves_global_clock_and_electrical_isolation(self):
        events = {'musicGT':188,'durationSeconds':9.4,'candidates':[
            event(1,0), event(82,1),
            *[event(83,2+i) for i in range(7)], event(84,9), event(179,10),
        ]}
        design = {'schemaVersion':1,'sections':[
            {'beginGT':0,'endGT':83,'style':'moon','anchors':{'theme_attack':[21,117]}},
            {'beginGT':83,'endGT':188,'style':'tide','anchors':{'theme_attack':[52,119]}},
        ]}
        info, blocks, notes, heads, _, _ = compile_blocks(events,'Test track','rmp_test','rmp_test',
                                                         track_design=design)
        self.assertEqual(len(notes),len(events['candidates']))
        physical = {n['id']:n for n in notes}
        self.assertEqual({n['launchGT'] for n in heads},{0,83})
        self.assertEqual(len(info['trackPlan']['sections'][1]['lanes']),4)
        self.assertGreater(info['decorativeBlocks'],0)
        for original in events['candidates']:
            placed = physical[original['id']]
            bank = placed['clockLane']['launchGT']
            self.assertEqual(placed['z'],80+original['gt'])
            self.assertEqual(placed['clockLane']['parity'],(original['gt']-bank)%2)
        self.assertEqual(len({(b['x'],b['y'],b['z']) for b in blocks}),len(blocks))
        self.assertEqual(info['trackPlan']['sections'][1]['lanes'][0]['x'],52)
        self.assertEqual(info['trackPlan']['sections'][1]['lanes'][0]['y'],119)

    def test_colliding_author_anchors_fail_without_relocating_them_silently(self):
        events = {'musicGT':160,'durationSeconds':8.,'candidates':[event(79,0),event(80,1)]}
        design = {'schemaVersion':1,'sections':[
            {'beginGT':0,'endGT':80,'anchors':{'theme_attack':[18,120]}},
            {'beginGT':80,'endGT':160,'anchors':{'theme_attack':[18,120]}},
        ]}
        with self.assertRaisesRegex(ValueError,'no isolated lane'):
            compile_blocks(events,'Bad','rmp_test','rmp_test',track_design=copy.deepcopy(design))
