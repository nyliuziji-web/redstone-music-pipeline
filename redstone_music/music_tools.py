"""Professional music tools with explicit inputs, immutable candidates and honest media claims.

Optional music21, Mido, SoundFile and TinySoundFont backends are imported only by
the operation that uses them. No model, SoundFont or Minecraft asset is downloaded.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

from .midi import half_up, parse_midi


def _json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def _hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def _report(value, out):
    if out is not None:
        _write(out, value)
    return value


def _new_dir(path):
    path = Path(path).resolve()
    path.mkdir(parents=True, exist_ok=False)
    return path


def _finite(value, name, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be finite numeric data')
    if minimum is not None and value < minimum or maximum is not None and value > maximum:
        raise ValueError(f'{name} outside supported range')
    return float(value)


def _score(source):
    if isinstance(source, dict):
        value = source
    else:
        path = Path(source)
        if path.read_bytes()[:4] == b'MThd':
            value = parse_midi(path.read_bytes())
            value['sourceMidiSha256'] = _hash(path)
        else:
            value = _json(path)
    if not isinstance(value, dict) or not isinstance(value.get('notes'), list) or not value['notes']:
        raise ValueError('Expected a MIDI or score JSON with nonempty notes')
    seen = set()
    for n in value['notes']:
        if n.get('id') in seen or not isinstance(n.get('id'), str):
            raise ValueError('Score note IDs must be unique strings')
        seen.add(n['id'])
        if type(n.get('sourceMidi')) is not int or not 0 <= n['sourceMidi'] <= 127:
            raise ValueError('Invalid source MIDI pitch')
        begin = _finite(n.get('sourceStartSeconds'), 'note start', 0)
        end = _finite(n.get('sourceEndSeconds'), 'note end', 0)
        if end <= begin:
            raise ValueError('Note end must follow its start')
    return value


def inspect_source(source, out=None):
    """Inspect actual bytes and decode media; extensions alone never establish a format."""
    path = Path(source).resolve(strict=True)
    size = path.stat().st_size
    if not 0 < size <= 256 * 1024 * 1024:
        raise ValueError('Input must contain 1 byte..256 MiB')
    with path.open('rb') as stream:
        head = stream.read(64)
    result = {'schemaVersion': 1, 'source': str(path), 'sha256': _hash(path), 'bytes': size,
              'musicalAccuracyVerified': False, 'listeningVerified': False, 'warnings': []}
    if head[:4] == b'MThd':
        score = parse_midi(path.read_bytes())
        result.update(kind='midi', structurallyValid=True, notes=len(score['notes']),
                      seconds=score['durationSeconds'], ppq=score['ppq'], sections=score['sections'], warnings=score['warnings'])
    elif zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            infos = z.infolist()
            if len(infos) > 10000 or sum(i.file_size for i in infos) > 512 * 1024 * 1024:
                raise ValueError('Archive exceeds inspection budget')
            for i in infos:
                parts = i.filename.replace('\\', '/').split('/')
                if i.filename.startswith(('/', '\\')) or '..' in parts or ':' in parts[0]:
                    raise ValueError('Archive contains an unsafe path')
            bad = z.testzip()
            if bad:
                raise ValueError('Archive CRC failure: ' + bad)
            result.update(kind='zip', structurallyValid=True, entries=len(infos), rootPackMetadata='pack.mcmeta' in z.namelist())
    elif head.lstrip().lower().startswith((b'<html', b'<!doctype')):
        raise ValueError('Input contains HTML, not the requested music file')
    else:
        probe = shutil.which('ffprobe')
        if not probe:
            raise ValueError('Unknown bytes; ffprobe is required to identify audio/video')
        run = subprocess.run([probe, '-v', 'error', '-show_entries',
                              'format=duration,format_name:stream=codec_type,codec_name,sample_rate,channels', '-of', 'json', str(path)],
                             capture_output=True, text=True, timeout=30)
        if run.returncode:
            raise ValueError('Media decoding failed: ' + run.stderr[-500:])
        media = json.loads(run.stdout)
        if not media.get('streams'):
            raise ValueError('No audio or video stream was found')
        result.update(kind='media', structurallyValid=True, media=media)
    return _report(result, out)


def analyze_music(source, out=None, backend='builtin'):
    """Return measured, time-localized findings, not an artistic quality score."""
    score = _score(source)
    if backend not in ('builtin', 'music21', 'auto'):
        raise ValueError('Analysis backend must be builtin, music21 or auto')
    groups = defaultdict(list)
    for note in score['notes']:
        groups[note['family']].append(note)
    roles, findings = {}, []
    for family, notes in sorted(groups.items()):
        notes.sort(key=lambda n: (n['sourceStartSeconds'], n['id']))
        pitches = [n['sourceMidi'] for n in notes]
        roles[family] = {'notes': len(notes), 'minMidi': min(pitches), 'maxMidi': max(pitches),
                         'rangeSemitones': max(pitches) - min(pitches),
                         'longerThanOneSecond': sum(n['sourceEndSeconds'] - n['sourceStartSeconds'] > 1 for n in notes),
                         'meanVelocity': round(sum(n.get('velocity', 90) for n in notes) / len(notes), 2)}
        if max(pitches) - min(pitches) > 24 and family not in ('kick', 'snare', 'hats', 'fx'):
            findings.append({'kind': 'register-span', 'role': family, 'noteIds': [n['id'] for n in notes],
                             'message': 'Role spans more than one note-block slot; consider phrase-aware registers or a second calibrated slot.', 'evidenceType': 'measured'})
        if family in ('voice', 'theme_attack', 'answer', 'sub_bass'):
            for a, b in zip(notes, notes[1:]):
                if 0 <= b['sourceStartSeconds'] - a['sourceEndSeconds'] < .4 and abs(b['sourceMidi'] - a['sourceMidi']) > 12:
                    findings.append({'kind': 'large-leap', 'role': family, 'beginSeconds': a['sourceStartSeconds'],
                                     'endSeconds': b['sourceEndSeconds'], 'noteIds': [a['id'], b['id']],
                                     'message': 'Large adjacent leap: inspect intentional register change versus octave transcription error.', 'evidenceType': 'measured'})
    edges = []
    for n in score['notes']:
        edges.extend([(n['sourceStartSeconds'], 1), (n['sourceEndSeconds'], -1)])
    active = peak = 0
    for _, delta in sorted(edges):
        active += delta
        peak = max(peak, active)
    result = {'schemaVersion': 1, 'backend': 'builtin', 'sourceMidiSha256': score.get('sourceMidiSha256'),
              'durationSeconds': score['durationSeconds'], 'notes': len(score['notes']), 'roles': roles,
              'sections': score.get('sections', []), 'tempoMap': score.get('tempoMap', []),
              'peakPolyphony': peak, 'findings': findings, 'warnings': list(score.get('warnings', [])),
              'listeningVerified': False, 'artisticQualityScored': False}
    if backend in ('music21', 'auto'):
        try:
            import music21
        except ImportError:
            if backend == 'music21':
                raise ValueError('music21 backend unavailable; install the declared music extras in the tool environment')
            result['warnings'].append('music21 unavailable: structural analysis only')
        else:
            stream = music21.stream.Stream()
            for n in score['notes']:
                if n['family'] in ('kick', 'snare', 'hats', 'fx'):
                    continue
                obj = music21.note.Note(n['sourceMidi'])
                obj.duration.quarterLength = max(.01, n['sourceEndSeconds'] - n['sourceStartSeconds'])
                stream.insert(n['sourceStartSeconds'], obj)
            if len(stream):
                key = stream.analyze('key')
                result['tonalCandidate'] = {'key': str(key), 'correlation': float(key.correlationCoefficient),
                                            'method': 'duration-weighted key analysis; second-based offsets are used for tonal evidence only'}
            result.update(backend='music21+builtin', music21Version=music21.__version__)
    return _report(result, out)


def analyze_audio(source, out=None):
    """Use librosa for real audio evidence; tempo/chroma are candidates, not a score."""
    import numpy as np
    import soundfile as sf
    try:
        import librosa
    except ImportError as exc:
        raise ValueError('Audio analysis backend unavailable; install the declared audio extras') from exc
    path = Path(source).resolve(strict=True)
    data, rate = sf.read(path, dtype='float32', always_2d=True)
    if not data.size or len(data) > rate * 900 or not np.isfinite(data).all():
        raise ValueError('Audio must contain finite samples and be <=900 seconds')
    mono = np.mean(data, axis=1)
    y = librosa.resample(mono, orig_sr=rate, target_sr=22050) if rate != 22050 else mono
    hop = 512
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop)[0]
    onset = librosa.onset.onset_strength(y=y, sr=22050, hop_length=hop)
    tempos = librosa.feature.tempo(onset_envelope=onset, sr=22050, hop_length=hop)
    chroma = librosa.feature.chroma_stft(y=y, sr=22050, hop_length=hop)
    boundaries = librosa.onset.onset_detect(onset_envelope=onset, sr=22050, hop_length=hop, units='time')
    levels = []
    for second in range(math.ceil(len(mono) / rate)):
        window = mono[second * rate:(second + 1) * rate]
        levels.append({'beginSeconds': second, 'rmsDbFS': float(20 * np.log10(max(float(np.sqrt(np.mean(window ** 2))), 1e-12)))})
    result = {'schemaVersion': 1, 'backend': 'librosa', 'backendVersion': librosa.__version__,
              'sourceSha256': _hash(path), 'durationSeconds': len(data) / rate, 'sampleRate': rate,
              'channels': data.shape[1], 'peak': float(np.max(np.abs(data))),
              'clippedSampleFraction': float(np.mean(np.abs(data) >= .999)),
              'tempoCandidateBPM': float(tempos[0]) if len(tempos) and np.any(onset > 0) else None,
              'onsetCandidatesSeconds': [round(float(x), 5) for x in boundaries],
              'meanPitchClassEnergy': [round(float(x), 7) for x in np.mean(chroma, axis=1)],
              'oneSecondLevels': levels, 'analysisFrames': len(rms), 'listeningVerified': False,
              'artisticQualityScored': False,
              'limitations': ['Audio-derived tempo can be half/double and must not overwrite a confirmed MIDI tempo map',
                              'Pitch-class similarity does not prove correct notes, instruments or arrangement',
                              'Energy/onset features are measurements; listening and musical decisions remain separate']}
    return _report(result, out)


def transcribe_melody(source, out, fmin=46.875, fmax=2093.75, confidence=.65):
    """Local SwiftF0 single-line candidate with raw confidence evidence, no network."""
    import csv
    from dataclasses import replace
    import importlib.metadata
    import numpy as np
    import mido
    import soundfile as sf
    try:
        from swift_f0 import SwiftF0, segment_notes
    except ImportError as exc:
        raise ValueError('SwiftF0 unavailable; install the declared pitch extras') from exc
    path = Path(source).resolve(strict=True)
    fmin = _finite(fmin, 'fmin', 46.875, 2093.75)
    fmax = _finite(fmax, 'fmax', 46.875, 2093.75)
    confidence = _finite(confidence, 'confidence', 0, 1)
    if fmax <= fmin:
        raise ValueError('fmax must exceed fmin')
    data, rate = sf.read(path, dtype='float32')
    if not data.size or len(data) > rate * 900 or not np.isfinite(data).all():
        raise ValueError('Input audio must be finite and <=900 seconds')
    detector = SwiftF0(threads=2, spin=False)
    raw = detector.detect(data, rate, fmin=fmin, fmax=fmax)
    mask = (raw.confidence >= confidence) & (raw.loudness_db >= -50)
    filtered = replace(raw, confidence=np.where(mask, raw.confidence, 0))
    segments = segment_notes(filtered, pitch_hold_ms=80)
    notes = []
    for n in segments:
        if n.end - n.start < .08:
            continue
        pitch = 69 + 12 * np.log2(n.pitch_hz / 440)
        frames = (raw.timestamps >= n.start) & (raw.timestamps < n.end)
        midi = int(round(float(pitch)))
        if not 0 <= midi <= 127 or not frames.any():
            continue
        notes.append({'startSeconds': float(n.start), 'endSeconds': float(n.end), 'midi': midi,
                      'centsFromEqualTemperament': float((pitch - midi) * 100),
                      'medianConfidence': float(np.median(raw.confidence[frames]))})
    if not notes:
        raise ValueError('No confident notes detected; inspect source/voicing/range rather than claiming transcription complete')
    folder = _new_dir(out)
    with (folder / 'pitch_frames.csv').open('x', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['seconds', 'pitch_hz', 'confidence', 'loudness_db', 'accepted'])
        writer.writerows(zip(map(float, raw.timestamps), map(float, raw.pitch_hz), map(float, raw.confidence), map(float, raw.loudness_db), map(int, mask)))
    midi = mido.MidiFile(type=1, ticks_per_beat=480)
    conductor = mido.MidiTrack([mido.MetaMessage('set_tempo', tempo=500000), mido.MetaMessage('end_of_track')])
    track = mido.MidiTrack([mido.MetaMessage('track_name', name='Voice candidate'), mido.Message('program_change', channel=0, program=53)])
    midi.tracks.extend([conductor, track])
    events = []
    for i, n in enumerate(notes):
        start, end = half_up(n['startSeconds'] * 960), half_up(n['endSeconds'] * 960)
        events.extend([(start, i * 2 + 1, mido.Message('note_on', note=n['midi'], velocity=90)),
                       (max(start + 1, end), i * 2, mido.Message('note_off', note=n['midi'], velocity=0))])
    previous = 0
    for tick, _, message in sorted(events, key=lambda x: (x[0], x[1])):
        track.append(message.copy(time=tick - previous))
        previous = tick
    track.append(mido.MetaMessage('end_of_track', time=0))
    midi.save(folder / 'candidate.mid')
    parse_midi((folder / 'candidate.mid').read_bytes())
    result = {'schemaVersion': 1, 'backend': 'swift-f0', 'backendVersion': importlib.metadata.version('swift-f0'),
              'sourceSha256': _hash(path), 'candidateSha256': _hash(folder / 'candidate.mid'),
              'midi': str(folder / 'candidate.mid'), 'pitchFrames': str(folder / 'pitch_frames.csv'),
              'notes': notes, 'settings': {'fmin': fmin, 'fmax': fmax, 'confidence': confidence, 'gateDb': -50},
              'listeningVerified': False, 'polyphonicTranscription': False,
              'limitations': ['Single-line candidate only; use an isolated melody/bass where possible',
                              'Octaves, vibrato, breath, leakage and note boundaries require musical review']}
    _write(folder / 'transcription.json', result)
    return result


def _absolute_tracks(midi):
    tracks = []
    for track in midi.tracks:
        tick, events = 0, []
        for index, message in enumerate(track):
            tick += message.time
            events.append([tick, index, message.copy(time=0)])
        tracks.append(events)
    return tracks


def _time_at(score, tick):
    tempo = score['tempoMap'][0]
    for item in score['tempoMap']:
        if item['tick'] > tick:
            break
        tempo = item
    return tempo['seconds'] + (tick - tempo['tick']) * tempo['microsecondsPerQuarter'] / score['ppq'] / 1000000


def edit_music_region(source, patch, out):
    """Patch selected original note pairs while freezing all other absolute MIDI events.

    Patch: {schemaVersion:1, sourceSha256, beginSeconds, endSeconds,
      operations:[{id, pitch?, velocity?, startTick?, endTick?, remove?}],
      addNotes:[{track, channel, pitch, velocity, startTick, endTick}]}.
    endTick is physical key release (CC64 is deliberately left untouched).
    """
    import mido
    source, out = Path(source).resolve(strict=True), Path(out).resolve()
    if out.exists() or source == out:
        raise ValueError('Candidate output must be a new file')
    patch = _json(patch) if not isinstance(patch, dict) else patch
    if not isinstance(patch, dict) or patch.get('schemaVersion') != 1 or patch.get('sourceSha256') != _hash(source):
        raise ValueError('Patch version/source hash mismatch')
    begin = _finite(patch.get('beginSeconds'), 'beginSeconds', 0)
    end = _finite(patch.get('endSeconds'), 'endSeconds', 0)
    if begin >= end:
        raise ValueError('Patch interval must be nonempty')
    raw = source.read_bytes()
    score = parse_midi(raw)
    midi = mido.MidiFile(source)
    tracks = _absolute_tracks(midi)
    pairs, pending = {}, {}
    for ti, events in enumerate(tracks):
        ordinal = 0
        for item in events:
            tick, _, msg = item
            if msg.type == 'note_on' and msg.velocity:
                ident = f't{ti}n{ordinal}'
                ordinal += 1
                pending[(ti, msg.channel, msg.note)] = (ident, item)
            elif msg.type == 'note_off' or msg.type == 'note_on' and not msg.velocity:
                ident, on = pending.pop((ti, msg.channel, msg.note))
                pairs[ident] = (ti, on, item)
    notes = {n['id']: n for n in score['notes']}
    operations = patch.get('operations', [])
    if not isinstance(operations, list) or not all(isinstance(op, dict) and isinstance(op.get('id'), str) for op in operations) or len({op['id'] for op in operations}) != len(operations):
        raise ValueError('Operations require unique note IDs')
    edits, removed = [], set()
    for op in operations:
        if not isinstance(op, dict) or set(op) - {'id', 'pitch', 'velocity', 'startTick', 'endTick', 'remove'}:
            raise ValueError('Unsupported MIDI patch operation')
        if 'remove' in op and type(op['remove']) is not bool:
            raise ValueError('remove must be boolean')
        ident = op.get('id')
        if ident not in pairs:
            raise ValueError('Unknown note ID: ' + str(ident))
        n = notes[ident]
        if not begin <= n['sourceStartSeconds'] or n['sourceEndSeconds'] > end + 1e-9:
            raise ValueError('Edit would touch a note outside the declared region')
        ti, on, off = pairs[ident]
        if op.get('remove'):
            removed.update([(ti, on[1]), (ti, off[1])])
        else:
            for field, lo, hi in [('pitch', 0, 127), ('velocity', 1, 127)]:
                if field in op and (type(op[field]) is not int or not lo <= op[field] <= hi):
                    raise ValueError('Invalid note ' + field)
            start_tick, end_tick = op.get('startTick', on[0]), op.get('endTick', off[0])
            if type(start_tick) is not int or type(end_tick) is not int or end_tick <= start_tick:
                raise ValueError('Invalid note ticks')
            if _time_at(score, start_tick) < begin - 1e-9 or _time_at(score, end_tick) > end + 1e-9:
                raise ValueError('Edited note would escape declared interval')
            on[0], off[0] = start_tick, end_tick
            on[2] = on[2].copy(note=op.get('pitch', on[2].note), velocity=op.get('velocity', on[2].velocity))
            off[2] = off[2].copy(note=op.get('pitch', off[2].note))
        edits.append(ident)
    additions = patch.get('addNotes', [])
    if not isinstance(additions, list):
        raise ValueError('addNotes must be an array')
    for add in additions:
        if not isinstance(add, dict) or set(add) != {'track', 'channel', 'pitch', 'velocity', 'startTick', 'endTick'}:
            raise ValueError('Added note fields are incomplete or unsupported')
        ti, ch, pitch, velocity, start_tick, end_tick = (add[k] for k in ('track', 'channel', 'pitch', 'velocity', 'startTick', 'endTick'))
        if any(type(v) is not int for v in (ti, ch, pitch, velocity, start_tick, end_tick)) or not 0 <= ti < len(tracks) or not 0 <= ch < 16 or not 0 <= pitch < 128 or not 1 <= velocity < 128 or end_tick <= start_tick:
            raise ValueError('Invalid added note')
        if _time_at(score, start_tick) < begin - 1e-9 or _time_at(score, end_tick) > end + 1e-9:
            raise ValueError('Added note would escape interval')
        serial = len(tracks[ti]) + 1
        tracks[ti].extend([[start_tick, serial, mido.Message('note_on', channel=ch, note=pitch, velocity=velocity)],
                           [end_tick, serial + 1, mido.Message('note_off', channel=ch, note=pitch, velocity=0)]])
    changed_midi = mido.MidiFile(type=midi.type, ticks_per_beat=midi.ticks_per_beat)
    for ti, events in enumerate(tracks):
        track, previous = mido.MidiTrack(), 0
        for tick, serial, message in sorted(events, key=lambda e: (e[0], e[1])):
            if (ti, serial) in removed or message.type == 'end_of_track':
                continue
            track.append(message.copy(time=tick - previous))
            previous = tick
        # Preserve the original track duration even if a final note is removed.
        final_tick = max(max((e[0] for e in events), default=0), previous)
        track.append(mido.MetaMessage('end_of_track', time=final_tick - previous))
        changed_midi.tracks.append(track)
    import io
    buffer = io.BytesIO()
    changed_midi.save(file=buffer)
    candidate = buffer.getvalue()
    after = parse_midi(candidate)
    if after['tempoMap'] != score['tempoMap']:
        raise ValueError('Patch changed the tempo map')
    original_controls = [[(t, m.bytes()) for t, _, m in ev if m.type not in ('note_on', 'note_off', 'end_of_track')] for ev in _absolute_tracks(midi)]
    new_controls = [[(t, m.bytes()) for t, _, m in ev if m.type not in ('note_on', 'note_off', 'end_of_track')] for ev in _absolute_tracks(changed_midi)]
    if original_controls != new_controls:
        raise ValueError('Patch changed a frozen control/meta event')
    def outside(s):
        return sorted((n['sourceTrack'], n['channel'], n['sourceMidi'], n['startTick'], n['keyReleaseTick'], n['endTick'], n['velocity'])
                      for n in s['notes'] if n['sourceStartSeconds'] < begin or n['sourceEndSeconds'] > end + 1e-9)
    if outside(score) != outside(after):
        raise ValueError('Patch changed notes outside its region, including pedal-held notes')
    if source.read_bytes() != raw:
        raise ValueError('Source changed while applying patch')
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('xb') as stream:
        stream.write(candidate)
    return {'schemaVersion': 1, 'sourceSha256': hashlib.sha256(raw).hexdigest(), 'candidateSha256': _hash(out),
            'output': str(out), 'editedSourceIds': edits, 'addedNotes': len(patch.get('addNotes', [])),
            'frozenControlsPreserved': True, 'outsideRegionPreserved': True, 'listeningVerified': False}


def _profile(value):
    root = Path.cwd()
    if isinstance(value, (str, Path)):
        p = Path(value).resolve(strict=True)
        root, value = p.parent, _json(p)
    if not isinstance(value, dict) or value.get('schemaVersion') != 1 or not isinstance(value.get('slots'), dict) or not value['slots']:
        raise ValueError('Sound profile requires schemaVersion 1 and nonempty slots')
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,47}', value.get('id', '')):
        raise ValueError('Profile id must be a short namespaced identifier')
    from .sound import _validate_event
    instruments = {}
    declared={}
    for key,slot in value['slots'].items():
        if not isinstance(slot,dict):raise ValueError('Every sound slot must be an object')
        instrument=slot.get('instrument')
        if instrument in declared:
            raise ValueError(f'Slots {declared[instrument]} and {key} share vanilla event {instrument}; give independently controlled sounds separate instruments')
        declared[instrument]=key
    for key, slot in value['slots'].items():
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,47}', key):
            raise ValueError('Invalid slot name')
        if type(slot.get('rootMidi')) is not int or not 12 <= slot['rootMidi'] <= 115:
            raise ValueError('Slot rootMidi must be an integer in 12..115')
        _validate_event({'gt': 0, 'note': 12, 'kind': 'onset', 'sourceStartSeconds': 0, 'sourceEndSeconds': 1,
                         'id': 'probe', 'parentId': 'probe', 'sourceMidi': 60, 'instrument': slot.get('instrument'), 'baseBlock': slot.get('baseBlock', '')})
        from .sound import TONAL, DRUMS
        stable_bases={name:base for name,_,base in TONAL}
        stable_bases.update({name:base for name,base,_ in DRUMS.values()})
        stable_bases.update(chime='minecraft:packed_ice',xylophone='minecraft:bone_block',
                            cow_bell='minecraft:soul_sand',didgeridoo='minecraft:pumpkin',pling='minecraft:glowstone')
        if slot['baseBlock'] != stable_bases[slot['instrument']]:
            raise ValueError(f"Slot {key} instrument/baseBlock mismatch; use stable base {stable_bases[slot['instrument']]}")
        identity = slot.get('sample') or slot.get('source') or json.dumps(slot.get('synthesis', {}), sort_keys=True)
        old = instruments.setdefault(slot['instrument'], (key, identity))
        if old[0] != key:
            raise ValueError(f'Slots {old[0]} and {key} share vanilla event {slot["instrument"]}; give independently controlled sounds separate instruments')
        _finite(slot.get('gain', 1), 'slot gain', 0, 4)
        sustain = slot.get('sustain', {'mode': 'natural'})
        if sustain.get('mode') not in ('natural', 'retrigger'):
            raise ValueError('Sustain mode must be natural or retrigger')
        if sustain['mode'] == 'retrigger' and (type(sustain.get('stepGT')) is not int or not 1 <= sustain['stepGT'] <= 200):
            raise ValueError('Retrigger needs explicit stepGT in 1..200')
    roles = value.get('roles', {})
    if not isinstance(roles, dict) or any(slot not in value['slots'] for slot in roles.values()):
        raise ValueError('Role mapping refers to an unknown slot')
    return value, root


def validate_sound_profile(profile, require_samples=True):
    """Validate a profile and, normally, every declared sample's existence/hash."""
    value, root = _profile(profile)
    for key, slot in value['slots'].items():
        if require_samples:
            if not isinstance(slot.get('sample'), str) or not slot['sample']:
                raise ValueError('Calibrated sound profile lacks sample for slot ' + key)
            sample = Path(slot['sample'])
            sample = sample if sample.is_absolute() else root / sample
            if not sample.is_file():
                raise ValueError('Profile sample is missing: ' + key)
            if slot.get('sampleSha256') and slot['sampleSha256'] != _hash(sample):
                raise ValueError('Profile sample hash mismatch: ' + key)
    return value


