"""Offline building workbench. Only reviewed stage blueprints reach the world writer."""

import hashlib
import json
import math
import os
from pathlib import Path
import subprocess

import nbtlib

from .stage_tools import MAX_BLOCKS, _new_out, _read, _state, _write, _xyz, evaluate_blueprint

VERSION = '1.21.1'
DATA_VERSION = 3955
DIRECTIONS = ('north', 'east', 'south', 'west')


def _builder(python, arguments):
    interpreter = Path(python).resolve(strict=True)
    try:
        return subprocess.run([str(interpreter), '-X', 'utf8', '-m', 'mcbuilder.cli', *arguments],
                              capture_output=True, encoding='utf8', errors='replace', timeout=300,
                              env={**os.environ, 'PYTHONHASHSEED': '0'})
    except subprocess.TimeoutExpired as error:
        raise ValueError('mcbuilder exceeded the five-minute tool limit.') from error


def _registry(cache):
    registry = _read(cache / VERSION / 'minecraft-data.json')
    if registry.get('version') != VERSION or registry.get('layout') != f'pc/{VERSION}':
        raise ValueError('Building requires the exact Java 1.21.1 block registry.')


def fetch_assets(python, cache):
    """Explicitly populate the private render cache using mcbuilder."""
    cache = Path(cache).resolve()
    result = _builder(python, ['assets', 'fetch', '--version', VERSION, '--cache-dir', str(cache)])
    if result.returncode:
        raise ValueError(f'mcbuilder asset fetch failed: {(result.stderr or result.stdout).strip()}')
    _registry(cache)
    return {'cache': str(cache), 'gameVersion': VERSION}


def build(source, python, cache, out, views):
    """Run the separately installed mcbuilder with an explicit 1.21.1 cache."""
    source = Path(source).resolve(strict=True)
    cache = Path(cache).resolve(strict=True)
    _registry(cache)
    destination = _new_out(out)
    config = destination / 'mcbuild.toml'
    config.write_text(f'mc_version = "{VERSION}"\nassets_dir = {json.dumps(cache.as_posix(), ensure_ascii=False)}\n',
                      encoding='utf8')
    args = ['run', str(source),
            '--config', str(config), '--out', str(destination), '--preview', '--views', views]
    result = _builder(python, args)
    (destination / 'builder.log').write_text(result.stdout + result.stderr, encoding='utf8')
    if result.returncode:
        raise ValueError(f'mcbuilder failed. See {destination / "builder.log"}')
    structures = list((destination / 'run-001').glob('*.nbt'))
    if len(structures) != 1:
        raise ValueError(f'Expected one vanilla structure. See {destination / "builder.log"}')
    structure = structures[0]
    blocks = read_structure(structure)
    return {'structure': str(structure), 'blocks': len(blocks), 'dataVersion': DATA_VERSION,
            'previews': [str(p) for p in sorted(structure.parent.glob('previews_faithful/*.png'))],
            'builderReport': str(structure.parent / 'report.json')}


def read_structure(source):
    """Read sparse vanilla NBT and retain placement-relevant block states."""
    if Path(source).stat().st_size > 8 * 1024 * 1024:
        raise ValueError('Structure file exceeds 8 MiB.')
    try:
        data = nbtlib.load(source)
    except (TypeError, EOFError) as error:
        raise ValueError(f'Invalid vanilla structure file: {source}') from error
    if data.get('DataVersion') != DATA_VERSION:
        raise ValueError(f'{source}: export a Java 1.21.1 vanilla structure (DataVersion 3955).')
    if data.get('entities') or 'palettes' in data:
        raise ValueError(f'{source}: entity and alternate palette imports require separate authoring.')
    size = _xyz(tuple(int(n) for n in data['size']), 'Structure size')
    if not all(1 <= n <= 256 for n in size) or math.prod(size) > 2_000_000:
        raise ValueError(f'{source}: unsupported structure dimensions.')
    palette = data['palette']
    entries = data['blocks']
    if len(entries) > MAX_BLOCKS:
        raise ValueError(f'{source}: structure exceeds the stage block budget.')
    blocks = {}
    seen = set()
    for entry in entries:
        if 'nbt' in entry:
            raise ValueError(f'{source}: block-entity data requires separate authoring.')
        pos = _xyz(tuple(int(n) for n in entry['pos']), 'Local position')
        index = int(entry['state'])
        if pos in seen or not all(0 <= a < n for a, n in zip(pos, size)) or not 0 <= index < len(palette):
            raise ValueError(f'{source}: invalid cell or palette index at {pos}.')
        seen.add(pos)
        tag = palette[index]
        name = str(tag['Name'])
        if name in {'minecraft:air', 'minecraft:cave_air', 'minecraft:void_air', 'minecraft:structure_void'}:
            continue
        if not name.startswith('minecraft:'):
            raise ValueError(f'{source}: non-vanilla block {name}.')
        blocks[pos] = _state(block_state(name, tag.get('Properties', {})))
    if not blocks:
        raise ValueError(f'{source}: structure contains no placeable blocks.')
    return blocks


