"""Add low lateral banks to a score-led stage blueprint for a short excerpt."""

import argparse
import json
import math
from pathlib import Path


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def banks(machine, existing=None):
    info = read_json(machine / 'build_manifest.json')
    length = info['excerpt']['musicGT']
    if not 80 <= length <= 432:
        raise ValueError('This example expects a short excerpt of 4–21.6 seconds.')
    center = round(info['camera']['x'])
    if not 31 <= center <= 46:
        raise ValueError('This example expects a central camera within the usual 80-block corridor.')
    data = read_json(existing) if existing else {}
    if not isinstance(data, dict) or data.keys() - {'schemaVersion', 'title', 'blocks'}:
        raise ValueError('Supply an existing stage expressed as blocks, or omit --existing.')
    old = {tuple(row['pos']): row['block'] for row in data.get('blocks', [])}
    placed = read_json(machine / 'placed_blocks.json')['blocks']
    occupied = {(row['x'], row['y'], row['z']) for row in placed}
    new = {}
    for side in (-1, 1):
        for q in range(1, length + 2):
            z = 75 + q
            taper = min(1, q / 28, (length + 2 - q) / 29)
            swing = round(3 * math.sin(q * .043 + side) + 2 * math.sin(q * .087))
            shore = round(16 + swing + 3 * (1 - taper))
            outer = min(30, round(shore + 7 + 5 * taper))
            for step in range(shore, outer + 1):
                x = center + side * step
                top = round(
                    79 + 6 * math.sin(q * .035 + (side + 1))
                    + 2.5 * math.sin(q * .094 + step * .25) + .29 * (step - shore)
                )
                top = max(69, min(87, top))
                for y in range(top - 2, top + 1):
                    pos = (x, y, z)
                    if pos in occupied or pos in old:
                        continue
                    name = 'deepslate'
                    if y == top:
                        if (z // 7 + x // 4) % 9 == 0:
                            name = 'tuff'
                        elif (z // 11 + x // 3) % 5 == 0:
                            name = 'polished_basalt'
                        elif step == shore:
                            name = 'deepslate_tiles'
                    new[pos] = 'minecraft:' + name
    if not new:
        raise ValueError('No clear terrain positions found.')
    return {
        'schemaVersion': 1,
        'title': 'Low lateral banks with an open center',
        'blocks': [
            {'pos': list(pos), 'block': material}
            for pos, material in sorted({**old, **new}.items())
        ],
    }, len(new)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('machine', type=Path)
    parser.add_argument('--existing', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args=parser.parse_args()
    try:
        value, count = banks(args.machine, args.existing)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open('x', encoding='utf8') as stream:
            json.dump(value, stream, indent=2)
        print(f'{count} low lateral bank blocks; merged blueprint {args.out}')
    except (OSError,ValueError) as error:
        parser.error(str(error))
