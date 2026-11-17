"""Optional real-server replay in an isolated, owned Java process (Java 1.21.1)."""
import hashlib
import json
from pathlib import Path
import queue
import re
import shutil
import subprocess
import threading
import time


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_server(ctx,out,info):
    cfg=ctx['config'].get('runtime',{});out=Path(out)
    if not cfg.get('acceptEula'):raise ValueError('Real-server replay requires runtime.acceptEula=true after reviewing Minecraft EULA')
    def file(key):
        value=cfg.get(key)
        if not value:raise ValueError(f'runtime.{key} must point to an existing local file')
        p=Path(value)
        if not p.is_absolute():p=Path(ctx['project'])/p
        p=p.resolve(strict=True)
        if not p.is_file():raise ValueError(f'runtime.{key} is not a file')
        return p
    java=file('java');server=file('serverJar');agent=file('traceAgent')
    hook=file('traceHook') if cfg.get('traceHook') else (agent.parent/'nevada-hook.jar').resolve(strict=True)
    work=out/'server_test';work.mkdir()
    shutil.copytree(out/'world',work/'world')
    asm=file('asmJar') if cfg.get('asmJar') else (agent.parent/'asm.jar').resolve(strict=True)
    for source,target in [(server,'server.jar'),(agent,'nevada-trace.jar'),(hook,'nevada-hook.jar'),(asm,'asm.jar')]:shutil.copyfile(source,work/target)
    (work/'eula.txt').write_text('eula=true\n',encoding='utf-8')
    (work/'server.properties').write_text('online-mode=false\nserver-ip=127.0.0.1\nserver-port=0\nenable-command-block=true\nview-distance=3\nsimulation-distance=3\nspawn-protection=0\nmax-players=1\nlevel-name=world\n',encoding='utf-8')
    total_timeout=float(cfg.get('timeoutSeconds',max(300,info['excerpt']['musicGT']/10+240)))
    if not 10<=total_timeout<=86400:raise ValueError('runtime.timeoutSeconds must be between 10 and 86400')
    test_deadline=time.monotonic()+total_timeout
    proc=subprocess.Popen([str(java),'-Xms256M','-Xmx1536M','-javaagent:nevada-trace.jar','-jar','server.jar','nogui'],cwd=work,
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    lines=[];incoming=queue.Queue()
    def reader():
        for line in proc.stdout:incoming.put(line)
        incoming.put(None)
    threading.Thread(target=reader,daemon=True).start()
    def command(text):proc.stdin.write(text+'\n');proc.stdin.flush()
    def until(pattern,start=0,timeout=180):
        deadline=min(time.monotonic()+timeout,test_deadline)
        while time.monotonic()<deadline:
            text=''.join(lines[start:])
            if re.search(pattern,text):return text
            try:line=incoming.get(timeout=min(.2,max(.001,deadline-time.monotonic())))
            except queue.Empty:continue
            if line is None:raise RuntimeError(f'Test server exited {proc.poll()} before {pattern}')
            lines.append(line)
        raise TimeoutError(f'Server replay timed out waiting for {pattern}')
    def playback():
        begin=len(lines);command(f'function {info["namespace"]}:validate_start')
        until('NEVADA_FULL_LAUNCH',begin);command(f'scoreboard players get #launch {info["objective"]}')
        trace=until('NEVADA_FULL_READY',begin,info['excerpt']['musicGT']/20+180)
        launch=re.search(r'#launch has (\d+)',trace)
        if not launch:raise ValueError('Server did not report launch game tick')
        launch=int(launch.group(1));expected=json.loads((out/'expected_events.json').read_text(encoding='utf-8'))['notes']
        actual=parse_trace(trace)
        wanted=sorted((n['x'],n['y'],n['z'],n['instrument'],n['note'],launch+70+n['q']) for n in expected)
        observed=sorted((n['x'],n['y'],n['z'],n['instrument'],n['note'],n['gt']) for n in actual)
        if wanted!=observed:raise ValueError(f'Actual redstone differs: expected {len(wanted)} got {len(observed)}; first mismatch '+str(next(((a,b) for a,b in zip(wanted,observed) if a!=b),None)))
        bypos={(n['x'],n['y'],n['z']):n for n in expected}
        for n in actual:
            q=bypos[n['x'],n['y'],n['z']]['q']
            camera=info['camera']
            if n['camera']!=[camera['x'],camera['eyeY'],68.5+camera['targetLeadBlocks']+q]:raise ValueError('Actual server camera target drifted')
        return len(actual)
    try:
        until(r'Done \(');until('NEVADA_FULL_READY')
        count=playback()
        # Abort a second run during music, then replay a complete third run.
        begin=len(lines);command(f'function {info["namespace"]}:validate_start');until('NEVADA_FULL_LAUNCH',begin)
        until('NEVADA_NOTE',begin);command(f'function {info["namespace"]}:stop')
        trace=until('NEVADA_FULL_READY',begin)
        after=trace.split('NEVADA_FULL_STOP',1)
        if len(after)!=2 or 'NEVADA_NOTE|' in after[1]:raise ValueError('Notes remained after stop')
        replay=playback()
        begin=len(lines);command('save-all flush');until('Saved the game',begin);command('stop');proc.wait(timeout=40)
        if proc.returncode:raise RuntimeError(f'Test server exited {proc.returncode}')
        result={'schemaVersion':1,'expectedEventsSha256':sha(out/'expected_events.json'),
            'server':{'passed':True,'actualCount':count,'exactTimingPitchAndCamera':True,'normal20TPS':True,'abortNoExtraEvents':True,'replayCount':replay,
                'javaSha256':sha(java),'serverJarSha256':sha(server),'traceAgentSha256':sha(agent)},
            'client':{'passed':False},'listeningVerified':False}
        (out/'runtime_validation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    finally:
        if proc.poll() is None:
            try:command('stop');proc.wait(timeout=30)
            except (OSError,subprocess.TimeoutExpired):proc.terminate();proc.wait(timeout=10)
        while not incoming.empty():
            line=incoming.get()
            if line:lines.append(line)
        (out/'server_playback.log').write_text(''.join(lines),encoding='utf-8')
        # Retain evidence, not third-party game binaries or the disposable world.
        for name in ('server.jar','nevada-trace.jar','nevada-hook.jar','asm.jar'):(work/name).unlink(missing_ok=True)


def parse_trace(trace):
    pattern=r'NEVADA_NOTE\|(\d+)\|jd\{x=(-?\d+), y=(-?\d+), z=(-?\d+)\}\|Block\{minecraft:note_block\}\[instrument=([^,]+),note=(\d+),powered=(?:true|false)\]\|CAM\|([\d.-]+),([\d.-]+),([\d.-]+)'
    return [{'gt':int(m[1]),'x':int(m[2]),'y':int(m[3]),'z':int(m[4]),'instrument':m[5],'note':int(m[6]),'camera':[float(m[7]),float(m[8]),float(m[9])]} for m in re.finditer(pattern,trace)]
