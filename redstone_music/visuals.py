"""Generate music-bound visual score, captions and optional Fabric client mod."""
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import zipfile

DEPENDENCY_FILES=['redstone_music/assets/PipelineFX.java','redstone_music/assets/PipelineCaptions.java']


def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def runtime_file(ctx):
    value=ctx['config'].get('runtime',{}).get('clientRuntime')
    if value:
        p=Path(value)
        return (p if p.is_absolute() else Path(ctx['project'])/p).resolve()
    p=Path(ctx['root'])/'.runtime/nevada_fx_client/runtime.json'
    return p if p.exists() else None


def compile_inputs(runtime):
    cfg=json.loads(Path(runtime).read_text(encoding='utf-8'));root=Path(cfg['root'])
    cp=[Path(p) for p in cfg['classpath'] if Path(p).name!=Path(cfg['original']).name+'.jar']
    cp+=list((Path(cfg['original'])/'.fabric/remappedJars').glob('**/client-intermediary.jar'))
    cp+=list((root/'game/mods').glob('*.jar'))+list((root/'compile_deps').glob('*.jar'))
    cp=[p.resolve() for p in cp if p.is_file()]
    java=Path(cfg['java']).parent/('javac.exe' if os.name=='nt' else 'javac')
    for p in [java]+cp:
        if any(c in str(p) for c in ('\r','\n','\0')):raise ValueError('Control character in compiler path')
    return java,list(dict.fromkeys(cp))


def fingerprint_inputs(ctx):
    p=runtime_file(ctx)
    if not p or not p.exists() or not ctx['config'].get('visuals',{}).get('enabled',True):return []
    java,cp=compile_inputs(p)
    return [p,java]+cp


def run(ctx):
    out=Path(ctx['out']);cfg=ctx['config'];machine=Path(ctx['deps']['machine'])
    expected=json.loads((machine/'expected_events.json').read_text(encoding='utf-8'));info=expected['info'];length=info['excerpt']['musicGT']
    score=json.loads((Path(ctx['deps']['music'])/'score.json').read_text(encoding='utf-8'))
    cut=info['excerpt'].get('startGT',0);notes=[]
    for n in expected['notes']:
        if n['kind']=='retrigger':continue
        notes.append({'id':n['id'],'parentId':n['parentId'],'family':n['family'],'q':n['q'],
            'end':min(length,max(n['q']+1,math.floor(n['sourceEndSeconds']*20+.5)-cut)),
            'midi':n['sourceMidi'],'gain':n.get('gainProxy',1),'kind':n['kind'],'x':n['x']+.5,'y':n['y']+.65,'z':n['z']+.5})
    notes.sort(key=lambda n:(n['q'],n['id']));sections=[];transitions=[]
    for i,s in enumerate(score.get('sections',[]) or [{'name':'SONG','beginGT':0,'endGT':length}]):
        begin=max(0,s['beginGT']-cut);end=min(length,s['endGT']-cut)
        if end<=begin:continue
        counts=Counter(n['family'] for n in notes if begin<=n['q']<end)
        focus='voice' if counts['voice'] else 'piano' if counts['piano']>counts['theme_attack'] else 'theme'
        sections.append({'name':s['name'],'begin':begin,'end':end,'focus':focus,'intensity':1.0,'widthScale':1.0})
        if i and begin>0:transitions.append({'id':f'section_{i}','q':begin,'begin':max(0,begin-8),'end':min(length,begin+36),'kind':'voice_crown' if focus=='voice' else 'piano_arc' if focus=='piano' else 'split_arch'})
    show={'id':cfg['slug'],'length':length,'cut':cut,'notes':notes,'sections':sections,'transitions':transitions}
    write(out/'show_assets.json',show)
    captions={'sampleKey':5,'mode':'fixed_screen','cues':[]}
    source=cfg.get('inputs',{}).get('captions')
    if source:
        p=Path(source);p=p if p.is_absolute() else Path(ctx['project'])/p
        supplied=json.loads(p.read_text(encoding='utf-8-sig'))
        for i,c in enumerate(supplied.get('cues',supplied) if isinstance(supplied,dict) else supplied):
            captions['cues'].append({'id':c.get('id',f'caption_{i}'),'translation':'','x':.5,'y':.8,'align':'center','effect':'fade_rule','color':'FFD69A',**c})
    elif length>40:
        captions['cues']=[{'id':'title','begin':0,'end':min(120,length),'text':cfg.get('title',cfg['slug']),'translation':'','x':.5,'y':.2,'align':'center','effect':'double_rule','color':'FFD69A'}]
    write(out/'captions.json',captions)
    warnings=[];enabled=cfg.get('visuals',{}).get('enabled',True);runtime=runtime_file(ctx)
    if enabled and runtime and runtime.is_file():
        javac,cp=compile_inputs(runtime)
        if not javac.is_file() or not cp:raise ValueError('Client compilation requires a Java 21 JDK and intermediary/Fabric classpath')
        source_dir=out/'java';source_dir.mkdir();classes=out/'classes';classes.mkdir()
        for name in ('PipelineFX','PipelineCaptions'):
            s=(Path(__file__).parent/'assets'/f'{name}.java').read_text(encoding='utf-8').replace('_NAMESPACE_',info['namespace']).replace('_OBJECTIVE_',info['objective'])
            if name=='PipelineFX':
                s=s.replace('new int[]{40,500,900,985,1180,1700,2100,2300,2640,2900,3140,3320,3820,4070}', 'new int[]{'+','.join(str(int(length*x)) for x in (.1,.35,.6,.85))+'}')
            (source_dir/f'{name}.java').write_text(s,encoding='utf-8')
        args=['-encoding','UTF-8','-proc:none','-classpath',os.pathsep.join(map(str,cp)),'-d',str(classes),str(source_dir/'PipelineFX.java'),str(source_dir/'PipelineCaptions.java')]
        argfile=out/'javac.args';argfile.write_text('\n'.join('"'+s.replace('\\','/').replace('"','\\"')+'"' for s in args),encoding='utf-8')
        result=subprocess.run([str(javac),'@'+str(argfile)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
        (out/'compiler.log').write_text(result.stdout+result.stderr,encoding='utf-8')
        if result.returncode:raise RuntimeError('Client compilation failed; see compiler.log: '+result.stderr[-1500:])
        assets=classes/'assets/redstone_music';assets.mkdir(parents=True)
        write(assets/'show_full.json',{'5':show});write(assets/'captions_scene.json',captions)
        metadata={'schemaVersion':1,'id':'redstone_music_show','version':'0.1.0','name':'Redstone Music Show','environment':'client',
            'entrypoints':{'client':['dev.redstone.pipeline.PipelineFX']},'depends':{'minecraft':'1.21.1','java':'>=21','fabricloader':'>=0.18.2','fabric-api':'*'}}
        write(classes/'fabric.mod.json',metadata)
        with zipfile.ZipFile(out/'client.jar','w',zipfile.ZIP_DEFLATED) as z:
            for p in sorted(classes.rglob('*')):
                if p.is_file():z.write(p,p.relative_to(classes).as_posix())
    elif enabled:warnings.append('Client build environment absent: assets generated, client rendering is not packaged. Set runtime.clientRuntime.')
    report={'schemaVersion':1,'visualOnsets':len(notes),'sections':len(sections),'transitions':len(transitions),'captions':len(captions['cues']),
        'clientJarBuilt':(out/'client.jar').is_file(),'clientVerified':False,'warnings':warnings}
    write(out/'report.json',report);return report