def sound_profile_dependencies(profile):
    """Return all concrete read dependencies for conductor fingerprints."""
    path = Path(profile).resolve(strict=True)
    value, root = _profile(path)
    result = [path]
    for slot in value['slots'].values():
        for name in ('sample', 'source'):
            if slot.get(name):
                p = Path(slot[name])
                result.append((p if p.is_absolute() else root / p).resolve(strict=True))
    return sorted(set(result))


def validate_soundpack(soundpack, profile):
    """Check declared event/sample links and byte identity with a calibrated profile."""
    value, root = _profile(profile)
    validate_sound_profile(profile)
    with zipfile.ZipFile(soundpack) as z:
        if len(z.infolist()) > 10000 or sum(i.file_size for i in z.infolist()) > 256 * 1024 * 1024:
            raise ValueError('Sound resource pack exceeds validation budget')
        for info in z.infolist():
            parts = info.filename.replace('\\', '/').split('/')
            if info.filename.startswith(('/', '\\')) or '..' in parts or ':' in parts[0]:
                raise ValueError('Unsafe sound resource path')
        if z.testzip() is not None:
            raise ValueError('Sound resource pack CRC failure')
        meta = json.loads(z.read('pack.mcmeta'))
        if meta.get('pack', {}).get('pack_format') != 34:
            raise ValueError('Sound profile requires Minecraft 1.21.1 resource pack format 34')
        sounds = json.loads(z.read('assets/minecraft/sounds.json'))
        for slot_id, slot in value['slots'].items():
            event = sounds.get('block.note_block.' + slot['instrument'], {})
            entries = event.get('sounds', [])
            if event.get('replace') is not True or len(entries) != 1:
                raise ValueError('Sound event must replace one declared calibrated sample')
            entry = entries[0] if isinstance(entries[0], dict) else {'name': entries[0]}
            if entry.get('pitch', 1) != 1 or entry.get('volume', 1) != 1:
                raise ValueError('Unexpected event pitch/gain outside calibrated profile')
            name = entry.get('name', '')
            if name != value['id'] + ':' + slot_id:
                raise ValueError('Sound event sample name disagrees with profile')
            content = z.read(f'assets/{value["id"]}/sounds/{slot_id}.ogg')
            sample = Path(slot['sample'])
            sample = sample if sample.is_absolute() else root / sample
            if content != sample.read_bytes():
                raise ValueError('Sound pack sample bytes disagree with calibrated profile')
    return {'schemaVersion': 1, 'profileId': value['id'], 'eventsVerified': len(value['slots']),
            'sha256': _hash(soundpack), 'clientVerified': False}


