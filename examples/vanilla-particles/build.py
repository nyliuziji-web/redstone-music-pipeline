"""Build a vanilla, music-synchronized particle layer over an exported machine world."""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import shutil

WARM, IVORY, MINT, LILAC = (1.,.72,.27),(1.,.97,.82),(.35,1.,.86),(.83,.76,1.)
COLORS = {'theme_attack':WARM,'voice':IVORY,'echo':MINT,'answer':LILAC}
CORE = 'minecraft:end_rod'


def build(machine, out, density, width, scale, viewer_radius, daytime):
    read = lambda name: json.loads((machine/name).read_text(encoding='utf8'))
    score = read('expected_events.json')
    info = score['info']
    length = info['excerpt']['musicGT']
    phases = info.get('trackPlan',{}).get('sections',[])
    if not phases or not 0 < length <= 2400:
        raise ValueError('Use a score-led representative excerpt up to 2400 GT.')
    ns, clock = info['namespace'], info['objective']
    cam = info['camera']
    center = cam['x']
    blocks = {(b['x'],b['y'],b['z']) for b in read('placed_blocks.json')['blocks']
              if b['state'] != 'minecraft:air'}
    schedule = defaultdict(lambda: defaultdict(list))
    starts = [n for n in score['notes'] if n['kind']=='onset']
    if not starts:
        raise ValueError('The study needs physical onset events.')

    def rgb(values):
        return '[' + ','.join(f'{v:.3f}f' for v in values) + ']'

    def add(q,layer,at,kind,args,count):
        if not 0<=q<=length+16 or tuple(map(math.floor,at)) in blocks:
            return
        xyz = ' '.join(f'{v:.3f}' for v in at)
        line = f'execute positioned {xyz} run particle {kind} ~ ~ ~ {args} force @a[distance=..{viewer_radius}]'
        schedule[q][layer].append((line,count))

    def dust(q,layer,at,color,size):
        end=tuple(.22+v*.38 for v in color)
        kind=f'minecraft:dust_color_transition{{from_color:{rgb(color)},to_color:{rgb(end)},scale:{min(4,size*scale):.3f}f}}'
        add(q,layer,at,kind,'0 0 0 0 1',1)

    def glow(q,layer,at,spread,count):
        add(q,layer,at,CORE,f'{spread:.2f} {spread*.62:.2f} {spread:.2f} .035 {count}',count)

    def anchor(note):
        return note['x']+.5,note['y']+1.24,note['z']+.5

    grouped=defaultdict(list)
    for n in starts:
        q,role=n['q'],n['family']
        leading=role in COLORS
        color=COLORS.get(role,LILAC if role=='sub_bass' else (.80,.73,.51))
        x,y,z=anchor(n)
        glow(q,'hits',(x,y,z),.38*width,14 if leading else 7)
        dust(q,'hits',(x,y+.27,z),color,2.04 if leading else 1.43)
        for lag in ((0,2,4,6) if leading else (0,2)):
            r=(.86+lag*.22)*width
            points=max(3,round((9 if leading else 5)*density))
            for j in range(points):
                a=math.tau*j/points+lag*.19
                dust(q+lag,'hits',(x+r*math.cos(a),y+.66*r*math.sin(a)+lag*.10,z+lag*.13),
                     color,1.42 if not lag else 1.02)
        if leading:
            grouped[n['clockLane']['launchGT'],role].append(n)

    for (_,role), notes in grouped.items():
        ordered=sorted(notes,key=lambda n:n['q'])
        for a,b in zip(ordered,ordered[1:]):
            span=b['q']-a['q']
            if not 3<=span<=15 or abs(a['x']-b['x'])>7:
                continue
            start,end=anchor(a),anchor(b)
            for step in range(1,span):
                u=step/span
                x,y,z=(v+(w-v)*u for v,w in zip(start,end))
                y+=math.sin(math.pi*u)*1.25
                dust(a['q']+step,'traces',(x,y,z),IVORY,1.29)
                for dx in (-.64,.64):
                    dust(a['q']+step,'traces',(x+dx,y-.15,z),COLORS[role],.92)

    for index,section in enumerate(phases):
        # Launch after the opening establishment, or at the actual following phrase boundary.
        start=section['beginGT']+(min(18,(section['endGT']-section['beginGT'])//3) if not index else 0)
        span=min(30,section['endGT']-start)
        z0=start+104-cam.get('followBack',0)*.5
        hue=(WARM,MINT,IVORY,LILAC)[index%4]
        ribs=max(12,round(21*density))
        direction=1 if index%2 else -1
        for t in range(0,span,2):
            for row,lag in enumerate((0,5,10)):
                age=(t-lag)/span
                if not 0<=age<=.89:
                    continue
                r=(4+13*math.sin(age*math.pi*.72))*width
                for j in range(ribs):
                    a=math.tau*j/ribs+direction*.075*t+row*.19
                    if math.sin(a)<-.52:   # retain a window onto the playing bays
                        continue
                    at=(center+r*math.cos(a),cam['eyeY']+1.9+r*.31*math.sin(a),
                        z0+t*.64+row*1.8+3.0*math.sin(2*a))
                    dust(start+t,'phrases',at,hue if row!=1 else IVORY,(1.92-.82*age)*(1-.10*row))
                    if row==0 and j%7==0 and t%4==0:
                        glow(start+t,'phrases',at,.64,8)

    # Only emit background strokes around sparse passages, at the edges rather than in the center.
    for q in range(12,length-16,5):
        if schedule[q].get('phrases') or len(schedule[q].get('hits',()))>28:
            continue
        for side in (-1,1):
            for j in range(round(5*density)):
                at=(center+side*(12.5+1.3*j*width),cam['eyeY']-.4+math.sin(q*.12+j),q+96+j*1.62)
                dust(q,'ambient',at,(.66,.59,.82),.74)

    # Reject over-budget presets before creating the output world; no silent thinning.
    peak=max(sum(map(len,layers.values())) for layers in schedule.values())
    if peak>210:
        raise ValueError(f'{peak} particle commands in one tick exceeds the study budget of 210; lower density.')

    out.mkdir(parents=True)
    world=out/'world'
    shutil.copytree(machine/'world',world)
    pack=world/'datapacks/helper/data'
    fn=pack/'rail_fx/function'

    def write(name,lines):
        dest=fn/(name+'.mcfunction')
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text('\n'.join(lines)+'\n',encoding='utf8')

    dispatch=[]
    for start in range(0,length+17,32):
        lines=[]
        end=min(start+31,length+16)
        for q in range(start,end+1):
            beat=[]
            if q in {p['beginGT'] for p in phases}:
                beat.append(f'execute unless entity @a run say RAILFX_ACT_{q}')
            for layer,items in schedule.get(q,{}).items():
                write(f'{layer}/{q}',[command for command,_ in items])
                guard='execute if score #mode rail_fx matches 2 run ' if layer!='hits' else ''
                beat.append(guard+f'function rail_fx:{layer}/{q}')
            if beat:
                write(f'beat/{q}',beat)
                lines.append(f'execute if score #q {clock} matches {q} run function rail_fx:beat/{q}')
        if lines:
            write(f'segment/{start}',lines)
            dispatch.append(f'execute if score #q {clock} matches {start}..{end} run function rail_fx:segment/{start}')
    write('dispatch',dispatch)
    write('tick',[
        'execute unless score #mode rail_fx matches 0..2 run scoreboard players set #mode rail_fx 2',
        f'execute if score #busy {clock} matches 2 if score #mode rail_fx matches 1.. run function rail_fx:dispatch',
    ])
    for name,value in [('off',0),('notes',1),('full',2)]:
        write(name,[f'scoreboard players set #mode rail_fx {value}'])
    for name,lines in [('load',['scoreboard objectives add rail_fx dummy',f'time set {daytime}']),
                       ('tick',['function rail_fx:tick'])]:
        with (pack/ns/'function'/(name+'.mcfunction')).open('a',encoding='utf8') as stream:
            stream.write('\n'.join(lines)+'\n')
    counts=Counter()
    for layers in schedule.values():
        for layer,items in layers.items():
            counts[layer]+=sum(count for _,count in items)
    shutil.copy2(machine/'expected_events.json',out/'expected_events.json')
    report={'scoreGT':length,'scoreNotes':len(score['notes']),'onsets':len(starts),
            'requestedParticlesByLayer':dict(counts),'peakCommandsPerTick':peak,
            'density':density,'width':width,'scale':scale,'viewerRadius':viewer_radius,'daytime':daytime,
            'visualAcceptance':'requires client viewing'}
    (out/'particle-budget.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('machine',type=Path)
    parser.add_argument('out',type=Path)
    parser.add_argument('--density',type=float,default=1.35)
    parser.add_argument('--width',type=float,default=1.18)
    parser.add_argument('--scale',type=float,default=1.30)
    parser.add_argument('--viewer-radius',type=int,default=50)
    parser.add_argument('--daytime',type=int,default=12850)
    a=parser.parse_args()
    if not (.5<=a.density<=2 and .7<=a.width<=1.55 and .65<=a.scale<=1.8
            and 24<=a.viewer_radius<=64 and 0<=a.daytime<24000):
        parser.error('Density .5..2, width .7..1.55, scale .65..1.8, viewer radius 24..64, daytime 0..23999.')
    try:
        print(json.dumps(build(a.machine,a.out,a.density,a.width,a.scale,a.viewer_radius,a.daytime),indent=2))
    except (ValueError,OSError) as error:
        parser.error(str(error))
