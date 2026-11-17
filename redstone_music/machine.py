"""Compile event IR to a physical even/odd redstone machine and playable world."""
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess

from .world import write_litematic, write_world

DEPENDENCY_FILES = ['redstone_music/assets/controls.mjs','redstone_music/assets/layout.json','redstone_music/world.py','redstone_music/runtime.py']


def fingerprint_inputs(ctx):
    cfg=ctx['config'].get('runtime',{})
    node=shutil.which('node')
    files=[Path(node)] if node else []
    if not cfg.get('serverValidation'):return files
    for key in ('java','serverJar','traceAgent','traceHook','asmJar'):
        if cfg.get(key):
            p=Path(cfg[key]);files.append(p if p.is_absolute() else Path(ctx['project'])/p)
    if cfg.get('traceAgent'):
        agent=Path(cfg['traceAgent']);agent=agent if agent.is_absolute() else Path(ctx['project'])/agent
        for key,name in [('traceHook','nevada-hook.jar'),('asmJar','asm.jar')]:
            if not cfg.get(key):files.append(agent.parent/name)
    return files


def dump(path, data): Path(path).write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')


def compile_blocks(events, title, namespace, objective, decorate=True):
    candidates=events['candidates']; length=max(1,int(events['musicGT']))
    total=max(256,math.ceil((80+length+48)/16)*16)
    layout=json.loads((Path(__file__).parent/'assets/layout.json').read_text(encoding='utf-8'))
    known={f['id'] for f in layout}
    if any(e['family'] not in known for e in candidates):raise ValueError('Unsupported family in event IR; provide a family mapping')
    grid={};notes=[];heads=[];repeaters=[];lights=[];families=[]
    def put(x,y,z,state,replace=False,nbt=None):
        k=(x,y,z);old=grid.get(k)
        if old and old['state']!=state and not replace:raise ValueError(f'Block collision at {k}: {old["state"]} / {state}')
        grid[k]={'x':x,'y':y,'z':z,'state':state,**({'nbt':nbt} if nbt else {})}
    def block(name,**props):return 'minecraft:'+name+('['+','.join(f'{k}={str(v).lower()}' for k,v in props.items())+']' if props else '')
    def rep(facing='north',delay=1,locked=False,powered=False):return block('repeater',facing=facing,delay=delay,locked=locked,powered=powered)
    slab=block('deepslate_tile_slab',type='top',waterlogged=False)
    for f in layout:
        group=[e for e in candidates if e['family']==f['id']]
        if not group:continue
        grouped=defaultdict(list)
        for e in group:grouped[int(e.get('q',e['gt']-events.get('sourceOffsetGT',0)))].append(e)
        rows=max(math.ceil(len(a)/3) for a in grouped.values());cx=37+math.floor(f['x']+.5);cy=112+math.floor(f['y']+.5)
        if cy+(rows-1)*6+2>=134:raise ValueError(f'{f["id"]} exceeds template polyphony; split/revoice this family')
        families.append({'id':f['id'],'label':f['label'],'centerX':cx,'centerY':cy,'rows':rows,'notes':len(group)})
        for row in range(rows):
            for parity in (0,1):
                x=cx+(2 if parity else -2);y=cy+row*6;z0=16+parity
                for z in range(z0,total-1):
                    put(x,y-1,z,slab)
                    state=block('polished_deepslate') if (z-z0)%2==0 else rep()
                    put(x,y,z,state)
                    if ':repeater[' in state:repeaters.append({'x':x,'y':y,'z':z,'state':state})
                if parity==0:
                    state=rep(delay=3);put(x,y-1,15,block('deepslate_bricks'));put(x,y,15,state)
                    repeaters.append({'x':x,'y':y,'z':15,'state':state});heads.append({'x':x,'y':y,'z':14,'on':block('redstone_block'),'off':block('air')})
                else:
                    put(x,y-1,11,block('sticky_piston',facing='up',extended=False));put(x,y,11,block('oak_log',axis='y'))
                    for i in range(1,4):put(x,y,11+i,block('oak_leaves',persistent=True,distance=i,waterlogged=False))
                    for rx,rz,state in [(x,16,rep(locked=True)),(x+1,16,rep('east',powered=True))]:
                        put(rx,y-1,rz,block('deepslate_bricks'));put(rx,y,rz,state);repeaters.append({'x':rx,'y':y,'z':rz,'state':state})
                    put(x+2,y-1,16,block('deepslate_bricks'));put(x+2,y,16,block('redstone_torch',lit=True))
                    heads.extend([{'x':x-1,'y':y-1,'z':11,'on':block('redstone_block'),'off':block('air')},
                                  {'x':x+2,'y':y-1,'z':16,'on':block('redstone_block'),'off':block('deepslate_bricks')}])
                    put(x,y,15,block('observer',facing='north',powered=False))
        for q,items in grouped.items():
            ordered=sorted(items,key=lambda e:(-e.get('gainProxy',1),e['note']))
            for row in range(rows):
                batch=ordered[row*3:row*3+3]
                if not batch:continue
                if len(batch)==3 and batch[2]['instrument']=='hat':
                    alt=next((i for i,e in enumerate(batch) if e['instrument']!='hat'),None)
                    if alt is None:raise ValueError('Three hats on one tick need separate physical lanes')
                    batch[alt],batch[2]=batch[2],batch[alt]
                parity=q%2;x=cx+(2 if parity else -2);y=cy+row*6;z=80+q;inward=1 if x<37 else -1
                for i,e in enumerate(batch):
                    nx=x+(inward if i==0 else -inward) if i<2 else x;ny=y if i<2 else y+1
                    by=y-1 if i<2 else y;bx=nx if i<2 else x
                    put(bx,by,z,e['baseBlock'],replace=(bx==x and by==y))
                    if e['baseBlock']=='minecraft:sand' and (bx,by-1,z) not in grid:put(bx,by-1,z,block('deepslate_bricks'))
                    put(nx,ny,z,block('note_block',instrument=e['instrument'],note=e['note'],powered=False))
                    notes.append({**e,'q':q,'x':nx,'y':ny,'z':z,'base':{'x':bx,'y':by,'z':z},'clockLane':{'x':x,'y':y,'parity':parity,'row':row}})
                put(x,y-1,z,block('redstone_wire',power=0,north='none',south='none',east='none',west='none'),replace=True)
                put(x,y-2,z,block('polished_blackstone'),replace=True)
                positions=[(-1,-2),(1,-2),(0,-3)] if len(batch)==3 else [(-1,-2),(1,-2)] if len(batch)==2 else [(0,-3)]
                ls=[]
                for dx,dy in positions:put(x+dx,y+dy,z,block('redstone_lamp',lit=False),replace=True);ls.append({'x':x+dx,'y':y+dy,'z':z})
                lights.append({'x':x,'y':y,'z':z,'q':q,'events':[e['id'] for e in batch],'lamps':ls})
    for x in range(30,45):
        for z in range(58,70):put(x,109,z,block('waxed_cut_copper' if x in (30,44) or z==58 else 'deepslate_tiles'))
    for x,label,command in [(31,'开始演奏',f'execute as @p at @s run function {namespace}:start'),(33,'停止复位',f'function {namespace}:stop'),
                            (35,'粒子关闭',f'function {namespace}:fx_off'),(39,'粒子开启',f'function {namespace}:fx_on'),
                            (41,'恢复默认',f'function {namespace}:p3_defaults'),(43,'返回起点','tp @p 37.5 111 68.5 180 0')]:
        put(x,110,63,block('command_block',facing='up',conditional=False),nbt={'id':'minecraft:command_block','Command':command,'auto':False,'TrackOutput':False})
        put(x,111,63,block('stone_button',face='floor',facing='north',powered=False))
        put(x,110,62,block('oak_sign',rotation=8,waterlogged=False),nbt={'id':'minecraft:sign','is_waxed':True,'front_text':{'messages':[json.dumps({'text':label},ensure_ascii=False),'""','""','""'],'color':'black','has_glowing_text':True}})
    decor=0
    if decorate:
        protected=set()
        for b in list(grid.values()):
            if any(t in b['state'] for t in ('repeater','wire','observer','piston','torch','note_block')):
                for dx in range(-2,3):
                    for dy in range(-2,3):
                        for dz in range(-2,3):protected.add((b['x']+dx,b['y']+dy,b['z']+dz))
        for f in families:
            for z in range(88,80+length,24):
                x=f['centerX'];y=f['centerY']-5
                module=[(x,y,z,block('ochre_froglight')),(x,y-1,z,slab),(x-1,y,z,block('waxed_cut_copper')),(x+1,y,z,block('waxed_cut_copper'))]
                if any((a,b,c) in grid or (a,b,c) in protected or b<88 for a,b,c,s in module):continue
                for a,b,c,s in module:put(a,b,c,s);decor+=1
    for n in notes:
        if (n['x'],n['y']+1,n['z']) in grid:raise ValueError(f'Blocked note {n["id"]}')
        if grid[n['base']['x'],n['base']['y'],n['base']['z']]['state']!=n['baseBlock']:raise ValueError('Instrument base overwritten')
    if len({(n['x'],n['y'],n['z']) for n in notes})!=len(notes):raise ValueError('Duplicate physical notes')
    for x,y,z in grid:
        if not (0<=x<80 and 88<=y<134 and 0<=z<total):raise ValueError('Template bounds exceeded')
    info={'version':'fx_pipeline_v1','title':title,'namespace':namespace,'objective':objective,'sourceMidiSha256':events.get('sourceMidiSha256'),
        'origin':{'x':0,'y':88,'z':0},'bounds':{'width':80,'height':46,'length':total},
        'excerpt':{'startGT':events.get('sourceOffsetGT',0),'musicGT':length,'seconds':events['durationSeconds'],'sourceStartSeconds':events.get('sourceOffsetGT',0)/20,'sourceEndSeconds':events.get('sourceOffsetGT',0)/20+events['durationSeconds']},
        'fxSample':{'id':'full','key':5,'world':'Performance','title':title,'length':length,'cut':0},
        'camera':{'x':37.5,'eyeY':112.5,'teleportDuration':3,'targetLeadBlocks':2,'speedBlocksPerSecond':20},
        'clock':{'musicBeginsAfterLaunchGT':70},'families':families,'noteEvents':len(notes),'onsets':sum(n['kind']!='retrigger' for n in notes),
        'retriggers':sum(n['kind']=='retrigger' for n in notes),'blocks':len(grid),'decorativeBlocks':decor,
        'claims':{'allMusicPhysicalRedstone':True,'runtimeVerified':False,'clientListening':False}}
    return info,list(grid.values()),notes,heads,repeaters,lights