def plan_noteblocks(source, out=None, profile=None, adaptation_plan=None, consistency='role'):
    """Plan one calibrated timbre per role/phrase, never silently fold each note."""
    from .sound import TONAL, DRUMS, PREFER
    if consistency not in ('role','phrase'):
        raise ValueError('consistency must be role or phrase; per-note timbre fallback is not supported')
    score = _score(source)
    if profile is None:
        value = {'schemaVersion': 1, 'id': 'vanilla', 'roles': {}, 'slots': {i: {'instrument': i, 'baseBlock': b, 'rootMidi': low + 12, 'gain': 1, 'sustain': {'mode': 'natural'}} for i, low, b in TONAL}}
        for family, (instrument, base, note) in DRUMS.items():
            value['slots'].setdefault(instrument, {'instrument': instrument, 'baseBlock': base, 'rootMidi': 66, 'gain': 1, 'sustain': {'mode': 'natural'}})
            value['roles'][family] = instrument
        value['_builtinVanillaTuning']={family:note for family,(_,_,note) in DRUMS.items()}
        root = Path.cwd()
    else:
        value, root = _profile(profile)
    groups, candidates, decisions = defaultdict(list), [], []
    for n in score['notes']:
        groups[n['family']].append(n)
    if adaptation_plan is not None:
        candidates = [{**n, 'gt': half_up(n['sourceStartSeconds'] * 20),
                       'phase': half_up(n['sourceStartSeconds'] * 20) % 2, 'kind': 'onset'} for n in score['notes']]
    for family, all_notes in (sorted(groups.items()) if adaptation_plan is None else []):
        all_notes.sort(key=lambda n: (n['sourceStartSeconds'], n['id']))
        # A short rest is not evidence that the melodic instrument should change.
        # Default to one identity and register for the complete role. Explicit
        # phrase mode remains available for deliberately reviewed orchestration.
        phrases = [all_notes] if consistency == 'role' else []
        if consistency == 'phrase':
            for n in all_notes:
                if not phrases or n['sourceStartSeconds'] - max(x['sourceEndSeconds'] for x in phrases[-1]) > .4:
                    phrases.append([])
                phrases[-1].append(n)
        for pi, notes in enumerate(phrases):
            is_drum = family in DRUMS
            fixed = value.get('roles', {}).get(family)
            choices = [fixed] if fixed else [s for s in value['slots'] if value['slots'][s]['instrument'] not in ('basedrum', 'snare', 'hat')]
            possible = []
            for slot_id in choices:
                slot = value['slots'][slot_id]
                for shift in ([0] if is_drum else range(-120, 121, 12)):
                    if is_drum or all(0 <= n['sourceMidi'] + shift - slot['rootMidi'] + 12 <= 24 for n in notes):
                        possible.append((abs(shift), slot['instrument'] != PREFER.get(family, 'harp'), slot_id, shift))
            if not possible:
                low=min(n['sourceMidi'] for n in notes); high=max(n['sourceMidi'] for n in notes)
                root=max(12,min(115,half_up((low+high)/2)))
                remedy=(f'create a calibrated sample with rootMidi={root} (25-key window {root-12}..{root+12})'
                        if high-low<=24 else 'design explicit sample zones or revoice the role; one slot spans only 24 semitones')
                raise ValueError(f'{consistency.capitalize()} {family}/{pi}, MIDI {low}..{high}, cannot fit one consistent slot; {remedy}. '
                                 'Do not fold individual source notes or alternate instruments to hide the range problem')
            _, _, slot_id, shift = min(possible)
            slot = value['slots'][slot_id]
            decisions.append({'role': family, 'phrase': pi, 'slot': slot_id, 'transpose': shift, 'noteIds': [n['id'] for n in notes],
                              'beginSeconds': notes[0]['sourceStartSeconds'], 'endSeconds': max(n['sourceEndSeconds'] for n in notes)})
            for n in notes:
                gt = half_up(n['sourceStartSeconds'] * 20)
                tuning = (DRUMS[family][2] if profile is None else 12) if is_drum else n['sourceMidi'] + shift - slot['rootMidi'] + 12
                event = {**n, 'gt': gt, 'phase': gt % 2, 'kind': 'onset', 'slot': slot_id, 'note': tuning,
                         'instrument': slot['instrument'], 'baseBlock': slot['baseBlock'], 'transpose': shift,
                         'mappedMidi': n['sourceMidi'] + shift, 'gainProxy': n.get('velocity', 90) / 127,
                         'approximation': 'percussion sample approximation' if is_drum else 'phrase octave transpose' if shift else None}
                candidates.append(event)
                sustain = slot.get('sustain', {'mode': 'natural'})
                if sustain['mode'] == 'retrigger' and not is_drum:
                    for i, t in enumerate(range(gt + sustain['stepGT'], half_up(n['sourceEndSeconds'] * 20) - 1, sustain['stepGT']), 1):
                        candidates.append({**event, 'id': n['id'] + '_r' + str(i), 'kind': 'retrigger', 'gt': t, 'phase': t % 2})
    candidates.sort(key=lambda n: (n['gt'], n['id']))
    result = {'schemaVersion': 1, 'sourceMidiSha256': score.get('sourceMidiSha256'), 'durationSeconds': score['durationSeconds'],
              'sourceOffsetGT': score.get('sourceOffsetGT',0), 'musicGT': math.ceil(score['durationSeconds'] * 20), 'candidates': candidates, 'merged': [],
              'profileId': value['id'], 'phraseDecisions': decisions, 'listeningVerified': False,
              'sections': score.get('sections',[]),
              'consistency':consistency,
              'limitations': ['MIDI note-off and velocity do not directly control vanilla sample playback',
                              'Phrase consistency and measurements do not establish artistic quality']}
    if adaptation_plan is not None:
        result = apply_adaptation_plan(result, adaptation_plan, value)
    cut=result['sourceOffsetGT']
    for n in result['candidates']:
        if cut:n['q']=n['gt']-cut
    result['musicGT']=max(result['musicGT'],max((n['gt']-cut+1 for n in result['candidates']),default=1))
    if out is not None:
        folder = _new_dir(out)
        _write(folder / 'events.json', result)
        _write(folder / 'adaptation_plan.json', {'schemaVersion': 1, 'profileId': value['id'], 'sourceMidiSha256': score.get('sourceMidiSha256'), 'decisions': result['phraseDecisions'],
                                               'listeningVerified': False, 'limitations': result['limitations']})
        result = {**result, 'eventsPath': str(folder / 'events.json'), 'planPath': str(folder / 'adaptation_plan.json')}
    return result


