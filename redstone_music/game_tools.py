"""Explicit, local Minecraft environment import and reproducible client builds."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import zipfile


def _hash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def _write(path, data):
    Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def java_info(java=None):
    path=Path(java).expanduser() if java else Path(shutil.which('java') or 'missing-java')
    if path.is_dir():path=path/'bin'/('java.exe' if os.name=='nt' else 'java')
    if not path.is_file():return {'available':False,'reason':'Provide --java pointing to a Java21 JDK or its java executable'}
    try:
        run=subprocess.run([str(path.resolve()),'-version'],capture_output=True,text=True,timeout=10)
    except (OSError,subprocess.TimeoutExpired) as exc:
        return {'available':False,'path':str(path.resolve()),'reason':str(exc)}
    output=run.stdout+run.stderr
    match=re.search(r'(?:version\s+"|openjdk\s+)(\d+)',output)
    major=int(match.group(1)) if match else None
    javac=path.with_name('javac.exe' if os.name=='nt' else 'javac')
    return {'available':run.returncode==0,'path':str(path.resolve()),'major':major,
            'jdk':javac.is_file(),'supported':major==21 and javac.is_file()}


def inspect_mod(jar):
    p=Path(jar)
    try:
        with zipfile.ZipFile(p) as z:
            if 'fabric.mod.json' not in z.namelist():return {'filename':p.name,'loader':'other','sha256':_hash(p)}
            info=z.getinfo('fabric.mod.json')
            if info.file_size>1024*1024:raise ValueError('Oversized mod metadata')
            data=json.loads(z.read('fabric.mod.json'))
            if not isinstance(data,dict):raise ValueError('Mod metadata must be an object')
            return {'filename':p.name,'loader':'fabric','id':data.get('id'),'version':data.get('version'),
                    'depends':data.get('depends',{}),'environment':data.get('environment','*'),
                    'declaredLicense':data.get('license'),'contact':data.get('contact',{}),'sha256':_hash(p)}
    except (zipfile.BadZipFile,ValueError,KeyError) as exc:
        return {'filename':p.name,'loader':'invalid','error':str(exc)}


def inspect_game(instance, java=None):
    """Read only game/version/mod metadata. Never reads launcher tokens/accounts."""
    root=Path(instance).expanduser().resolve(strict=True)
    if not root.is_dir():raise ValueError('Minecraft instance must be a directory')
    versions=[]
    version_dir=root/'versions'
    if version_dir.is_dir():
        for p in sorted(version_dir.glob('*/*.json')):
            if p.stat().st_size>4*1024*1024:continue
            try:
                data=json.loads(p.read_text(encoding='utf-8-sig'))
                if data.get('id')=='1.21.1' or data.get('inheritsFrom')=='1.21.1':
                    versions.append({'id':data.get('id'),'parent':data.get('inheritsFrom'),'file':str(p),'sha256':_hash(p)})
            except (ValueError,OSError):continue
    mods=[inspect_mod(p) for p in sorted((root/'mods').glob('*.jar'))]
    java_result=java_info(java)
    issues=[]
    if not java_result.get('supported'):issues.append('Java21 JDK is required; PATH Java alone may be an older runtime')
    if not versions:issues.append('No Java1.21.1 launcher profile found here; game-directory-only imports need a separate launcher root')
    if not (root/'assets').is_dir():issues.append('Minecraft assets directory not found in selected root')
    return {'schemaVersion':1,'instance':str(root),'java':java_result,'versions':versions,'mods':mods,
            'assetsPresent':(root/'assets').is_dir(),'librariesPresent':(root/'libraries').is_dir(),
            'issues':issues,'clientLaunched':False,'credentialsRead':False,
            'scope':'metadata inspection; does not establish authenticated launch, rendering or sound'}


def import_game(instance, out, java=None):
    """Create an isolated writable game dir and explicit references to local assets."""
    dest=Path(out).resolve()
    if dest.exists():raise ValueError('Refusing to overwrite imported runtime')
    report=inspect_game(instance,java)
    source=Path(report['instance'])
    if dest==source or dest.is_relative_to(source):
        raise ValueError('Runtime output must be outside the source Minecraft directory')
    dest.mkdir(parents=True);game=dest/'game';(game/'mods').mkdir(parents=True)
    imported=[]
    for m in report['mods']:
        if m.get('id')=='fabric-api':
            path=source/'mods'/m['filename'];shutil.copyfile(path,game/'mods'/path.name);imported.append(m)
    profile={'schemaVersion':1,'minecraft':'1.21.1','java':report['java'].get('path'),
             'sourceRoot':str(source),'gameDir':str(game),'assets':str(source/'assets'),
             'libraries':str(source/'libraries'),'versions':report['versions'],
             'importedMods':imported,'requiredMods':['fabric-api','redstone_music_show'],
             'credentials':'provided by the operator launcher; never stored here',
             'launchInstructions':'Configure an installed Java1.21.1 Fabric launcher profile to use gameDir. Install the generated client.jar and matching Fabric API; then use the launcher normally.',
             'dependencyCompatibilityVerified':False,'clientVerified':False,'audioVerified':False}
    _write(dest/'runtime_profile.json',profile);_write(dest/'inspection.json',report)
    return {'output':str(dest),'profile':str(dest/'runtime_profile.json'),'gameDir':str(game),
            'importedMods':len(imported),'issues':report['issues'],'clientLaunched':False}


def build_client(source, out, java=None, gradle=None):
    """Run the standard Loom build in the explicitly selected source checkout."""
    root=Path(source).resolve(strict=True)
    if not (root/'build.gradle').is_file() or not (root/'settings.gradle').is_file():
        raise ValueError('Expected the client Gradle source project')
    jdk=java_info(java)
    if not jdk.get('supported'):raise ValueError('Client build requires an explicit Java21 JDK')
    if gradle:
        executable=Path(gradle).resolve(strict=True)
    else:
        executable=root/('gradlew.bat' if os.name=='nt' else 'gradlew')
        if not executable.is_file():raise ValueError('Supply Gradle8.12.1 or the source wrapper')
    dest=Path(out).resolve()
    if dest.exists():raise ValueError('Refusing to overwrite client build report')
    dest.mkdir(parents=True)
    env=dict(os.environ);env['JAVA_HOME']=str(Path(jdk['path']).parent.parent)
    env['PATH']=str(Path(jdk['path']).parent)+os.pathsep+env.get('PATH','')
    # Cache within ignored project state so failed/repeated builds reuse downloads.
    env['GRADLE_USER_HOME']=env.get('GRADLE_USER_HOME',str(root/'.gradle/rmp-user-home'))
    command=[str(executable),'--no-daemon','--console=plain','--info','--max-workers=2',
             '-Dfabric.loom.ci=true',
             '-Dorg.gradle.internal.http.connectionTimeout=30000',
             '-Dorg.gradle.internal.http.socketTimeout=30000','build']
    # Stream to disk: operators can inspect dependency progress during long first builds.
    with (dest/'build.log').open('w',encoding='utf-8') as log:
        try:
            run=subprocess.run(command,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=900)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError('Fabric build exceeded 15 minutes; inspect '+str(dest/'build.log')) from exc
    if run.returncode:raise RuntimeError('Fabric build failed; inspect '+str(dest/'build.log'))
    jars=[p for p in (root/'build/libs').glob('*.jar') if not any(x in p.name for x in ('sources','dev','javadoc'))]
    if len(jars)!=1:raise RuntimeError('Expected one remapped runtime JAR')
    shutil.copyfile(jars[0],dest/'client.jar')
    report={'schemaVersion':1,'clientJar':str(dest/'client.jar'),'sha256':_hash(dest/'client.jar'),
            'java':jdk,'builtWith':'Fabric Loom / Gradle','clientVerified':False,'listeningVerified':False}
    _write(dest/'report.json',report)
    return report


def plan_photon_comparison(show, out, mod_jar):
    """Prepare an identical-score comparison from an explicitly supplied Photon1.6 JAR.

    Static metadata/class inspection only: never executes, installs or copies the JAR,
    and does not pretend that the reference geometry is a compiled Photon .fx file.
    """
    from .stage_tools import validate_show
    source=Path(show).resolve(strict=True);jar=Path(mod_jar).resolve(strict=True)
    score=validate_show(json.loads(source.read_text(encoding='utf-8-sig')))
    metadata=inspect_mod(jar)
    if metadata.get('id')!='photon' or str(metadata.get('version'))!='1.6':
        raise ValueError('This experimental comparison supports explicitly supplied Photon Fabric1.6 only')
    commands=[]
    with zipfile.ZipFile(jar) as z:
        name='com/lowdragmc/photon/client/ClientCommands.class'
        if name not in z.namelist() or z.getinfo(name).file_size>1024*1024:
            raise ValueError('Photon client command class missing or oversized')
        bytecode=z.read(name)
        for value in ('photon_editor','photon_client','clear_particles','clear_client_fx_cache'):
            if value.encode() in bytecode:commands.append(value)
    changes={}
    for effect in score.get('effects',[]):
        points=effect.get('points',24)
        changes[effect['beginGT']]=changes.get(effect['beginGT'],0)+points
        changes[effect['endGT']]=changes.get(effect['endGT'],0)-points
    active=peak=0
    for q in sorted(changes):active+=changes[q];peak=max(peak,active)
    dest=Path(out).resolve()
    if dest.exists():raise ValueError('Refusing to overwrite Photon comparison')
    dest.mkdir(parents=True)
    _write(dest/'show_score.json',score)
    checks=[
        ('environment','Launch isolated Java1.21.1 Fabric profile with the inspected Photon and its declared dependencies; retain exact hashes.'),
        ('authoring','Author/export original Photon effects matching each source effect kind, timing, color and trajectory. No automatic .fx translation exists here.'),
        ('same-scene','Use the same physical music clock, module, camera path, resolution and shader settings. Keep independent reference and Photon captures.'),
        ('synchronization','Check first note, long sustain, section transition and final stop against the machine musicGT clock; record measured offsets.'),
        ('cleanup','Stop mid-show, replay twice and unload the world. Record owned-effect cleanup and any remaining particles.'),
        ('performance','Record FPS/frame-time, active particle counts, tick behavior and recording load for both backends with identical settings.'),
        ('captions','Check caption readability and F1 behavior with the final shaders.'),
        ('artistic-review','Present both representative clips to the user; record the accepted backend and requested changes.')]
    report={'schemaVersion':1,'status':'comparison-prepared','showScore':str(dest/'show_score.json'),
        'sourceShowSha256':_hash(source),'lengthGT':score['lengthGT'],'clock':'musicGT',
        'effects':len(score.get('effects',[])),'effectKinds':sorted({e['kind'] for e in score.get('effects',[])}),
        'requestedPeakPointsPerTick':peak,'referencePointBudgetPerTick':1200,
        'referenceBudgetClips':peak>1200,'photon':metadata,
        'photonCommandConstants':commands,'commandVerification':'class constants present; not executed',
        'jarCopied':False,'clientLaunched':False,'photonRuntimeIntegrated':False,
        'photonEffectsCompiled':False,'clientVerified':False,'artisticApproval':False,
        'licenseReview':'Installed metadata is a declaration, not a redistribution grant. Check this exact release and upstream license before distribution.',
        'sources':['https://modrinth.com/mod/photon-editor-fabric/version/1.6','https://github.com/ELBGG/Photon'],
        'checks':[{'id':key,'status':'pending','instruction':instruction} for key,instruction in checks],
        'evidence':{'referenceVideo':None,'photonVideo':None,'performanceLogs':[],'userDecision':None}}
    _write(dest/'comparison.json',report)
    return report
