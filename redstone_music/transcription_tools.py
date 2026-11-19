"""Local, explicit audio backends and auditable transcription candidates.

Heavy libraries run in a selected Python process so they do not change the main
production environment. No API keys, cloud calls, arbitrary commands or accepted
model licences are supplied by a project file. The default is offline.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time


BACKENDS = {
    'basic-pitch': {'distribution': 'basic-pitch', 'modules': ['basic_pitch', 'onnxruntime', 'librosa', 'pretty_midi'],
                    'purpose': 'Single-instrument polyphonic candidate; instrument identity is not detected'},
    'beat-this': {'distribution': 'beat-this', 'modules': ['beat_this', 'torch', 'torchaudio', 'soundfile'],
                  'purpose': 'Beat/downbeat timestamps, not a confirmed meter or musical score'},
    'audio-separator': {'distribution': 'audio-separator', 'modules': ['audio_separator', 'torch'],
                        'purpose': 'Audio stems; separation is not transcription and may introduce artefacts'},
    'muscriptor': {'distribution': 'muscriptor', 'modules': ['muscriptor', 'torch', 'safetensors'],
                   'purpose': 'Multi-instrument candidate; separately supplied non-commercial gated weights'},
}


def _hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def _write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False); f.write('\n')


def _read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def _python(value=None):
    executable = Path(value or sys.executable).expanduser().resolve(strict=True)
    if not executable.is_file(): raise ValueError('Explicit backend Python must be an executable file')
    return executable


def _probe():
    modules = {}
    for name in sorted({m for b in BACKENDS.values() for m in b['modules']}):
        try: modules[name] = importlib.util.find_spec(name) is not None
        except (ModuleNotFoundError, ValueError): modules[name] = False
    rows = {}
    for name, spec in BACKENDS.items():
        try: version = importlib.metadata.version(spec['distribution'])
        except importlib.metadata.PackageNotFoundError: version = None
        rows[name] = {'installed': all(modules[m] for m in spec['modules']), 'version': version,
                      'missingModules': [m for m in spec['modules'] if not modules[m]],
                      'purpose': spec['purpose'], 'inferenceVerified': False}
    return {'schemaVersion': 1, 'python': sys.version.split()[0], 'executable': sys.executable,
            'backends': rows, 'scope': 'Metadata/import-discovery only; weights and inference not verified',
            'networkUsed': False, 'artisticApproval': False}


def transcription_capabilities(python=None):
    """Check a selected environment without importing models or downloading weights."""
    command = [str(_python(python)), '-X', 'utf8', str(Path(__file__).resolve()), '--probe']
    p = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
    if p.returncode: raise ValueError('Backend environment probe failed: ' + p.stderr[-1500:])
    return json.loads(p.stdout)


def _input(source):
    from .music_tools import inspect_source
    path = Path(source).resolve(strict=True)
    info = inspect_source(path)
    with path.open('rb') as f: header=f.read(4)
    if header == b'MThd': raise ValueError('This backend requires actual audio, not MIDI')
    duration = info.get('durationSeconds')
    if duration is None:
        try: duration=float(info.get('media',{}).get('format',{}).get('duration',0))
        except (TypeError,ValueError): duration=None
    if not isinstance(duration, (int, float)) or not math.isfinite(duration) or not 0 < duration <= 900:
        raise ValueError('Audio must decode to finite duration <=900 seconds')
    return path, {'path': str(path), 'sha256': _hash(path), 'durationSeconds': duration}


def _local_model(value, label='model'):
    if not value: raise ValueError(f'An explicit local {label} file is required; no model is downloaded automatically')
    path = Path(value).expanduser().resolve(strict=True)
    if not path.is_file(): raise ValueError(f'{label} must be a local file')
    return {'path': str(path), 'sha256': _hash(path), 'bytes': path.stat().st_size}


def _execute(source, out, backend, operation, python=None, **settings):
    if backend not in BACKENDS: raise ValueError('Unknown fixed audio backend: ' + str(backend))
    executable = _python(python)
    available = transcription_capabilities(executable)['backends'][backend]
    if not available['installed']:
        raise ValueError(f"Backend {backend} unavailable in {executable}; missing {available['missingModules']}. See integrations/transcription/README.md")
    source, source_info = _input(source)
    folder = Path(out).resolve()
    if folder.exists(): raise ValueError('Backend output directory must be new')
    folder.mkdir(parents=True)
    if settings.get('allow_download') and not settings.get('model_dir'):
        settings['model_dir'] = str(folder/'models')
    request = {'schemaVersion': 1, 'operation': operation, 'backend': backend, 'source': str(source),
               'out': str(folder), 'settings': settings}
    _write(folder/'request.json', request)
    command = [str(executable), '-X', 'utf8', str(Path(__file__).resolve()), '--worker', str(folder/'request.json')]
    _write(folder/'execution.json', {'command': command, 'backendVersion': available['version'],
                                    'source': source_info, 'allowsNetwork': bool(settings.get('allow_download'))})
    env = dict(os.environ)
    env.update(PYTHONIOENCODING='utf-8', OMP_NUM_THREADS='4', MKL_NUM_THREADS='4')
    if not settings.get('allow_download'):
        env.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    if settings.get('model_dir'):
        env['TORCH_HOME'] = str(Path(settings['model_dir']).resolve())
    start = time.monotonic()
    try:
        run = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace',
                             timeout=1800, env=env)
        (folder/'stdout.log').write_text(run.stdout, encoding='utf-8')
        (folder/'stderr.log').write_text(run.stderr, encoding='utf-8')
        if run.returncode:
            problem = _read(folder/'worker_error.json') if (folder/'worker_error.json').exists() else {'message': run.stderr[-1600:]}
            raise ValueError(f"{backend} failed: {problem.get('message')}; diagnostics: {folder}")
        result = _read(folder/'worker_result.json')
        if _hash(source) != source_info['sha256']: raise ValueError('Source audio changed during inference')
        result.update(schemaVersion=1, backend=backend, backendVersion=available['version'],
                      source=source_info, processingSeconds=round(time.monotonic()-start, 3),
                      listeningVerified=False, musicalAccuracyVerified=False, artisticApproval=False,
                      timeAxis='seconds from unchanged source audio zero; not retimed to an integer BPM')
        if result.get('midi'):
            from .midi import parse_midi
            score = parse_midi(Path(result['midi']).read_bytes())
            result['candidateSha256'] = _hash(result['midi'])
            result['notes'] = [{k: n[k] for k in ('id', 'sourceTrack', 'channel', 'sourceMidi', 'sourceStartSeconds', 'sourceEndSeconds', 'velocity')} for n in score['notes']]
            result['noteCount'] = len(score['notes'])
            result['uncertainties'] = candidate_uncertainties(result['notes'], source_info['durationSeconds'])
        _write(folder/'result.json', result)
        return result
    except Exception as exc:
        if not (folder/'failure.json').exists():
            _write(folder/'failure.json', {'status': 'failed', 'backend': backend, 'message': str(exc),
                                           'source': source_info, 'inferenceCertified': False})
        raise


def transcribe_audio(source, out, backend='basic-pitch', python=None, model=None,
                     model_dir=None, allow_download=False, instruments=None):
    """Create a raw editable candidate. Gated MuScriptor models must be local."""
    if backend not in ('basic-pitch', 'muscriptor'): raise ValueError('Use basic-pitch or muscriptor for note transcription')
    if type(allow_download) is not bool: raise ValueError('allow_download must be boolean')
    if allow_download: raise ValueError('Transcription weights must be explicitly supplied or already installed; this command never accepts gated model terms')
    record = _local_model(model) if model else None
    if backend == 'muscriptor':
        if not record or Path(record['path']).suffix.lower() != '.safetensors':
            raise ValueError('MuScriptor requires an explicit local .safetensors checkpoint obtained after the operator reviews its weight licence')
    if instruments is not None and (not isinstance(instruments, list) or not instruments or
            any(not isinstance(s, str) or not re.fullmatch(r'[A-Za-z0-9 _-]{1,64}', s) for s in instruments)):
        raise ValueError('Expected a nonempty list of instrument group names')
    return _execute(source, out, backend, 'transcribe', python, model=record,
                    instruments=instruments, allow_download=False)


def track_beats(source, out, checkpoint=None, python=None, model_dir=None, allow_download=False):
    """Beat This! beat/downbeat timestamps; local checkpoint or explicit named download."""
    record = None
    if checkpoint and Path(checkpoint).expanduser().is_file(): record = _local_model(checkpoint, 'checkpoint')
    elif not (allow_download and checkpoint in ('small0', 'small1', 'small2', 'final0', 'final1', 'final2')):
        raise ValueError('Supply a local Beat This! checkpoint, or explicitly allow a published small*/final* download')
    return _execute(source, out, 'beat-this', 'beats', python, model=record, checkpoint=str(checkpoint),
                    model_dir=str(Path(model_dir).resolve()) if model_dir else None,
                    allow_download=bool(allow_download))


def separate_audio(source, out, model, model_dir, python=None, allow_download=False):
    """Run one explicitly selected audio-separator model, preserving original zero."""
    if not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9_.+ -]{1,180}', model) or model.startswith('.'):
        raise ValueError('Model must be a model filename, without path or shell syntax')
    cache = Path(model_dir).expanduser().resolve()
    if not cache.is_dir(): raise ValueError('Supply an existing model/cache directory')
    record = _local_model(cache/model) if (cache/model).is_file() else None
    if not record and not allow_download:
        raise ValueError('Separation checkpoint is missing; no model is downloaded without explicit allow_download')
    return _execute(source, out, 'audio-separator', 'separate', python, model=record, model_name=model,
                    model_dir=str(cache), allow_download=bool(allow_download))


def candidate_uncertainties(notes, duration):
    """Localize checkable risks; none of these labels is a musical error verdict."""
    risks = []
    for n in notes:
        begin, end = n['sourceStartSeconds'], n['sourceEndSeconds']
        if not 0 <= begin < end or not all(math.isfinite(v) for v in (begin, end)):
            raise ValueError('Candidate contains invalid note timing')
        if end > duration + .1:
            risks.append({'noteId': n['id'], 'timeSeconds': begin, 'kind': 'extends_beyond_source', 'reviewRequired': True})
        if end-begin < .09:
            risks.append({'noteId': n['id'], 'timeSeconds': begin, 'kind': 'short_note_or_fragment', 'reviewRequired': True})
    if notes:
        by_track = {}
        for n in notes: by_track.setdefault(n['sourceTrack'], []).append(n)
        for track, group in by_track.items():
            group.sort(key=lambda n: n['sourceStartSeconds'])
            for a, b in zip(group, group[1:]):
                if b['sourceStartSeconds'] >= a['sourceEndSeconds'] and abs(a['sourceMidi']-b['sourceMidi']) >= 12:
                    risks.append({'noteId': b['id'], 'timeSeconds': b['sourceStartSeconds'],
                                  'kind': 'large_melodic_leap_or_octave_alias', 'reviewRequired': True})
    return {'items': risks, 'counts': dict(Counter(r['kind'] for r in risks)),
            'scope': 'Candidate risks only; intentional short notes, leaps and tails are allowed',
            'instrumentAndNoteAccuracyVerified': False}


def _notes(path):
    from .midi import parse_midi
    path = Path(path).resolve(strict=True)
    with path.open('rb') as stream:
        is_midi = stream.read(4) == b'MThd'
    if is_midi:
        return path, parse_midi(path.read_bytes())['notes']
    manifest = _read(path)
    midi = manifest.get('midi') or manifest.get('candidateMidi')
    if not midi: raise ValueError('Candidate must be MIDI or a transcription result with midi')
    midi = Path(midi); midi = midi if midi.is_absolute() else path.parent/midi
    return midi.resolve(strict=True), parse_midi(midi.read_bytes())['notes']


def compare_transcriptions(reference, candidates, out, begin=0, end=None, soundfont=None,
                           gm_engine='auto', fluidsynth=None):
    """Original-vs-reconstruction audition and localized cross-candidate disputes.

    The reference is audio, not a ground-truth score. Agreement cannot be called
    transcription accuracy. Without a SoundFont the reconstruction is explicitly
    the kit's structural synthesis, not a recovered original instrument.
    """
    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly
    from .music_tools import render_preview
    ref, source = _input(reference)
    if not isinstance(candidates, (list, tuple)) or not 1 <= len(candidates) <= 6:
        raise ValueError('Supply 1–6 candidate MIDI/result files')
    if type(begin) not in (int, float) or not math.isfinite(begin) or begin < 0:
        raise ValueError('Audition begin must be finite and nonnegative')
    end = source['durationSeconds'] if end is None else end
    if type(end) not in (int, float) or not math.isfinite(end) or not begin < end <= source['durationSeconds']+.01 or end-begin > 60:
        raise ValueError('Choose a source-bound representative interval <=60 seconds')
    loaded = [_notes(p) for p in candidates]
    with sf.SoundFile(ref) as handle:
        rate = handle.samplerate
        handle.seek(round(begin*rate))
        raw = handle.read(round(end*rate)-round(begin*rate), always_2d=True, dtype='float32')
    if not raw.size or not np.isfinite(raw).all():
        raise ValueError('Reference excerpt must decode to finite audio')
    target_rate = 22050
    divisor = math.gcd(rate, target_rate)
    original = resample_poly(raw.mean(axis=1), target_rate//divisor, rate//divisor)
    folder = Path(out).resolve(); folder.mkdir(parents=True, exist_ok=False)
    original_path = folder/'original.wav'
    sf.write(original_path, original, target_rate, subtype='PCM_24')
    rows = []
    for i, (midi, notes) in enumerate(loaded):
        output = folder/f'candidate_{i+1}.wav'
        preview = render_preview(midi, output, mode='gm' if soundfont else 'reference',
                                 soundfont=soundfont, begin=begin, end=end, gm_engine=gm_engine,
                                 fluidsynth=fluidsynth, extend_interval=True)
        y, sr = sf.read(output, always_2d=True)
        if sr != target_rate:
            divisor = math.gcd(sr, target_rate); y = resample_poly(y, target_rate//divisor, sr//divisor, axis=0)
        rebuilt = y.mean(axis=1)[:len(original)] / preview['commonSafetyGain']
        rebuilt = np.pad(rebuilt, (0, max(0, len(original)-len(rebuilt))))
        stereo = np.column_stack((original, rebuilt))
        gain = min(1., .95/max(float(np.max(np.abs(stereo))), 1e-9))
        paired = folder/f'original_left_candidate_{i+1}_right.wav'
        sf.write(paired, stereo*gain, target_rate, subtype='PCM_16')
        last_note_end = max((n['sourceEndSeconds'] for n in notes), default=0.)
        rows.append({'candidate': str(midi), 'sha256': _hash(midi), 'noteCount': len(notes),
                     'onsetsInExcerpt': sum(begin <= n['sourceStartSeconds'] < end for n in notes),
                     'lastNoteEndSeconds': last_note_end,
                     'scoreMinusSourceDurationSeconds': preview['scoreDurationSeconds'] - source['durationSeconds'],
                     'excerptSecondsAfterLastNote': max(0., end-max(begin, last_note_end)),
                     'pairedAudio': str(paired), 'pairedSha256': _hash(paired),
                     'commonSafetyGain': gain, 'preview': preview,
                     'uncertainties': candidate_uncertainties(notes, source['durationSeconds'])})
    disputes = []
    if len(loaded) > 1:
        indices = []
        for _, notes in loaded:
            index = {}
            for n in notes:
                key = (n['sourceMidi'], math.floor(n['sourceStartSeconds']/.08))
                index.setdefault(key, []).append(n['sourceStartSeconds'])
            indices.append(index)
        for i, (_, notes) in enumerate(loaded):
            for n in notes:
                t = n['sourceStartSeconds']
                if not begin <= t < end: continue
                matching = []
                for j, index in enumerate(indices):
                    bucket=math.floor(t/.08)
                    if i != j and any(abs(other-t)<=.08 for k in (bucket-1,bucket,bucket+1)
                                      for other in index.get((n['sourceMidi'],k), [])): matching.append(j+1)
                if len(matching) < len(loaded)-1:
                    disputes.append({'candidate': i+1, 'noteId': n['id'], 'timeSeconds': t,
                                     'midi': n['sourceMidi'], 'matchingCandidates': matching})
    _write(folder/'disagreements.json', {'onsetToleranceSeconds': .08, 'items': disputes,
                                        'scope': 'Disagreement is a review location, not proof either candidate is wrong'})
    result = {'schemaVersion': 1, 'source': source, 'interval': {'beginSeconds': begin, 'endSeconds': end},
              'originalAudio': str(original_path), 'originalAudioSha256': _hash(original_path),
              'candidates': rows, 'disagreements': str(folder/'disagreements.json'),
              'listeningVerified': False, 'accuracyMeasured': False, 'artisticApproval': False,
              'audition': 'Left original / right reconstruction. No time warping or independent stem normalization.',
              'limitations': ['Source audio is not a ground-truth score; candidate agreement is not accuracy',
                              'Structural synthesis cannot establish original timbre or Minecraft sound']}
    _write(folder/'comparison.json', result)
    return result


def _offline_guard():
    """Do not let an upstream convenience loader silently fetch a missing model."""
    import socket
    def denied(*args, **kwargs): raise RuntimeError('Network disabled for this backend run; supply all local model/config files or explicitly allow a public download')
    socket.socket.connect = denied
    socket.socket.connect_ex = denied
    socket.create_connection = denied


def _worker(request):
    """Fixed API calls only. Kept self-contained for a separate Python environment."""
    import numpy as np
    import soundfile as sf
    backend, operation = request['backend'], request['operation']
    settings, folder = request['settings'], Path(request['out'])
    if not settings.get('allow_download'): _offline_guard()
    source = request['source']
    model = settings.get('model')
    if backend == 'basic-pitch' and operation == 'transcribe':
        import onnxruntime as ort
        from basic_pitch import ICASSP_2022_MODEL_PATH
        from basic_pitch.inference import Model, predict
        path = Path(model['path']) if model else Path(ICASSP_2022_MODEL_PATH)
        if not path.is_file(): raise ValueError('Basic Pitch model must be an installed local model file; no download attempted')
        detector = Model(path)
        if path.suffix.lower() == '.onnx':
            options = ort.SessionOptions(); options.intra_op_num_threads = 4; options.inter_op_num_threads = 1
            detector.model = ort.InferenceSession(str(path), sess_options=options, providers=['CPUExecutionProvider'])
        raw, midi, notes = predict(source, detector, onset_threshold=.5, frame_threshold=.3,
                                    minimum_note_length=80, melodia_trick=False)
        np.savez_compressed(folder/'raw_model_output.npz', **raw)
        midi.write(str(folder/'candidate.mid'))
        events = [{'startSeconds': float(s), 'endSeconds': float(e), 'midi': int(p),
                   'amplitude': float(a), 'pitchBends': [int(v) for v in bends] if bends is not None else None} for s,e,p,a,bends in notes]
        _write(folder/'raw_notes.json', {'notes': events, 'amplitudeIsConfidence': False})
        return {'midi': str(folder/'candidate.mid'), 'rawNotes': str(folder/'raw_notes.json'),
                'rawModelOutput': str(folder/'raw_model_output.npz'), 'model': _local_model(path),
                'settings': {'onsetThreshold': .5, 'frameThreshold': .3, 'minimumNoteLengthMs': 80},
                'limitations': ['Best for one instrument at a time; mixed instruments may merge or create harmonic false notes',
                                'The backend does not identify original instruments; output program is a placeholder',
                                'No quantization, octave folding or integer-BPM retiming was requested']}
    if backend == 'beat-this' and operation == 'beats':
        import torch
        from beat_this.inference import Audio2Beats
        torch.set_num_threads(4)
        path = model['path'] if model else settings['checkpoint']
        detector = Audio2Beats(checkpoint_path=path, device='cpu', dbn=False)
        audio, sr = sf.read(source, dtype='float32')
        beats, downbeats = detector(audio, sr)
        beats, downbeats = [float(v) for v in beats], [float(v) for v in downbeats]
        if any(not math.isfinite(v) or v < 0 for v in beats+downbeats): raise ValueError('Non-finite/negative beat timestamp')
        if beats != sorted(set(beats)) or downbeats != sorted(set(downbeats)): raise ValueError('Non-monotonic beat output')
        if model is None:
            path = Path(torch.hub.get_dir())/'checkpoints'/('beat_this-'+settings['checkpoint']+'.ckpt')
        _write(folder/'beats.json', {'beatsSeconds': beats, 'downbeatsSeconds': downbeats})
        return {'beatsSeconds': beats, 'downbeatsSeconds': downbeats, 'model': _local_model(path),
                'tempoCandidateBPM': float(60/np.median(np.diff(beats))) if len(beats)>1 else None,
                'raw': str(folder/'beats.json'), 'limitations': ['Beat/downbeat are candidates; verify half/double tempo and meter',
                                                               'Original audio zero is retained; no quantization or retiming']}
    if backend == 'audio-separator' and operation == 'separate':
        from audio_separator.separator import Separator
        separator = Separator(output_dir=str(folder/'stems'), model_file_dir=settings['model_dir'], output_format='WAV')
        separator.load_model(model_filename=settings['model_name'])
        files = separator.separate(source)
        original = sf.info(source)
        stems = []
        for value in files:
            p = Path(value)
            if not p.is_absolute(): p = folder/'stems'/p
            p = p.resolve(strict=True)
            if not p.is_relative_to((folder/'stems').resolve()): raise ValueError('Separation output escaped its designated directory')
            info = sf.info(p)
            stems.append({'path': str(p), 'sha256': _hash(p), 'durationSeconds': info.duration,
                          'offsetSeconds': 0., 'durationDifferenceSeconds': info.duration-original.duration})
        if not stems: raise ValueError('Separation produced no audio stems')
        return {'stems': stems, 'model': _local_model(Path(settings['model_dir'])/settings['model_name']),
                'limitations': ['Stem labels are model predictions, not verified source instruments',
                                'Source zero is retained; waveform delay and separation artefacts still require review']}
    if backend == 'muscriptor' and operation == 'transcribe':
        import dataclasses
        import torch
        from muscriptor.events import ProgressEvent
        from muscriptor.transcription_model import TranscriptionModel
        from muscriptor.utils.midi import ExportOptions
        torch.set_num_threads(4)
        detector = TranscriptionModel.load_model(weights_path=model['path'], device='cpu')
        events = [e for e in detector.transcribe(source, instruments=settings.get('instruments'),
                  use_sampling=False, batch_size=1, prelude_forcing=True) if not isinstance(e, ProgressEvent)]
        _write(folder/'raw_events.json', [{'type': type(e).__name__, **dataclasses.asdict(e)} for e in events])
        midi = detector.events_to_midi_bytes(iter(events), beat_grid=None,
                                             export=ExportOptions(quantize=False, trim_leading_bars=False, fill_gaps=0))
        (folder/'candidate.mid').write_bytes(midi)
        return {'midi': str(folder/'candidate.mid'), 'rawEvents': str(folder/'raw_events.json'), 'model': model,
                'weightLicence': 'Operator-supplied MuScriptor weights; published weights are CC BY-NC 4.0',
                'settings': {'batchSize': 1, 'preludeForcing': True, 'quantize': False},
                'limitations': ['Multi-instrument prediction is a candidate, not professional arrangement',
                                '120 BPM is only a serialization placeholder; original note seconds are preserved',
                                'No beat model, gated weights or external API were downloaded']}
    raise ValueError('Unsupported fixed worker operation')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', action='store_true'); parser.add_argument('--worker')
    args = parser.parse_args()
    if args.probe: print(json.dumps(_probe(), ensure_ascii=False))
    elif args.worker:
        req = _read(args.worker)
        try: _write(Path(req['out'])/'worker_result.json', _worker(req))
        except Exception as exc:
            _write(Path(req['out'])/'worker_error.json', {'type': type(exc).__name__, 'message': str(exc)})
            raise