def apply_adaptation_plan(planned, adaptation_plan, profile):
    """Apply complete explicit phrase decisions, rejecting omitted/duplicate source notes."""
    plan = _json(adaptation_plan) if not isinstance(adaptation_plan, dict) else adaptation_plan
    if not isinstance(plan, dict) or plan.get('schemaVersion') != 1 or plan.get('profileId') != profile['id']:
        raise ValueError('Adaptation plan version/profile mismatch')
    if plan.get('sourceMidiSha256') and plan['sourceMidiSha256'] != planned.get('sourceMidiSha256'):
        raise ValueError('Adaptation plan source hash mismatch')
    decisions = plan.get('decisions')
    if not isinstance(decisions, list) or not decisions:
        raise ValueError('Adaptation plan needs nonempty decisions')
    from .sound import DRUMS
    original = {n['id']: n for n in planned['candidates'] if n['kind'] == 'onset'}
    seen, events = set(), []
    for decision in decisions:
        if not isinstance(decision, dict):
            raise ValueError('Adaptation decision must be an object')
        ids, role, slot_id, shift = decision.get('noteIds'), decision.get('role'), decision.get('slot'), decision.get('transpose', 0)
        if not isinstance(ids, list) or not ids or type(shift) is not int or shift % 12:
            raise ValueError('Adaptation needs nonempty noteIds and an explicit whole-phrase octave shift')
        if slot_id not in profile['slots']:
            raise ValueError('Adaptation refers to unknown sample slot')
        slot = profile['slots'][slot_id]
        for ident in ids:
            if ident in seen or ident not in original:
                raise ValueError('Adaptation note IDs are duplicate or unknown')
            seen.add(ident)
            note = original[ident]
            if note['family'] != role:
                raise ValueError('Adaptation role disagrees with source note')
            tuning = profile.get('_builtinVanillaTuning',{}).get(role,12) if role in DRUMS else note['sourceMidi'] + shift - slot['rootMidi'] + 12
            if not 0 <= tuning <= 24:
                raise ValueError('Adaptation choice puts source pitch outside calibrated slot')
            event = {**note, 'slot': slot_id, 'transpose': shift, 'mappedMidi': note['sourceMidi'] + shift,
                     'note': tuning, 'instrument': slot['instrument'], 'baseBlock': slot['baseBlock'],
                     'approximation': 'explicit percussion adaptation' if role in DRUMS else 'explicit phrase octave transpose' if shift else None}
            events.append(event)
            sustain = slot.get('sustain', {'mode': 'natural'})
            if sustain['mode'] == 'retrigger' and role not in DRUMS:
                for i, gt in enumerate(range(event['gt'] + sustain['stepGT'], half_up(event['sourceEndSeconds'] * 20) - 1, sustain['stepGT']), 1):
                    events.append({**event, 'id': ident + '_r' + str(i), 'kind': 'retrigger', 'gt': gt, 'phase': gt % 2})
    if seen != original.keys():
        raise ValueError('Adaptation plan must account for every source onset exactly once')
    return {**planned, 'candidates': sorted(events, key=lambda n: (n['gt'], n['id'])),
            'phraseDecisions': decisions, 'explicitAdaptationApplied': True}


