"""Compile and protect authored vanilla spectator camera poses."""

from collections import defaultdict
import math

PRE_ROLL = 20
POST_ROLL = 20
POSE_FIELDS = ('x', 'eyeY', 'yaw', 'pitch')


def compile_camera_rail(camera, length):
    keys = camera.pop('keyframes', None)
    back = camera.get('followBack', 0)
    if type(back) not in (int, float) or not math.isfinite(back) or not 0 <= back <= 16:
        raise ValueError('Camera followBack must be 0..16 blocks')
    if keys is None:
        if back:
            raise ValueError('Camera followBack requires authored keyframes')
        return
    if not isinstance(keys, list) or not 2 <= len(keys) <= 64 or length > 2400:
        raise ValueError('Camera rail requires 2..64 keyframes for a score up to 120 seconds')
    for row in keys:
        if (not isinstance(row, dict) or set(row) != {'atGT', *POSE_FIELDS}
                or type(row['atGT']) is not int
                or any(type(row[k]) not in (int, float) or not math.isfinite(row[k]) for k in POSE_FIELDS)
                or not (4 <= row['x'] <= 75 and 92 <= row['eyeY'] <= 129
                        and -55 <= row['yaw'] <= 55 and -35 <= row['pitch'] <= 50)):
            raise ValueError('Camera keyframe needs atGT, x, eyeY, yaw and pitch inside the following corridor')
    if keys[0]['atGT'] != -PRE_ROLL or keys[-1]['atGT'] != length + POST_ROLL:
        raise ValueError('Camera keyframes must cover -20 through musicGT plus 20')
    if any(b['atGT'] - a['atGT'] < 12 for a, b in zip(keys, keys[1:])):
        raise ValueError('Camera keyframes must be ordered and at least 12 ticks apart')
    frames = []
    for a, b in zip(keys, keys[1:]):
        span = b['atGT'] - a['atGT']
        for i in range(span):
            u = i / span
            weight = u * u * (3 - 2 * u)
            frames.append([round(a[k] + (b[k] - a[k]) * weight, 3) for k in POSE_FIELDS])
    frames.append([keys[-1][k] for k in POSE_FIELDS])
    camera['rail'] = {'beginGT': -PRE_ROLL, 'keyframes': keys, 'frames': frames}


def camera_target(camera, tick):
    rail = camera.get('rail')
    x, y = rail['frames'][tick - rail['beginGT']][:2] if rail else (camera['x'], camera['eyeY'])
    return x, y, 68.5 + camera['targetLeadBlocks'] + tick - camera.get('followBack', 0)


def check_camera_clearance(camera, blocks):
    rail = camera.get('rail')
    if not rail:
        return
    by_z = defaultdict(list)
    for block in blocks:
        if block['state'] != 'minecraft:air':
            by_z[block['z']].append(block)
    for tick in range(rail['beginGT'], rail['beginGT'] + len(rail['frames'])):
        pose = camera_target(camera, tick)
        for z in range(math.floor(pose[2])-2, math.floor(pose[2])+3):
            for block in by_z[z]:
                position = tuple(block[k] for k in ('x', 'y', 'z'))
                if all(start-1 <= value <= start+2 for start, value in zip(position, pose)):
                    raise ValueError(f'Camera clearance conflict at tick {tick} with block {position}')
