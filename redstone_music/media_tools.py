"""Inspect and bind actual media; measurements never establish its artistic merits."""
import json
import math
from pathlib import Path
import shutil
import subprocess

from .core import hash_file, read_json, atomic_json


def inspect_media(source, out=None):
    source=Path(source).resolve(strict=True)
    executable=shutil.which('ffprobe')
    if not executable:raise ValueError('Media inspection requires ffprobe on PATH')
    run=subprocess.run([executable,'-v','error','-show_format','-show_streams','-of','json',str(source)],
                       capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60)
    if run.returncode:raise ValueError('ffprobe could not decode media: '+run.stderr[-1000:])
    data=json.loads(run.stdout)
    duration=float(data.get('format',{}).get('duration',0))
    if not math.isfinite(duration) or duration<=0:raise ValueError('Media has no positive finite duration')
    streams=[{k:s[k] for k in ('index','codec_type','codec_name','width','height','sample_rate','channels','avg_frame_rate','duration') if k in s}
             for s in data.get('streams',[])]
    result={'schemaVersion':1,'source':str(source),'sha256':hash_file(source),'durationSeconds':duration,
            'streams':streams,'hasVideo':any(s.get('codec_type')=='video' for s in streams),
            'hasAudio':any(s.get('codec_type')=='audio' for s in streams),
            'actualGameSourceVerified':False,'listeningVerified':False,'artisticPassGranted':False}
    if out:
        out=Path(out)
        if out.exists():raise ValueError('Refusing to overwrite media report')
        atomic_json(out,result)
    return result


def capture_evidence(project, source, out, kind='sample'):
    from .core import load_config, project_lock, status
    if kind not in ('sample','full'):raise ValueError('Capture kind must be sample or full')
    project=Path(project).resolve(strict=True)
    out=Path(out).resolve()
    if not out.is_relative_to((project/'evidence').resolve()):raise ValueError('Capture report must remain inside project/evidence')
    media=inspect_media(source)
    with project_lock(project):
        load_config(project)
        if out.exists():raise ValueError('Refusing to overwrite capture evidence')
        state=status(project)
        bindings=[]
        for stage,name in (('machine','expected_events.json'),('release','release_manifest.json')):
            row=state.get('stages',{}).get(stage,{})
            if row.get('status')=='passed' and row.get('artifact') and not row.get('stale') and row.get('artifactIntact'):
                base=Path(row['artifact'])
                base=base if base.is_absolute() else project/base
                p=base/name
                if p.is_file():bindings.append({'path':p.relative_to(project).as_posix(),'sha256':hash_file(p)})
        result={'schemaVersion':1,'kind':kind,'media':media,'candidateBindings':bindings,
                'provenance':'Operator supplied media; game origin and synchronization need actual viewing',
                'status':'media_inspected','userReview':'not_performed'}
        atomic_json(out,result)
    return result


def clip_media(source, out, begin, end):
    if not all(type(n) in (int,float) and math.isfinite(n) for n in (begin,end)) or not 0<=begin<end:
        raise ValueError('Clip requires finite 0 <= begin < end')
    source=Path(source).resolve(strict=True);out=Path(out).resolve()
    if out.exists():raise ValueError('Refusing to overwrite a media clip')
    media=inspect_media(source)
    if end>media['durationSeconds']+.05:raise ValueError('Clip exceeds source duration')
    executable=shutil.which('ffmpeg')
    if not executable:raise ValueError('Clip encoding requires ffmpeg on PATH')
    out.parent.mkdir(parents=True,exist_ok=True)
    args=[executable,'-nostdin','-n','-v','error','-i',str(source),'-ss',str(begin),'-t',str(end-begin),
          '-map','0:v:0?','-map','0:a:0?']
    if media['hasVideo']:args+=['-c:v','libx264','-pix_fmt','yuv420p','-crf','18']
    if media['hasAudio']:args+=['-c:a','pcm_s16le'] if out.suffix.lower()=='.wav' else ['-c:a','aac','-b:a','192k']
    run=subprocess.run(args+[str(out)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=300)
    if run.returncode:raise ValueError('ffmpeg clip failed: '+run.stderr[-1000:])
    report=inspect_media(out)
    report.update(sourceSha256=media['sha256'],beginSeconds=begin,endSeconds=end)
    atomic_json(out.with_suffix(out.suffix+'.json'),report)
    return report