def block_state(name, properties):
    return name + ('[' + ','.join(f'{k}={v}' for k, v in sorted(properties.items())) + ']'
                   if properties else '')


def rotate(pos, state, turns):
    """Rotate around the module's local zero, clockwise from above."""
    x, y, z = pos
    for _ in range(turns):
        x, z = -z, x
    name, _, raw = state.partition('[')
    props = dict(part.split('=') for part in raw[:-1].split(',')) if raw else {}

    def direction(key):
        return DIRECTIONS[(DIRECTIONS.index(key) + turns) % 4] if key in DIRECTIONS else key

    props = {direction(k): v for k, v in props.items()}
    if 'facing' in props:
        props['facing'] = direction(props['facing'])
    if turns % 2 and props.get('axis') in ('x', 'z'):
        props['axis'] = 'z' if props['axis'] == 'x' else 'x'
    if 'rotation' in props:
        props['rotation'] = str((int(props['rotation']) + 4 * turns) % 16)
    if turns and (name.endswith('rail') or 'orientation' in props or 'vertical_direction' in props):
        raise ValueError(f'Rotating {name} requires a separately oriented structure.')
    return (x, y, z), block_state(name, props)


def assemble(recipe, out, machine=None):
    recipe = Path(recipe).resolve(strict=True)
    spec = _read(recipe)
    if spec.get('schemaVersion') != 1 or spec.get('gameVersion') != VERSION:
        raise ValueError('Expected architecture schemaVersion 1 and gameVersion 1.21.1.')
    modules = spec['modules']
    placements = spec['placements']
    if not isinstance(modules, dict) or not isinstance(placements, list) or not 1 <= len(placements) <= 256:
        raise ValueError('Expected named modules and 1–256 placements.')
    base = spec.get('baseStage')
    blocks = {}
    if base:
        existing, report = evaluate_blueprint(recipe.parent / base)
        if not report['protected'] or any(b['block'] == 'minecraft:air' for b in existing):
            raise ValueError('Base stage must be conflict-free and additive.')
        blocks = {tuple(row['pos']): row['block'] for row in existing}
    counts = []
    prototypes = {}
    for row in placements:
        key = row['module']
        if key not in prototypes:
            source = recipe.parent / modules[key]
            prototypes[key] = (read_structure(source), hashlib.sha256(source.read_bytes()).hexdigest())
        cells, digest = prototypes[key]
        origin = _xyz(row['origin'], 'Placement origin')
        turns = row.get('quarterTurns', 0)
        if type(turns) is not int or not 0 <= turns <= 3:
            raise ValueError('quarterTurns must be an integer from 0 to 3.')
        for cell, state in cells.items():
            rotated, state = rotate(cell, state, turns)
            pos = tuple(a + b for a, b in zip(origin, rotated))
            if pos in blocks:
                raise ValueError(f'Architecture placement {key} overlaps an existing stage cell at {pos}.')
            blocks[pos] = state
        if len(blocks) > MAX_BLOCKS:
            raise ValueError('Merged architecture exceeds the stage block budget.')
        counts.append({'module': key, 'origin': origin, 'quarterTurns': turns,
                       'blockCount': len(cells), 'structureSha256': digest})
    blueprint = {'schemaVersion': 1, 'title': spec.get('title', 'Architecture'),
                 'blocks': [{'pos': list(pos), 'block': state} for pos, state in sorted(blocks.items())]}
    _, stage = evaluate_blueprint(blueprint)
    if machine:
        from .machine import merge_stage_module
        machine = Path(machine)
        world = _read(machine / 'placed_blocks.json')
        # Supply the pre-architecture machine, including no duplicate copies of the base stage.
        manifest = _read(machine / 'build_manifest.json')
        notes = _read(machine / 'expected_events.json')['notes']
        merge_stage_module(manifest, world['blocks'], notes, blueprint)
    output = _new_out(out)
    _write(output / 'stage.json', blueprint)
    report = {'blockCount': stage['blockCount'], 'bounds': stage['bounds'], 'placements': counts,
              'machineClearanceChecked': bool(machine), 'actualGameChecked': False,
              'stage': str(output / 'stage.json')}
    _write(output / 'architecture-report.json', report)
    return report