def _synthesize(spec, root_midi, rate, seed, max_seconds=10):
    import numpy as np
    seconds = _finite(spec.get('seconds', 1), 'synthesis seconds', .005, max_seconds)
    gain = _finite(spec.get('gain', .3), 'synthesis gain', 0, .9)
    kind = spec.get('kind', 'pluck')
    if kind not in ('pluck', 'sustain', 'bass', 'kick', 'snare', 'hat'):
        raise ValueError('Unknown original synthesis kind')
    t = np.arange(round(seconds * rate)) / rate
    freq = 440 * 2 ** ((root_midi - 69) / 12)
    rng = np.random.default_rng(seed)
    if kind == 'kick':
        x = np.sin(2 * np.pi * (48 * t + 14 * (1 - np.exp(-t * 26)))) * np.exp(-t * 15)
    elif kind in ('snare', 'hat'):
        noise = rng.normal(0, .22, len(t))
        x = np.r_[0, np.diff(noise)] * np.exp(-t * (25 if kind == 'hat' else 15))
        if kind == 'snare':
            x += .22 * np.sin(2 * np.pi * 180 * t) * np.exp(-t * 20)
    else:
        x = np.sin(2 * np.pi * freq * t) + .22 * np.sin(2 * np.pi * freq * 2 * t) + .08 * np.sin(2 * np.pi * freq * 3 * t)
        x *= np.exp(-t * (5 if kind == 'pluck' else 2 if kind == 'bass' else .4))
    attack = np.minimum(1, t / (.025 if kind == 'sustain' else .004))
    release = np.minimum(1, np.maximum(0, seconds - t) / .025)
    x *= attack * release
    peak = max(float(np.max(np.abs(x))), 1e-12)
    return (x * gain / peak).astype(np.float32)