def run(ctx):
    out=Path(ctx['out']);config=ctx['config'];events=json.loads((Path(ctx['deps']['sound'])/'events.json').read_text(encoding='utf-8'))
    slug=config['slug'];namespace='rm_'+slug;objective='rm_'+hashlib.sha256(slug.encode()).hexdigest()[:8]
    info,blocks,notes,heads,repeaters,lights=compile_blocks(events,config.get('title',slug),namespace,objective,config.get('machine',{}).get('decorate',True))
    for name,data in [('expected_events.json',{'info':info,'notes':notes}),('placed_blocks.json',{'info':info,'blocks':blocks}),('build_manifest.json',info),('light_modules.json',lights)]:dump(out/name,data)
    pack=out/'helper';pack.mkdir();args={'OUT':str(out),'PACK':str(pack),'FN':str(pack/'data/nevada_full/function'),
        'info':info,'blocks':blocks,'notes':notes,'heads':heads,'resetRepeaters':repeaters,'lightModules':lights}
    argsfile=out/'controls_input.json';dump(argsfile,args)
    node=shutil.which('node')
    if not node:raise RuntimeError('Node.js is required to compile the verified datapack template')
    subprocess.run([node,str(Path(__file__).parent/'assets/controls.mjs'),str(argsfile)],check=True,capture_output=True,text=True,timeout=180)
    argsfile.unlink()
    # Relocate namespace directory after rendering, with unique scoreboard/entity tags.
    (pack/'data/nevada_full').rename(pack/'data'/namespace)
    load=pack/'data'/namespace/'function/load.mcfunction';text=load.read_text(encoding='utf-8').splitlines()
    text.insert(1,f'execute unless score #built {objective} matches 1 run scoreboard players set #built {objective} 1')
    text.append(f'execute unless score #sub {objective} matches 0..1 run scoreboard players set #sub {objective} 1')
    load.write_text('\n'.join(text)+'\n',encoding='utf-8')
    state_file=pack/'data'/namespace/'function/fx_state.mcfunction'
    with state_file.open('a',encoding='utf-8') as stream:
        stream.write(f'execute store result storage {namespace}:fx subtitles int 1 run scoreboard players get #sub {objective}\n')
    scene=pack/'data'/namespace/'function/scene';scene.mkdir()
    for name,value in [('subtitles_on',1),('subtitles_off',0)]:
        (scene/(name+'.mcfunction')).write_text(f'scoreboard players set #sub {objective} {value}\n',encoding='utf-8')
    rounds={'schematic':write_litematic(out/'performance.litematic',blocks,info),'world':write_world(out/'world',blocks,info)}
    shutil.copytree(pack,out/'world/datapacks/helper')
    sound=Path(ctx['deps']['sound'])/'resources.zip'
    if sound.exists():shutil.copyfile(sound,out/'world/resources.zip')
    dump(out/'roundtrip.json',rounds)
    if config.get('runtime',{}).get('serverValidation'):
        from .runtime import run_server
        run_server(ctx,out,info)
    return {'notes':len(notes),'blocks':len(blocks),'namespace':namespace,'runtimeVerified':bool(config.get('runtime',{}).get('serverValidation'))}
