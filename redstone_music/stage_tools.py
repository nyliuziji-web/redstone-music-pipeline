"""Declarative stage modules and data-driven, music-clock visual scores.

The sparse VoxelGrid is from harrynull/mcbuild (MIT, Copyright 2026 Harry).
See integrations/mcbuild/provenance.json and LICENSE for the pinned source.
All other code here is local; previews contain no Minecraft textures.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

from ._vendor.mcbuild_voxel import VoxelGrid, VoxelLimitError

MAX_BLOCKS = 50000
MAX_OPERATIONS = 2000
KINDS = {'node', 'ring', 'helix', 'bezier'}
COLOR = {'voice': 'FFD17C', 'theme_attack': '57DFFF', 'theme_body': 'C78BFF',
         'piano': 'DAF3FF', 'bass': 'B1D79C', 'pad': '8EA8ED'}


def _read(value):
    if isinstance(value, dict):
        return json.loads(json.dumps(value, allow_nan=False))
    return json.loads(Path(value).read_text(encoding='utf-8-sig'))


def _write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _new_out(value):
    p = Path(value).resolve()
    if p.exists():
        raise ValueError(f'Refusing to overwrite output directory: {p}')
    p.mkdir(parents=True)
    return p


def _xyz(value, name='position'):
    if not isinstance(value, (list, tuple)) or len(value) != 3 or any(type(x) is not int or abs(x) > 30000000 for x in value):
        raise ValueError(f'{name} must have three bounded integer coordinates')
    return tuple(value)


def _box(value):
    if not isinstance(value, dict):
        raise ValueError('Box must contain min and max')
    lo, hi = _xyz(value.get('min'), 'min'), _xyz(value.get('max'), 'max')
    if any(a > b for a, b in zip(lo, hi)):
        raise ValueError('Inverted bounds')
    return lo, hi


def _inside(p, box):
    return all(a <= n <= b for n, a, b in zip(p, *box))


def _state(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9_.-]+:[a-z0-9_/.-]+(?:\[[a-z0-9_=,.-]+\])?', value):
        raise ValueError('Block state must be a namespaced identifier with valid properties')
    name, _, properties = value.partition('[')
    props = {}
    for item in properties.rstrip(']').split(',') if properties else []:
        if '=' not in item:
            raise ValueError('Block state properties need key=value')
        k, v = item.split('=', 1)
        if k in props:
            raise ValueError('Duplicate block state property')
        props[k] = v
    allowed = {'facing': {'north', 'south', 'east', 'west', 'up', 'down'},
               'half': {'top', 'bottom', 'upper', 'lower'}, 'waterlogged': {'true', 'false'},
               'axis': {'x', 'y', 'z'}}
    for k, values in allowed.items():
        if k in props and props[k] not in values:
            raise ValueError(f'Invalid {k} block property')
    if name.endswith('_slab') and props.get('type', 'bottom') not in {'bottom', 'top', 'double'}:
        raise ValueError('Invalid slab type')
    if name.endswith('_stairs') and props.get('facing', 'north') not in {'north', 'south', 'east', 'west'}:
        raise ValueError('Stairs require horizontal facing')
    return name + ('[' + ','.join(f'{k}={props[k]}' for k in sorted(props)) + ']' if props else '')


def evaluate_blueprint(blueprint, protection=None):
    """Evaluate bounded JSON operations. Returns grid/report; never writes a world."""
    data = _read(blueprint)
    if data.get('schemaVersion', 1) != 1:
        raise ValueError('Unsupported blueprint schemaVersion')
    operations = data.get('operations', [])
    blocks = data.get('blocks', [])
    if not isinstance(operations, list) or not isinstance(blocks, list) or len(operations) > MAX_OPERATIONS or len(blocks) > MAX_BLOCKS:
        raise ValueError('Blueprint exceeds limits or has invalid lists')
    grid, palette, states = VoxelGrid(), {}, []

    def place(position, state):
        state = _state(state)
        if state not in palette:
            palette[state] = len(states)
            states.append(state)
        try:
            grid.set(*position, palette[state])
        except VoxelLimitError as exc:
            raise ValueError('Stage module extent exceeds 512 blocks per axis; split into separately placed modules') from exc
        if len(grid) > MAX_BLOCKS:
            raise ValueError('Stage module exceeds block budget')

    for b in blocks:
        place(_xyz(b.get('pos')), b.get('block'))
    for op in operations:
        kind = op.get('op')
        block = _state(op.get('block', 'minecraft:stone_bricks'))
        if kind == 'set':
            place(_xyz(op.get('pos')), block)
        elif kind in {'fill', 'frame'}:
            lo, hi = _box(op)
            volume = math.prod(b - a + 1 for a, b in zip(lo, hi))
            if volume > MAX_BLOCKS:
                raise ValueError('Operation volume exceeds module budget')
            for x in range(lo[0], hi[0] + 1):
                for y in range(lo[1], hi[1] + 1):
                    for z in range(lo[2], hi[2] + 1):
                        edge = sum(n in (a, b) for n, a, b in zip((x, y, z), lo, hi))
                        if kind == 'fill' or edge >= 2:
                            place((x, y, z), block)
        elif kind == 'stairs':
            origin = _xyz(op.get('origin'))
            count = op.get('steps')
            direction = op.get('direction', 'north')
            if type(count) is not int or not 1 <= count <= 128 or direction not in {'north', 'south', 'east', 'west'}:
                raise ValueError('Invalid stairs operation')
            dx, dz = {'north': (0, -1), 'south': (0, 1), 'east': (1, 0), 'west': (-1, 0)}[direction]
            for i in range(count):
                place((origin[0] + dx * i, origin[1] + i, origin[2] + dz * i), block)
        else:
            raise ValueError(f'Unknown declarative operation: {kind}')
    if not len(grid):
        raise ValueError('Blueprint is empty')
    protected = _read(protection) if protection is not None else data.get('protection', {})
    boxes = [(_box(b), b.get('kind', 'protected')) for b in protected.get('boxes', [])]
    clearance = protected.get('circuitClearance', 2)
    if type(clearance) is not int or not 0 <= clearance <= 8:
        raise ValueError('circuitClearance must be 0..8')
    for p in protected.get('circuitBlocks', []):
        p = _xyz(p)
        boxes.append(((tuple(n - clearance for n in p), tuple(n + clearance for n in p)), 'circuit-neighborhood'))
    for p in protected.get('noteBlocks', []):
        p = _xyz(p)
        boxes.append(((tuple((p[0], p[1] - 1, p[2])), tuple((p[0], p[1] + 1, p[2]))), 'note-base-and-headroom'))
    for p in protected.get('cameraPath', []):
        p = _xyz(p)
        boxes.append(((tuple(n - 1 for n in p), tuple(n + 1 for n in p)), 'camera-clearance'))
    # Bucket protected boxes so a large module does not scan every circuit cell
    # for every decorative block. Very large explicit boxes remain a small list.
    buckets,large = {},[]
    for box,kind in boxes:
        lo,hi=box;first=tuple(n//16 for n in lo);last=tuple(n//16 for n in hi)
        if math.prod(b-a+1 for a,b in zip(first,last))>512:
            large.append((box,kind));continue
        for x in range(first[0],last[0]+1):
            for y in range(first[1],last[1]+1):
                for z in range(first[2],last[2]+1):
                    buckets.setdefault((x,y,z),[]).append((box,kind))
    conflicts = []
    for p, index in grid.items():
        for box, kind in buckets.get(tuple(n//16 for n in p),[])+large:
            if _inside(p, box):
                conflicts.append({'pos': list(p), 'block': states[index], 'reason': kind})
                break
    output = [{'pos': list(p), 'block': states[index]} for p, index in sorted(grid.items())]
    return output, {'schemaVersion': 1, 'sourceSha256': _digest(data), 'blockCount': len(grid),
                    'bounds': [list(p) for p in grid.bounds], 'materials': dict(Counter(b['block'] for b in output)),
                    'protected': not conflicts, 'conflicts': conflicts[:200], 'conflictCount': len(conflicts),
                    'scope': 'declarative geometry and protected cells; not redstone/physics/registry simulation'}


def _cuboids(block):
    """Simple architectural silhouettes; unsupported shape families remain cubes."""
    s = block['block']
    if s.split('[',1)[0].endswith('_slab') and 'type=double' not in s:
        return [(0, .5 if 'type=top' in s else 0, 0, 1, 1 if 'type=top' in s else .5, 1)]
    if '_stairs' in s:
        top = 'half=top' in s
        base = (0, .5 if top else 0, 0, 1, 1 if top else .5, 1)
        lo, hi = (0, .5) if top else (.5, 1)
        half = (0, lo, 0, 1, hi, .5)
        if 'facing=south' in s: half = (0, lo, .5, 1, hi, 1)
        elif 'facing=east' in s: half = (.5, lo, 0, 1, hi, 1)
        elif 'facing=west' in s: half = (0, lo, 0, .5, hi, 1)
        return [base, half]
    return [(0, 0, 0, 1, 1, 1)]


def _color(state):
    known = {'copper': (176, 105, 67), 'stone': (113, 125, 135), 'glass': (118, 197, 212),
             'wood': (157, 117, 67), 'oak': (157, 117, 67), 'sea_lantern': (202, 245, 227),
             'gold': (236, 197, 76), 'amethyst': (158, 111, 209)}
    for key, value in known.items():
        if key in state: return value
    return tuple(90 + v % 120 for v in hashlib.sha256(state.encode()).digest()[:3])


def render_views(blocks, out):
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise RuntimeError('CPU previews require Pillow; install the production extra') from exc
    views = []
    for view in range(4):
        faces = []
        angle = view * math.pi / 2
        c, s = round(math.cos(angle)), round(math.sin(angle))
        def rotate(p):
            x, y, z = p
            return x*c-z*s, y, x*s+z*c
        def project(p):
            x, y, z = rotate(p)
            return (x-z)*.8660254, (x+z)*.5-y
        for block in blocks:
            if block['block'] == 'minecraft:air': continue
            x, y, z = block['pos']
            color = _color(block['block'])
            for a,b,d,e,f,g in _cuboids(block):
                points = [(x+a,y+b,z+d),(x+e,y+b,z+d),(x+e,y+b,z+g),(x+a,y+b,z+g),
                          (x+a,y+f,z+d),(x+e,y+f,z+d),(x+e,y+f,z+g),(x+a,y+f,z+g)]
                for ids, shade in [((4,5,6,7),1.1),((0,1,5,4),.65),((1,2,6,5),.83),((2,3,7,6),.65),((3,0,4,7),.83)]:
                    polygon = [points[i] for i in ids]
                    depth = sum(rotate(p)[0]+rotate(p)[2]+rotate(p)[1]*.01 for p in polygon)/4
                    faces.append((depth, [project(p) for p in polygon], tuple(min(255,int(v*shade)) for v in color)))
        points = [p for _,poly,_ in faces for p in poly]
        if not points:
            raise ValueError('Blueprint has no visible blocks')
        minx,maxx = min(p[0] for p in points),max(p[0] for p in points)
        miny,maxy = min(p[1] for p in points),max(p[1] for p in points)
        scale = min(550/max(1,maxx-minx),380/max(1,maxy-miny))
        im = Image.new('RGB',(640,460),'#101a26'); draw = ImageDraw.Draw(im)
        for _,poly,color in sorted(faces,key=lambda f:f[0]):
            draw.polygon([(45+(x-minx)*scale,50+(y-miny)*scale) for x,y in poly],fill=color,outline='#29343e')
        draw.text((18,15),f'view {view+1}: simple-color CPU preview',fill='#dbeafa')
        im.save(Path(out)/f'view_{view+1}.png'); views.append(im)
    contact = Image.new('RGB',(1280,920),'#101a26')
    for i,im in enumerate(views): contact.paste(im,((i%2)*640,(i//2)*460))
    contact.save(Path(out)/'contact_sheet.png')
    return ['view_1.png','view_2.png','view_3.png','view_4.png','contact_sheet.png']


def preview_stage(blueprint, out, protection=None):
    blocks, report = evaluate_blueprint(blueprint, protection)
    dest = _new_out(out)
    _write(dest/'blocks.json', {'schemaVersion':1,'blocks':blocks})
    report['previews'] = render_views(blocks, dest)
    report['accepted'] = report['protected']
    report['clientVerified'] = False
    _write(dest/'report.json', report)
    return {**report, 'output':str(dest), 'contactSheet':str(dest/'contact_sheet.png')}


def effect_points(effect, q):
    """Deterministic geometry shared with the reference client, for review images."""
    begin,end = effect['beginGT'], effect['endGT']
    if not begin <= q < end: return []
    u = (q-begin)/max(1,end-begin)
    x,y,z = effect['position']; radius=effect.get('radius',1)
    n=effect.get('points',24); kind=effect['kind']; phase=u*math.tau
    if kind=='node':
        radius *= .4+.6*math.sin(math.pi*u)
        return [(x+radius*math.cos(t), y+radius*math.sin(t), z) for t in [i*math.tau/n for i in range(n)]]
    if kind=='ring':
        r=radius*(.1+u)
        return [(x+r*math.cos(i*math.tau/n),y,z+r*math.sin(i*math.tau/n)) for i in range(n)]
    if kind=='helix':
        return [(x+radius*math.cos(i*math.tau*2/n+phase),y+i*effect.get('height',3)/n,z+radius*math.sin(i*math.tau*2/n+phase)) for i in range(n)]
    control=effect['controlPoints']
    points=[]
    for i in range(n):
        t=max(0,min(1,u-.3+i*.3/max(1,n-1)));v=1-t
        points.append(tuple(v**3*control[0][j]+3*v*v*t*control[1][j]+3*v*t*t*control[2][j]+t**3*control[3][j] for j in range(3)))
    return points


def validate_show(data):
    if data.get('schemaVersion')!=1 or data.get('clock')!='musicGT':
        raise ValueError('Show requires schemaVersion=1 and clock=musicGT')
    length=data.get('lengthGT')
    if type(length) is not int or not 1 <= length <= 144000:
        raise ValueError('Invalid show duration')
    if not re.fullmatch(r'[a-z0-9_.-]+',data.get('namespace','')):
        raise ValueError('Invalid show namespace')
    seen=set()
    effects=data.get('effects',[])
    if not isinstance(effects,list) or len(effects)>20000:raise ValueError('Too many effects')
    for e in effects:
        if not isinstance(e.get('id'),str) or e['id'] in seen:raise ValueError('Duplicate or invalid effect id')
        seen.add(e['id'])
        if e.get('kind') not in KINDS:raise ValueError('Unsupported effect kind')
        if any(type(e.get(k)) is not int for k in ('beginGT','endGT')) or not 0<=e['beginGT']<e['endGT']<=length:
            raise ValueError('Effect outside show bounds')
        p=e.get('position')
        if not isinstance(p,list) or len(p)!=3 or any(not isinstance(v,(int,float)) or not math.isfinite(v) or abs(v)>30000000 for v in p):
            raise ValueError('Invalid effect position')
        if not re.fullmatch(r'[0-9a-fA-F]{6}',e.get('color','')):raise ValueError('Effect color must be RGB hex')
        if type(e.get('points',24)) is not int or not 4<=e.get('points',24)<=96:raise ValueError('Effect points must be 4..96')
        for k,default,lo,hi in [('radius',1,.01,32),('height',3,0,64),('size',.7,.1,4)]:
            v=e.get(k,default)
            if not isinstance(v,(int,float)) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError(f'Invalid effect {k}')
        if e['kind']=='bezier':
            c=e.get('controlPoints')
            if not isinstance(c,list) or len(c)!=4 or any(not isinstance(p,list) or len(p)!=3 or any(not isinstance(v,(int,float)) or not math.isfinite(v) or abs(v)>30000000 for v in p) for p in c):
                raise ValueError('Bezier needs four finite control points')
    if type(data.get('sampleKey',5)) is not int:raise ValueError('sampleKey must be integer')
    cues=data.get('captions',[])
    if not isinstance(cues,list) or len(cues)>2000:raise ValueError('Invalid caption list')
    for cue in cues:
        if not isinstance(cue,dict) or not isinstance(cue.get('text'),str) or len(cue['text'])>2000:
            raise ValueError('Caption needs bounded text')
        if any(type(cue.get(k)) is not int for k in ('begin','end')) or not 0<=cue['begin']<cue['end']<=length:
            raise ValueError('Caption outside show bounds')
        if any(not isinstance(cue.get(k,.5),(int,float)) or not math.isfinite(cue.get(k,.5)) or not 0<=cue.get(k,.5)<=1 for k in ('x','y')):
            raise ValueError('Caption anchors must be normalized')
    return data


def compile_show(score, out, style=None):
    data=_read(score); settings=_read(style) if style else {}
    if 'effects' in data:
        show=validate_show(data)
    else:
        info=data.get('info',{}); notes=data.get('notes',data.get('candidates',[]))
        length=info.get('excerpt',{}).get('musicGT') or data.get('musicGT') or max(1,math.ceil(data.get('durationSeconds',1)*20))
        namespace=settings.get('namespace',info.get('namespace','redstone_music'))
        cut=info.get('excerpt',{}).get('startGT',0)
        effects=[]; roles=sorted({n.get('family','melody') for n in notes})
        colors={**COLOR,**settings.get('colors',{})}
        for n in notes:
            if n.get('kind')=='retrigger':continue
            begin=int(n.get('q',n.get('gt',math.floor(n.get('sourceStartSeconds',0)*20+.5))))
            if not 0<=begin<length:continue
            family=n.get('family','melody');index=roles.index(family)
            end=min(length,max(begin+1,math.floor(n.get('sourceEndSeconds',(begin+cut+8)/20)*20+.5)-cut))
            pos=[float(n.get('x',index*4))+ .5,float(n.get('y',110))+1.3,float(n.get('z',begin))+.5]
            effects.append({'id':str(n.get('id',f'onset_{len(effects)}')),'sourceId':str(n.get('parentId',n.get('id',''))),
                'family':family,'kind':'helix' if end-begin>=16 else 'node','beginGT':begin,
                'endGT':end if end-begin>=16 else min(length,begin+10),'position':pos,
                'color':colors.get(family,'B4D8ED'),'radius':.8,'height':2.5,'size':.65,'points':16})
        show=validate_show({'schemaVersion':1,'clock':'musicGT','namespace':namespace,'sampleKey':settings.get('sampleKey',info.get('fxSample',{}).get('key',5)),
                            'lengthGT':length,'effects':effects,'captions':settings.get('captions',[]),'sourceSha256':_digest(data)})
    dest=_new_out(out)
    _write(dest/'show_score.json',show)
    report={'schemaVersion':1,'output':str(dest),'showScore':str(dest/'show_score.json'),'effects':len(show['effects']),
            'byKind':dict(Counter(e['kind'] for e in show['effects'])),'clientVerified':False,'artisticApproval':False,
            'backend':'reference-fabric-particles','scope':'deterministic effect geometry; no redstone audio replacement'}
    try:
        from PIL import Image,ImageDraw
        image=Image.new('RGB',(1200,650),'#101a26');draw=ImageDraw.Draw(image)
        times=sorted({e['beginGT'] for e in show['effects']})
        samples=[times[math.floor((len(times)-1)*i/5)] if times else 0 for i in range(6)]
        for i,q in enumerate(samples):
            points=[(p,e['color']) for e in show['effects'] for p in effect_points(e,q)]
            x0=(i%3)*400;y0=(i//3)*325
            draw.text((x0+12,y0+12),f'music GT {q} - geometry preview',fill='#dbeafa')
            if not points:continue
            xs=[p[0][0] for p in points];ys=[p[0][1] for p in points]
            scale=min(350/max(1,max(xs)-min(xs)),240/max(1,max(ys)-min(ys)))
            for p,c in points:
                x=x0+25+(p[0]-min(xs))*scale;y=y0+290-(p[1]-min(ys))*scale
                draw.ellipse((x-1,y-1,x+1,y+1),fill='#'+c)
        image.save(dest/'effect_contact.png');report['contactSheet']=str(dest/'effect_contact.png')
    except ImportError:
        report['warning']='Install Pillow for CPU effect contact sheets'
    _write(dest/'report.json',report)
    return report