def calibrate_sound_profile(profile, out=None):
    """Measure sample spectra and flag reference-pitch mismatches for review.

    A spectral peak is deliberately labeled a candidate: formants and overtone-
    dominant samples still need a second pitch estimator or actual listening.
    """
    import numpy as np
    import soundfile as sf
    value, root = _profile(profile)
    validate_sound_profile(profile)
    rows, findings = [], []
    for key, slot in value['slots'].items():
        path = Path(slot['sample'])
        path = path if path.is_absolute() else root / path
        data, rate = sf.read(path, dtype='float32')
        if data.ndim != 1 or not len(data) or not np.isfinite(data).all():
            raise ValueError('Calibration requires finite mono samples')
        row = {'slot': key, 'sampleSha256': _hash(path), 'declaredRootMidi': slot['rootMidi'],
               'seconds': len(data) / rate, 'peak': float(np.max(np.abs(data))),
               'rms': float(np.sqrt(np.mean(data ** 2)))}
        if slot['instrument'] not in ('basedrum', 'snare', 'hat') and len(data) >= 256 and row['rms'] > 1e-5:
            frame = data[:min(len(data), rate * 2)]
            nfft = 2 ** math.ceil(math.log2(len(frame) * 4))
            spectrum = np.abs(np.fft.rfft(frame * np.hanning(len(frame)), n=nfft))
            low = max(1, int(15 / rate * nfft))
            high = min(len(spectrum) - 1, int(10000 / rate * nfft))
            peak_bin = low + int(np.argmax(spectrum[low:high]))
            values = np.log(spectrum[peak_bin - 1:peak_bin + 2] + 1e-20)
            denominator = values[0] - 2 * values[1] + values[2]
            offset = .5 * (values[0] - values[2]) / denominator if abs(denominator) > 1e-12 else 0
            frequency = (peak_bin + float(offset)) * rate / nfft
            midi = 69 + 12 * math.log2(frequency / 440)
            cents = (midi - slot['rootMidi']) * 100
            row.update(spectralPitchCandidateHz=frequency, spectralPitchCandidateMidi=midi,
                       centsFromDeclaredRoot=cents, pitchMethod='windowed spectral peak with interpolation')
            if abs(cents) > 70:
                findings.append({'slot': key, 'kind': 'root-pitch-candidate-mismatch', 'cents': cents,
                                 'evidenceType': 'measured-candidate', 'message': 'Inspect root pitch versus overtone/formant dominance before using this profile.'})
        rows.append(row)
    return _report({'schemaVersion': 1, 'profileId': value['id'], 'slots': rows, 'findings': findings,
                    'clientVerified': False, 'listeningVerified': False,
                    'limitations': ['Spectral-peak pitch is an estimate, not proof of a sample fundamental',
                                    'Low/middle/high note playback and game recording still require verification']}, out)


