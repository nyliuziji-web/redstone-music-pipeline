import json
from pathlib import Path
import tempfile
import unittest

import nbtlib as nbt

from redstone_music.architecture import assemble, read_structure


class ArchitectureTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)

    def structure(self, data_version=3955):
        palette = nbt.List[nbt.Compound]([
            {'Name': nbt.String('minecraft:dark_oak_stairs'),
             'Properties': nbt.Compound({'facing': nbt.String('north'), 'half': nbt.String('top')})},
            {'Name': nbt.String('minecraft:stripped_spruce_log'),
             'Properties': nbt.Compound({'axis': nbt.String('x')})},
            {'Name': nbt.String('minecraft:air')},
        ])
        blocks = nbt.List[nbt.Compound]([
            {'pos': nbt.List[nbt.Int]([i, 0, 0]), 'state': nbt.Int(i)} for i in range(3)
        ])
        path = self.root / 'module.nbt'
        nbt.File({'size': nbt.List[nbt.Int]([3, 1, 1]), 'palette': palette,
                  'blocks': blocks, 'DataVersion': nbt.Int(data_version)}).save(path, gzipped=True)
        return path

    def recipe(self, placements):
        path = self.root / 'recipe.json'
        path.write_text(json.dumps({'schemaVersion': 1, 'gameVersion': '1.21.1',
                                    'modules': {'roof': 'module.nbt'}, 'placements': placements}),
                        encoding='utf8')
        return path

    def test_sparse_placement_rotates_states_with_geometry(self):
        self.structure()
        report = assemble(self.recipe([{'module': 'roof', 'origin': [9, 104, 23], 'quarterTurns': 1}]),
                          self.root / 'assembly')
        result = json.loads(Path(report['stage']).read_text(encoding='utf8'))
        self.assertEqual(result['blocks'], [
            {'pos': [9, 104, 23], 'block': 'minecraft:dark_oak_stairs[facing=east,half=top]'},
            {'pos': [9, 104, 24], 'block': 'minecraft:stripped_spruce_log[axis=z]'},
        ])

    def test_rejects_overlaps_before_writing_stage(self):
        self.structure()
        item = {'module': 'roof', 'origin': [9, 104, 23]}
        with self.assertRaisesRegex(ValueError, 'overlaps'):
            assemble(self.recipe([item, item]), self.root / 'assembly')
        self.assertFalse((self.root / 'assembly').exists())

    def test_rejects_other_data_versions(self):
        with self.assertRaisesRegex(ValueError, 'DataVersion 3955'):
            read_structure(self.structure(data_version=4189))
