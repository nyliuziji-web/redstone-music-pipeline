"""Import an untouched MIDI master or an explicitly approved game-event baseline."""
import hashlib
import json
import math
from pathlib import Path
import shutil

from .midi import parse_midi


def _path(ctx, value):
    path = Path(value)
    return path if path.is_absolute() else Path(ctx['project']) / path


def _write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def run(ctx):
    out = Path(ctx['out'])
    out.mkdir(parents=True, exist_ok=True)
    inputs = ctx['config'].get('inputs', {})
    approved, midi = inputs.get('approvedEvents'), inputs.get('midi')
    hashes = {}
    if approved:
        source = _path(ctx, approved)
        raw = source.read_bytes()
        baseline = json.loads(raw.decode('utf-8-sig'))
        notes = baseline.get('notes')
        if not isinstance(notes, list) or not notes:
            raise ValueError('Approved events must contain a nonempty notes list')
        required = {'id', 'parentId', 'family', 'sourceMidi', 'sourceStartSeconds', 'sourceEndSeconds', 'gt', 'kind', 'instrument', 'note', 'baseBlock'}
        ids = set()
        for note in notes:
            if not required <= note.keys() or note['id'] in ids:
                raise ValueError('Invalid or duplicate approved musical event')
            ids.add(note['id'])
        duration = baseline.get('info', {}).get('excerpt', {}).get('seconds')
        duration = float(duration or max(n['sourceEndSeconds'] for n in notes))
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError('Approved baseline duration must be finite and positive')
        score = {'schemaVersion': 1, 'sourceMode': 'approved_events', 'durationSeconds': duration,
                 'ppq': None, 'tempoMap': [], 'sections': [{'name': 'SONG', 'beginGT': 0, 'endGT': max(1, math.ceil(duration * 20))}],
                 'sourceOffsetGT': baseline.get('info', {}).get('excerpt', {}).get('startGT', 0),
                 'notes': [dict(n) for n in notes if n['kind'] != 'retrigger'],
                 'sourceMidiSha256': baseline.get('info', {}).get('sourceMidiSha256'),
                 'claims': {'importedExplicitBaseline': True, 'musicalAccuracyVerified': False, 'listeningVerified': False}, 'warnings': []}
        shutil.copyfile(source, out / 'approved_events.json')
        hashes['approvedEvents'] = hashlib.sha256(raw).hexdigest()
    elif midi:
        source = _path(ctx, midi)
        raw = source.read_bytes()
        score = parse_midi(raw)
        hashes['midi'] = hashlib.sha256(raw).hexdigest()
        score.update(sourceMode='midi', sourceMidiSha256=hashes['midi'])
    else:
        raise ValueError('Music input missing: supply inputs.midi or complete the music specialist task with a MIDI master')
    if midi:
        source = _path(ctx, midi)
        raw = source.read_bytes()
        parse_midi(raw)
        digest = hashlib.sha256(raw).hexdigest()
        if approved and score.get('sourceMidiSha256') and score['sourceMidiSha256'] != digest:
            raise ValueError('Approved baseline and supplied master MIDI hash disagree')
        score['sourceMidiSha256'] = digest
        hashes['midi'] = digest
        shutil.copyfile(source, out / 'master.mid')
    _write(out / 'score.json', score)
    _write(out / 'source_hashes.json', hashes)
    return {'notes': len(score['notes']), 'durationSeconds': score['durationSeconds'],
            'sourceMode': score['sourceMode'], 'listeningVerified': False}