def build_soundpack(spec, out):
    """Create a calibrated vanilla replacement pack from user samples or original synthesis."""
    import numpy as np
    import soundfile as sf
    value, source_root = _profile(spec)
    folder = _new_dir(out)
    samples = folder / 'samples'
    samples.mkdir()
    profile = json.loads(json.dumps(value))
    sounds, rows = {}, []
    with zipfile.ZipFile(folder / 'resources.zip', 'x', zipfile.ZIP_DEFLATED) as z:
        z.writestr('pack.mcmeta', json.dumps({'pack': {'pack_format': 34, 'description': value.get('description', value['id'])}}, ensure_ascii=False))
        for key, slot in profile['slots'].items():
            rate = 22050
            if 'synthesis' in slot:
                data = _synthesize(slot['synthesis'], slot['rootMidi'], rate, int.from_bytes(hashlib.sha256(key.encode()).digest()[:4], 'big'))
                provenance = {'method': 'original procedural synthesis', 'license': 'CC0-1.0'}
            else:
                source = Path(slot.get('source', slot.get('sample', '')))
                if not source.is_absolute():
                    source = source_root / source
                if not source.is_file():
                    raise ValueError('Missing sample for slot ' + key)
                data, rate = sf.read(source, dtype='float32')
                provenance = {'method': 'user-provided sample', 'sourceSha256': _hash(source), 'license': slot.get('license', 'unspecified-user-source')}
            if data.ndim != 1 or not 8000 <= rate <= 96000 or not 0 < len(data) <= rate * 30 or not np.isfinite(data).all():
                raise ValueError('Samples must be finite mono audio, <=30 seconds, 8..96 kHz')
            data = data * slot.get('gain', 1)
            if float(np.max(np.abs(data))) > .999:
                raise ValueError('Sample gain clips; revise the source/gain before packing')
            path = samples / (key + '.ogg')
            sf.write(path, data, rate, format='OGG', subtype='VORBIS')
            decoded, actual_rate = sf.read(path, dtype='float32')
            if not np.isfinite(decoded).all() or actual_rate != rate or decoded.ndim != 1:
                raise ValueError('Encoded sample failed decoding')
            slot.pop('source', None)
            slot.pop('synthesis', None)
            slot.update(sample='samples/' + key + '.ogg', gain=1, sampleSha256=_hash(path), provenance=provenance)
            archive_path = f'assets/{value["id"]}/sounds/{key}.ogg'
            z.write(path, archive_path)
            sounds['block.note_block.' + slot['instrument']] = {'replace': True, 'sounds': [{'name': value['id'] + ':' + key, 'stream': False}]}
            rows.append({'slot': key, 'instrument': slot['instrument'], 'baseBlock': slot['baseBlock'], 'rootMidi': slot['rootMidi'],
                         'rootFrequencyHz': 440 * 2 ** ((slot['rootMidi'] - 69) / 12), 'seconds': len(decoded) / rate,
                         'sampleRate': rate, 'channels': 1, 'peak': float(np.max(np.abs(decoded))),
                         'rms': float(np.sqrt(np.mean(decoded ** 2))), 'sha256': _hash(path), 'provenance': provenance,
                         'pitchAtNotes': {str(n): slot['rootMidi'] + n - 12 for n in (0, 12, 24)},
                         'durationAtNotesSeconds': {str(n): len(decoded) / rate / 2 ** ((n - 12) / 12) for n in (0, 12, 24)},
                         'pitchVerification': 'synthesis design or supplied rootMidi; actual client frequency not yet measured'})
        z.writestr('assets/minecraft/sounds.json', json.dumps(sounds, ensure_ascii=False, indent=2))
    profile['resourcePackSha256'] = _hash(folder / 'resources.zip')
    _write(folder / 'profile.json', profile)
    pitch_report = calibrate_sound_profile(folder / 'profile.json')
    report = {'schemaVersion': 1, 'profileId': value['id'], 'slots': rows, 'soundEvents': list(sounds),
              'resourcesSha256': profile['resourcePackSha256'], 'decodedAllSamples': True, 'sharedSlotConflicts': [],
              'measuredPitchCandidates': pitch_report['slots'], 'pitchFindings': pitch_report['findings'],
              'clientVerified': False, 'listeningVerified': False}
    _write(folder / 'calibration.json', report)
    return {'schemaVersion': 1, 'profile': str(folder / 'profile.json'), 'soundPack': str(folder / 'resources.zip'),
            'calibration': str(folder / 'calibration.json'), 'slots': len(rows), 'clientVerified': False, 'listeningVerified': False}


