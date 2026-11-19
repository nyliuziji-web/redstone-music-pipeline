"""Portable capability discovery and evidence-backed project handoff.

These tools never grant an artistic or runtime pass from an import check.
"""
from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

from .core import atomic_json, hash_file, load_config, owned, project_lock, read_json


def resource_root():
    source = Path(__file__).resolve().parent.parent
    return source if (source / 'START_HERE.md').is_file() else Path(__file__).parent / 'kit_data'


def _command(name, args, minimum=None):
    executable = shutil.which(name)
    if not executable:
        return {'available': False, 'reason': f'{name} not found on PATH', 'remedy': 'See docs/ENVIRONMENT.md or supply an explicit tool path'}
    try:
        result = subprocess.run([executable, *args], capture_output=True, text=True, errors='replace', timeout=15)
        output = (result.stdout + result.stderr).strip()
        match = re.search(r'(?:version\s+\"?|v)?(\d+)\.(\d+)', output)
        version = tuple(map(int, match.groups())) if match else None
        okay = result.returncode == 0 and (minimum is None or version is not None and version >= minimum)
        return {'available': okay, 'path': executable, 'versionOutput': output[:350],
                'reason': None if okay else f'Command failed or version below {minimum}'}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'available': False, 'path': executable, 'reason': str(exc)}


def capabilities(project=None, probe=False):
    """Probe real lightweight operations, never download or launch Minecraft."""
    modules = {}
    checks = {'numpy': 'numpy', 'nbtlib': 'nbtlib', 'mido': 'mido', 'soundfile': 'soundfile',
              'scipy': 'scipy', 'music21': 'music21', 'tinysoundfont': 'tinysoundfont',
              'PIL': 'Pillow', 'jsonschema': 'jsonschema', 'swift_f0': 'swift-f0', 'librosa': 'librosa'}
    for name, distribution in checks.items():
        try:
            module = importlib.import_module(name)
            item = {'available': True, 'version': importlib.metadata.version(distribution), 'tested': 'import'}
            if name == 'numpy':
                assert module.isfinite(module.array([1., 2.])).all()
                item['tested'] = 'array operation'
            elif name == 'nbtlib':
                assert int(module.Int(7)) == 7
                item['tested'] = 'typed NBT value'
            elif name == 'mido':
                from io import BytesIO
                from .demo import demo_midi_bytes
                assert module.MidiFile(file=BytesIO(demo_midi_bytes())).length > 0
                item['tested'] = 'original MIDI parse'
            elif name == 'soundfile':
                import numpy as np
                from io import BytesIO
                buffer = BytesIO()
                module.write(buffer, np.zeros(64), 22050, format='WAV')
                buffer.seek(0)
                assert module.read(buffer)[1] == 22050
                item['tested'] = 'WAV encode/decode'
            elif probe and name == 'music21':
                assert module.chord.Chord(['C4', 'E4', 'G4']).isMajorTriad()
                item['tested'] = 'chord analysis'
            elif probe and name == 'scipy':
                from scipy.signal import resample_poly
                assert len(resample_poly([0., 1., 0.], 2, 1)) == 6
                item['tested'] = 'sample-rate conversion'
            elif probe and name == 'tinysoundfont':
                synth = module.Synth(samplerate=22050)
                assert len(synth.generate_simple(64)) > 0
                item['tested'] = 'silent synthesis buffer (no SoundFont validated)'
            modules[name] = item
        except Exception as exc:
            modules[name] = {'available': False, 'reason': f'{type(exc).__name__}: {exc}',
                             'remedy': f'Install the relevant kit extra; distribution={distribution}'}
    commands = {'node': _command('node', ['--version'], (24, 0)),
                'ffmpeg': _command('ffmpeg', ['-version']), 'ffprobe': _command('ffprobe', ['-version']),
                'java': _command('java', ['-version'], (21, 0)),
                'fluidsynth': _command('fluidsynth', ['--version'])}
    config = load_config(project) if project else {}
    runtime = config.get('runtime', {})
    paths = {key: bool(value and Path(value).expanduser().is_file()) for key, value in runtime.items()
             if key in ('java', 'serverJar', 'traceAgent', 'clientJar', 'clientRuntime')}
    definition = {
        'midi-build': ('nbtlib', 'numpy'), 'music-edit': ('mido',), 'music-theory': ('music21',),
        'reference-audition': ('numpy', 'soundfile'), 'gm-audition-engine': ('numpy', 'soundfile', 'mido'),
        'sample-audition-and-soundpack': ('numpy', 'soundfile', 'scipy'), 'stage-preview': ('numpy', 'PIL'),
        'schema-validation': ('jsonschema',), 'pitch-assistance': ('swift_f0',), 'audio-analysis': ('librosa','soundfile')}
    items = {key: {'available': all(modules[n]['available'] for n in names), 'requires': list(names)}
             for key, names in definition.items()}
    items['midi-build']['available'] &= commands['node']['available']
    items['gm-audition-engine']['available'] &= modules['tinysoundfont']['available'] or commands['fluidsynth']['available']
    items['gm-audition-engine']['oneOf'] = ['TinySoundFont Python package', 'FluidSynth binary (PATH or explicit --fluidsynth)']
    items['gm-audition-engine']['additionalInput'] = 'A compatible, licensed SoundFont file must also be supplied and tested'
    items['media-comparison'] = {'available': commands['ffmpeg']['available'] and modules['soundfile']['available']}
    items['game-server-replay'] = {'available': False, 'configuredFiles': paths,
                                  'reason': 'Requires explicit runtime configuration and a successful actual replay; run does not probe Minecraft'}
    items['client-and-artistic-review'] = {'available': False, 'reason': 'Requires actual game output and user/model listening/viewing evidence'}
    return {'schemaVersion': 1, 'python': sys.version.split()[0], 'supportedPython': sys.version_info >= (3, 12),
            'modules': modules, 'commands': commands, 'capabilities': items,
            'resourceRoot': str(resource_root()), 'noNetworkUsed': True, 'runtimePassGranted': False}


