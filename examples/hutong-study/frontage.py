"""Original small-scale Beijing hutong frontage studies for mcbuilder."""

import mcbuilder as mb

BASE = 'minecraft:polished_andesite'
BRICK = 'minecraft:tuff_bricks'
PANEL = 'minecraft:dark_oak_planks'
POST = 'minecraft:stripped_dark_oak_log[axis=y]'
BEAM = 'minecraft:stripped_dark_oak_log[axis=x]'
LATTICE = 'minecraft:dark_oak_fence[east=true,west=true,waterlogged=false]'
PLASTER = 'minecraft:light_gray_terracotta'
DARK_TILE = 'minecraft:deepslate_tile_slab[type=bottom,waterlogged=false]'
RIDGE = 'minecraft:polished_blackstone_brick_slab[type=bottom,waterlogged=false]'


def make_frontage(kind):
    """Local +x runs along the frontage. The front faces north; y=0 is the threshold."""
    width, depth, trim, entrance = {
        'narrow': (9, 8, 'minecraft:brown_terracotta', (3, 5)),
        'wide': (15, 10, 'minecraft:red_terracotta', (6, 8)),
        'shallow': (11, 6, 'minecraft:brown_terracotta', (4, 6)),
        'courtyard': (12, 9, 'minecraft:stripped_spruce_log[axis=y]', (4, 7)),
    }[kind]
    build = mb.Build(seed=37)
    end = width - 1
    with build:
        build.box((1, 0, 1), (end - 1, 0, depth - 1), BASE)
        build.box((entrance[0], 0, 0), (entrance[1], 0, 0), BASE)
        if kind == 'courtyard':
            build.box((1, 1, 2), (3, 4, 2), BRICK)
            build.box((8, 1, 2), (end - 1, 4, 2), BRICK)
            build.box((1, 1, 3), (1, 3, depth - 1), BRICK)
            build.box((end - 1, 1, 3), (end - 1, 3, depth - 1), BRICK)
            build.box((1, 1, depth - 1), (end - 1, 3, depth - 1), BRICK)
            for x in (3, 8):
                build.box((x, 1, 1), (x, 4, 1), trim)
            build.box((3, 1, 6), (8, 3, 6), PLASTER)
            build.box((3, 4, 6), (8, 4, 6), RIDGE)
            roof(build, 2, 9, 5)
            for lo, hi in ((0, 1), (10, 11)):
                build.box((lo, 5, 1), (hi, 5, 3), DARK_TILE)
        else:
            build.box((1, 1, depth - 1), (end - 1, 4, depth - 1), BRICK)
            for x in (1, end - 1):
                build.box((x, 1, 2), (x, 4, depth - 2), BRICK)
            for x in range(1, end):
                if entrance[0] <= x <= entrance[1]:
                    continue
                build.box((x, 1, 1), (x, 1, 1), BRICK)
                build.box((x, 2, 1), (x, 3, 1), LATTICE if x % 3 != 1 else trim)
                build.box((x, 4, 1), (x, 4, 1), PANEL)
            for x in (1, entrance[0] - 1, entrance[1] + 1, end - 1):
                build.box((x, 1, 1), (x, 4, 1), POST)
            build.box((1, 5, 1), (end - 1, 5, 1), BEAM)
            build.box((entrance[0], 4, 0), (entrance[1], 4, 0), trim)
            build.box((2, 1, depth - 3), (end - 2, 1, depth - 3), PANEL)
            build.box((2, 2, depth - 2), (end - 2, 2, depth - 2), 'minecraft:spruce_slab[type=top]')
            build.box((end - 2, 1, 3), (end - 2, 1, 4), 'minecraft:spruce_stairs[facing=west]')
            roof(build, 0, end, depth)
        for x in (entrance[0] - 1, entrance[1] + 1):
            build.box((x, 4, 0), (x, 4, 0), 'minecraft:lantern[hanging=true,waterlogged=false]')
    return build


def roof(build, lo, hi, depth):
    """Model the weather-side overhang, a raised ridge, and full-depth rear slope."""
    def stairs(facing, material='deepslate_tile_stairs'):
        return f'minecraft:{material}[facing={facing},half=bottom,shape=straight,waterlogged=false]'

    build.box((lo, 5, 0), (hi, 5, 0), stairs('south', 'polished_blackstone_brick_stairs'))
    build.box((lo, 6, 1), (hi, 6, 1), stairs('south'))
    middle = depth // 2
    build.box((lo, 7, 2), (hi, 7, middle), DARK_TILE)
    build.box((lo, 7, middle + 1), (hi, 7, middle + 1), RIDGE)
    if middle + 2 < depth - 1:
        build.box((lo, 6, middle + 2), (hi, 6, depth - 2), DARK_TILE)
        build.box((lo, 6, middle + 1), (hi, 6, middle + 1), 'minecraft:deepslate_tiles')
    for x in (lo + 1, hi - 1):
        build.box((x, 5, 2), (x, 6, middle), BRICK)
    build.box((lo, 5, depth - 1), (hi, 5, depth - 1), stairs('north'))
    for x in (lo, hi):
        build.box((x, 7, 2), (x, 7, middle), RIDGE)