def render_preview(source, out, mode='reference', soundfont=None, profile=None, begin=0, end=None,
                   gm_engine='auto', fluidsynth=None, extend_interval=False):
    """Render honest audition media. Reference synth is original, never called Minecraft audio."""
    import numpy as np
    import soundfile as sf
    out = Path(out).resolve()
    if out.exists() or out.with_suffix(out.suffix + '.json').exists():
        raise ValueError('Preview output must be new')
    if mode not in ('reference', 'gm', 'noteblock'):
        raise ValueError('Preview mode must be reference, gm or noteblock')
    begin = _finite(begin, 'begin', 0)
    rate, tail = 22050, 1.0
    if mode == 'noteblock':
        events = _json(source) if not isinstance(source, dict) else source
        notes = events.get('candidates', events.get('notes'))
        if not isinstance(notes, list) or not notes:
            raise ValueError('Note-block preview requires planned events')
        value, base = _profile(profile)
        duration = float(events['durationSeconds'])
    else:
        score = _score(source)
        notes, duration = score['notes'], float(score['durationSeconds'])
    end = duration if end is None else _finite(end, 'end', 0)
    if end <= begin or (end > duration + .001 and not extend_interval) or end > 900:
        raise ValueError('Invalid preview interval or >900 second preview')
    # Render from zero including pre-roll history before cropping. This preserves
    # notes and sample tails already sounding when a requested excerpt begins.
    audio = np.zeros((round((end + tail) * rate), 2), dtype=np.float32)
    if mode == 'gm':
        if not soundfont or not Path(soundfont).is_file() or not isinstance(source, (str, Path)):
            raise ValueError('GM preview needs a real MIDI path and supplied SoundFont')
        from .renderers import gm_buffer
        audio,renderer = gm_buffer(source,soundfont,rate,end,tail,gm_engine,fluidsynth)
    else:
        cache = {}
        for n in notes:
            start = n.get('q', n.get('gt', 0)) / 20 if mode == 'noteblock' else n['sourceStartSeconds']
            if start < 0 or not math.isfinite(start):
                raise ValueError('Preview event time must be finite and nonnegative')
            if start >= end:
                continue
            if mode == 'noteblock':
                if type(n.get('note')) is not int or not 0 <= n['note'] <= 24:
                    raise ValueError('Note-block tuning must be an integer in 0..24')
                slot_id = n.get('slot', value.get('roles', {}).get(n['family']))
                if slot_id not in value['slots']:
                    raise ValueError('No explicit sample slot for event ' + n['id'])
                slot = value['slots'][slot_id]
                if not slot.get('sample'):
                    raise ValueError('Note-block preview needs real samples in the supplied profile')
                key = slot_id, n['note']
                if key not in cache:
                    sample = base / slot['sample']
                    data, sr = sf.read(sample, dtype='float32')
                    if data.ndim != 1 or not np.isfinite(data).all():
                        raise ValueError('Sample must be finite mono audio')
                    if slot.get('sampleSha256') and _hash(sample) != slot['sampleSha256']:
                        raise ValueError('Sample hash changed after profile calibration')
                    step = sr / rate * 2 ** ((n['note'] - 12) / 12)
                    cache[key] = np.interp(np.arange(0, max(0, len(data) - 1), step), np.arange(len(data)), data) * slot.get('gain', 1)
                x = cache[key]
            else:
                length = min(end + tail - start, max(.005, n['sourceEndSeconds'] - start))
                family = n['family']
                kind = 'kick' if family == 'kick' else 'snare' if family == 'snare' else 'hat' if family == 'hats' else 'sustain' if family in ('voice', 'pad', 'theme_body') else 'pluck'
                x = _synthesize({'kind': kind, 'seconds': length, 'gain': .12 * n.get('velocity', 90) / 127}, n['sourceMidi'], rate, 42, max_seconds=end + tail)
            cursor = round(start * rate)
            if cursor >= len(audio):
                continue
            x = x[:len(audio) - cursor]
            audio[cursor:cursor + len(x), 0] += x * .70710678
            audio[cursor:cursor + len(x), 1] += x * .70710678
    audio = audio[round(begin * rate):round((end + tail) * rate)]
    if not np.isfinite(audio).all():
        raise ValueError('Render produced non-finite audio')
    peak = float(np.max(np.abs(audio)))
    gain = min(1., .89 / max(peak, 1e-12))
    audio *= gain
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(out, audio, rate, format='WAV', subtype='PCM_24')
    report = {'schemaVersion': 1, 'mode': mode, 'output': str(out), 'sha256': _hash(out), 'sampleRate': rate,
              'beginSeconds': begin, 'endSeconds': end, 'scoreDurationSeconds': duration,
              'tailSeconds': tail, 'peakBeforeGain': peak,
              'commonSafetyGain': gain, 'referenceKind': 'original synthesized structural audition' if mode == 'reference' else 'General MIDI SoundFont audition' if mode == 'gm' else 'explicit sample-bank note-block approximation',
              'actualMinecraftRecording': False, 'spatialSimulation': False, 'listeningVerified': False,
              'limitations': ['No reference-mode output establishes real instrument timbre or artistic approval', 'Actual game attenuation, listener motion and simultaneous voice limits need client validation']}
    if soundfont:
        report['soundfontSha256'] = _hash(soundfont)
    if mode=='gm':report['renderer']=renderer
    _write(out.with_suffix(out.suffix + '.json'), report)
    return report


def compare_candidates(a, b, out):
    """Export loudness-matched A/B copies with shared true-peak headroom."""
    import numpy as np
    import soundfile as sf
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise ValueError('FFmpeg is required for integrated loudness and true-peak measurements')
    sources, measurements, audio = [Path(a).resolve(strict=True), Path(b).resolve(strict=True)], [], []
    for p in sources:
        data, rate = sf.read(p, dtype='float32', always_2d=True)
        if not data.size or not np.isfinite(data).all():
            raise ValueError('Comparison input must contain finite audio')
        audio.append((data, rate))
        run = subprocess.run([ffmpeg, '-hide_banner', '-nostdin', '-i', str(p), '-af', 'loudnorm=I=-18:TP=-2:LRA=11:print_format=json', '-f', 'null', '-'], capture_output=True, text=True, timeout=90)
        if run.returncode or '{' not in run.stderr:
            raise ValueError('Loudness analysis failed: ' + run.stderr[-400:])
        m, _ = json.JSONDecoder().raw_decode(run.stderr[run.stderr.rfind('{'):])
        if not math.isfinite(float(m['input_i'])) or not math.isfinite(float(m['input_tp'])):
            raise ValueError('Input is too silent/short for a finite loudness comparison')
        measurements.append(m)
    if audio[0][1] != audio[1][1] or abs(len(audio[0][0]) - len(audio[1][0])) / audio[0][1] > .05:
        raise ValueError('A/B must have the same sample rate and aligned duration (<=50 ms difference)')
    gains_db = [-18 - float(m['input_i']) for m in measurements]
    headroom_db = min(0., -2 - max(float(m['input_tp']) + g for m, g in zip(measurements, gains_db)))
    folder = _new_dir(out)
    rows = []
    for label, p, (data, rate), m, gain_db in zip(('A', 'B'), sources, audio, measurements, gains_db):
        gain_db += headroom_db
        path = folder / (label + '.wav')
        sf.write(path, data * 10 ** (gain_db / 20), rate, subtype='PCM_24')
        rows.append({'label': label, 'sourceSha256': _hash(p), 'output': str(path), 'sha256': _hash(path),
                     'inputLUFS': float(m['input_i']), 'inputTruePeakDb': float(m['input_tp']), 'gainDb': gain_db})
    report = {'schemaVersion': 1, 'candidates': rows, 'targetLUFS': -18, 'truePeakCeilingDb': -2,
              'contentAlignmentVerified': False, 'listeningVerified': False, 'relativeBalanceWithinEachMixPreserved': True,
              'limitations': ['Operator must choose the same musical excerpt; equal lengths do not prove aligned content', 'Loudness matching does not establish which version sounds better']}
    _write(folder / 'comparison.json', report)
    return report