def _json_lines(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()] if path.exists() else []


def set_brief(project, text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError('A nonempty work brief is required')
    project = Path(project).resolve(strict=True)
    with project_lock(project):
        load_config(project)
        p = owned(project, 'brief.md')
        p.write_text('# 作品需求\n\n' + text.strip() + '\n', encoding='utf-8')
    return {'brief': str(p), 'sha256': hash_file(p), 'stagePassGranted': False}


def record_decision(project, summary, reason):
    if not all(isinstance(x, str) and x.strip() for x in (summary, reason)):
        raise ValueError('Decision requires a summary and its reason')
    project = Path(project).resolve(strict=True)
    with project_lock(project):
        load_config(project)
        path = owned(project, 'decisions.jsonl')
        history = _json_lines(path)
        record = {'id': f'decision-{len(history)+1:04}', 'createdAt': time.time(), 'summary': summary, 'reason': reason}
        history.append(record)
        temporary = owned(project, '.decisions.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in history), encoding='utf-8')
        os.replace(temporary, path)
    return record


def _bind_file(project, entry):
    if not isinstance(entry, dict) or not isinstance(entry.get('path'), str):
        raise ValueError('Evidence input requires path and sha256')
    path = Path(entry['path'])
    path = (project / path).resolve() if not path.is_absolute() else path.resolve()
    if not path.is_file() or hash_file(path) != entry.get('sha256'):
        raise ValueError(f'Input/evidence absent or hash changed: {entry["path"]}')
    return {**entry, 'path': path.relative_to(project).as_posix() if path.is_relative_to(project) else str(path)}


def record_review(project, review_file):
    """Record a supplied review; it is an attributed claim, not a tool's approval."""
    project = Path(project).resolve(strict=True)
    document = read_json(review_file)
    required = {'schemaVersion', 'stage', 'scope', 'verdict', 'reviewer', 'method', 'inputs', 'summary'}
    if not isinstance(document, dict) or not required <= document.keys() or document['schemaVersion'] != 1:
        raise ValueError('Review requires schemaVersion, stage, scope, verdict, reviewer, method, inputs and summary')
    if document['stage'] not in ('music', 'sound', 'machine', 'visuals', 'capture', 'final'):
        raise ValueError('Unknown review stage')
    if document['scope'] not in ('sample', 'full') or document['verdict'] not in ('approved', 'changes_requested', 'needs_review'):
        raise ValueError('Invalid scope or verdict')
    reviewer = document['reviewer']
    if not isinstance(reviewer, dict) or reviewer.get('kind') not in ('user', 'agent', 'tool') or not reviewer.get('name'):
        raise ValueError('Reviewer requires kind=user|agent|tool and name')
    if document['method'] not in ('actual_listening', 'actual_viewing', 'actual_listening_and_viewing', 'static', 'runtime_measurement'):
        raise ValueError('Unknown review method')
    if not isinstance(document['summary'], str) or not document['summary'].strip() or not isinstance(document['inputs'], list) or not document['inputs']:
        raise ValueError('Review must bind nonempty inputs and describe findings')
    if reviewer['kind'] == 'user' and not document.get('userFeedback'):
        raise ValueError('A user-attributed review must preserve the actual supplied userFeedback')
    if document['verdict'] == 'approved' and reviewer['kind'] == 'tool' and document['method'].startswith('actual_'):
        raise ValueError('Measurement tools cannot approve actual listening/viewing')
    with project_lock(project):
        from .core import _request_signature
        config=load_config(project)
        document['inputs'] = [_bind_file(project, item) for item in document['inputs']]
        document['evidence'] = [_bind_file(project, item) for item in document.get('evidence', [])]
        document['candidateInputSignature']=_request_signature(project,config,include_artifacts=False)
        state=read_json(owned(project,'state.json'))
        relevant={'music':('music','sound'),'sound':('sound',),'machine':('machine',),
                  'visuals':('machine','visuals'),'capture':('release',),'final':('release',)}[document['stage']]
        document['candidateStages']={key:state['stages'][key]['fingerprint'] for key in relevant
            if state.get('stages',{}).get(key,{}).get('status')=='passed'}
        document.update(recordedAt=time.time(), stagePassGranted=False,
                        interpretation='Attributed review claim; verify the described method and actual feedback')
        identity = hashlib.sha256(json.dumps(document, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
        path = owned(project, f'reviews/{identity}.json')
        atomic_json(path, document)
    return {'review': str(path), 'id': identity, 'stagePassGranted': False}


def handoff(project):
    from .core import status, _request_signature
    project = Path(project).resolve(strict=True)
    state = status(project)
    config = load_config(project)
    candidate_signature=_request_signature(project,config,include_artifacts=False)
    reviews = []
    for p in sorted(owned(project, 'reviews').glob('*.json')):
        row = read_json(p)
        if not isinstance(row, dict) or 'inputs' not in row:
            continue
        try:
            for entry in row['inputs'] + row.get('evidence', []):
                _bind_file(project, entry)
            if row.get('candidateInputSignature') and row['candidateInputSignature']!=candidate_signature:
                raise ValueError('Project source inputs changed since review')
            for key,value in row.get('candidateStages',{}).items():
                current=state.get('stages',{}).get(key,{})
                if current.get('fingerprint')!=value or current.get('stale'):
                    raise ValueError('Reviewed candidate stage changed')
            row['current'] = True
        except (ValueError, OSError):
            row['current'] = False
        reviews.append({'path': p.relative_to(project).as_posix(), **row})
    incomplete = [s for s in ('music', 'sound', 'machine', 'visuals', 'validate', 'release')
                  if state.get('stages', {}).get(s, {}).get('status') != 'passed' or state.get('stages', {}).get(s, {}).get('stale')]
    next_action = ('Inspect the pending/repair task and complete its result contract' if state.get('task') else
                   'Run or repair stage: ' + incomplete[0] if incomplete else
                   'Review actual sample/full media and record user feedback; then verify capture and delivery')
    current_user_reviews = [r for r in reviews if r['current'] and r.get('reviewer', {}).get('kind') == 'user'
                            and r.get('verdict') == 'approved' and r.get('method', '').startswith('actual_')]
    music_evidence = {}
    listening_methods = {'actual_listening', 'actual_listening_and_viewing'}
    for stage in ('music', 'sound'):
        music_evidence[stage] = sorted({r['scope'] for r in current_user_reviews
                                      if r['stage'] == stage and r['method'] in listening_methods})
    result = {'schemaVersion': 1, 'project': str(project), 'title': config['title'], 'state': state,
              'reviews': reviews, 'currentUserArtisticReviews': len(current_user_reviews),
              'userApprovedListeningScopes': music_evidence,
              'decisions': _json_lines(owned(project, 'decisions.jsonl'))[-10:],
              'nextAction': next_action, 'artisticPassInferred': False}
    lines = ['# 当前交接', '', config['title'], '', f'运行状态：{state.get("status")}',
             f'下一操作：{next_action}', f'有效用户听看认可记录：{len(current_user_reviews)}',
             f'音乐母版听审：{music_evidence["music"] or "待听审"}',
             f'游戏音色听审：{music_evidence["sound"] or "待听审"}', '',
             '## 阶段', '']
    for name, row in state.get('stages', {}).items():
        lines.append(f'- {name}: {row.get("status")}; stale={row.get("stale", False)}; {row.get("artifact", row.get("error", ""))}')
    lines += ['', '## 事实边界', '', '技术构建不授予艺术认可；读取 brief.md、project.json、当前任务和 reviews/ 后继续。', '']
    owned(project, 'STATUS.md').write_text('\n'.join(lines), encoding='utf-8')
    atomic_json(owned(project, 'handoff.json'), result)
    return result


def bundle_check(root=None):
    root = Path(root).resolve() if root else resource_root()
    required = ['START_HERE.md', 'docs/WORKFLOW.md', 'docs/ENVIRONMENT.md', 'docs/TROUBLESHOOTING.md',
                'schemas/review.schema.json', 'schemas/sound-profile.schema.json', 'profiles/environment.json']
    errors = [f'Missing bundled resource: {name}' for name in required if not (root/name).is_file()]
    skills = []
    for p in sorted((root/'skills').glob('*/SKILL.md')):
        text = p.read_text(encoding='utf-8')
        match = re.search(r'^name:\s*([a-z0-9-]+)\s*$', text, re.M)
        if not text.startswith('---\n') or not match or not re.search(r'^description:', text, re.M):
            errors.append(f'Invalid skill frontmatter: {p.relative_to(root)}')
        else:
            skills.append(match.group(1))
    if len(skills) != 8:
        errors.append(f'Expected 8 project skills, found {len(skills)}')
    checked = 0
    for folder in ('skills', 'docs'):
        for p in (root/folder).rglob('*.md'):
            for _, value in re.findall(r'\[([^\]]+)\]\(([^)]+)\)', p.read_text(encoding='utf-8')):
                if value.startswith(('https:', 'http:', '#', 'mailto:')):
                    continue
                target = (p.parent/value.split('#', 1)[0]).resolve()
                if not target.exists():
                    errors.append(f'Broken link in {p.relative_to(root)}: {value}')
                checked += 1
    for p in (root/'schemas').glob('*.json'):
        try:
            read_json(p)
        except (OSError, ValueError) as exc:
            errors.append(f'Invalid schema JSON {p.name}: {exc}')
    return {'schemaVersion': 1, 'root': str(root), 'valid': not errors, 'errors': errors,
            'skills': skills, 'checkedLocalLinks': checked, 'claims': 'Bundle structure only; no artistic or runtime validation'}


def export_bundle(out, root=None):
    """Export a reviewable source kit from an explicit allowlist, never a workspace sweep."""
    root=Path(root).resolve() if root else resource_root()
    out=Path(out).resolve()
    if out.exists():
        raise ValueError('Refusing to overwrite an existing bundle directory')
    checked=bundle_check(root)
    if not checked['valid']:
        raise ValueError('Bundle resources invalid: '+str(checked['errors']))
    selected=[]
    for name in ('redstone_music','skills','schemas','profiles','templates','docs','examples','client','integrations','agents','tests','.github'):
        folder=root/name
        if folder.exists():
            for p in folder.rglob('*'):
                relative=p.relative_to(folder)
                if any(v in {'__pycache__','build','.gradle','node_modules','kit_data'} for v in relative.parts):
                    continue
                if p.is_symlink():
                    raise ValueError('Linked file cannot enter bundle: '+str(p))
                if p.is_file() and p.suffix not in ('.pyc','.log','.tmp'):
                    selected.append(p)
    for name in ('START_HERE.md','README.md','AGENTS.md','PIPELINE.md','PIPELINE_VERIFICATION.md','THIRD_PARTY.md',
                 'LICENSE','pyproject.toml','setup.py','MANIFEST.in','requirements.txt','run_pipeline.py','start_demo.cmd','.gitignore','.gitattributes'):
        if (root/name).is_file():selected.append(root/name)
    out.mkdir(parents=True)
    files={}
    for p in sorted(selected):
        target=out/p.relative_to(root)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(p,target)
        files[target.relative_to(out).as_posix()]={'sha256':hash_file(target),'bytes':target.stat().st_size}
    if not (root/'redstone_music').is_dir():
        package=Path(__file__).resolve().parent
        for p in sorted(package.rglob('*')):
            if not p.is_file() or any(v in {'kit_data','__pycache__'} for v in p.relative_to(package).parts):continue
            if p.is_symlink():raise ValueError('Linked package source cannot enter bundle')
            target=out/'redstone_music'/p.relative_to(package)
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(p,target)
            files[target.relative_to(out).as_posix()]={'sha256':hash_file(target),'bytes':target.stat().st_size}
    report={'schemaVersion':1,'files':files,'count':len(files),'artisticPassGranted':False,
            'excludes':['private projects','game binaries/assets','accounts','runtime caches','Nevada source music']}
    atomic_json(out/'bundle_manifest.json',report)
    return {'directory':str(out),'count':len(files),'manifest':str(out/'bundle_manifest.json')}
