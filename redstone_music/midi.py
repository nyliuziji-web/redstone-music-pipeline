"""Strict Standard MIDI File reader with exact tempo-map and pedal timing.

No synthesizer or transcription claims are made by this parser. Original files
remain the master; the returned score is a loss-aware interchange format.
"""
from bisect import bisect_right
from collections import defaultdict
import math
import struct


def half_up(value):
    return math.floor(value + .5)


def family_for(name, program, channel, key):
    name = name.lower()
    if channel == 9:
        return 'kick' if key in (35, 36) else 'snare' if key in (38, 39, 40) else 'hats' if key in (42, 44, 46) else 'fx'
    for words, family in [(('echo', '回声'), 'echo'), (('vocal', 'voice', '主唱', '人声'), 'voice'),
                          (('theme body', 'theme_body', 'theme sustain', '延音层'), 'theme_body'), (('theme', 'lead', '主题', '旋律'), 'theme_attack'),
                          (('pad', '铺底'), 'pad'), (('chord', '和弦'), 'chords'), (('arp', '琶音'), 'arp'),
                          (('answer', '应答'), 'answer'), (('sub', '低音基础'), 'sub_bass'), (('mid bass', 'mid_bass', 'bass pulse'), 'mid_bass')]:
        if any(word in name for word in words):
            return family
    if 0 <= program <= 7:
        return 'piano'
    if 32 <= program <= 39:
        return 'sub_bass'
    if 52 <= program <= 54:
        return 'voice'
    if 88 <= program <= 95:
        return 'pad'
    if 8 <= program <= 15:
        return 'arp'
    return 'theme_attack'


def parse_midi(data):
    if not isinstance(data, bytes) or data[:4] != b'MThd' or len(data) < 14:
        raise ValueError('Not a Standard MIDI File (expected MThd)')
    header_length = int.from_bytes(data[4:8], 'big')
    if header_length < 6 or 8 + header_length > len(data):
        raise ValueError('Invalid MIDI header length')
    fmt, tracks, ppq = struct.unpack('>HHH', data[8:14])
    if fmt not in (0, 1) or not tracks or (fmt == 0 and tracks != 1):
        raise ValueError('Only synchronous MIDI format 0 and 1 are supported')
    if not ppq or ppq & 0x8000:
        raise ValueError('SMPTE or zero MIDI division is not supported')
    position, events, names, ends = 8 + header_length, [], {}, []
    for track in range(tracks):
        if data[position:position + 4] != b'MTrk' or position + 8 > len(data):
            raise ValueError('Missing MIDI track chunk')
        length = int.from_bytes(data[position + 4:position + 8], 'big')
        chunk = data[position + 8:position + 8 + length]
        if len(chunk) != length:
            raise ValueError('Truncated MIDI track')
        position += 8 + length
        p, tick, running, serial, ended = 0, 0, None, 0, False

        def byte():
            nonlocal p
            if p >= len(chunk):
                raise ValueError('Truncated MIDI event')
            value = chunk[p]
            p += 1
            return value

        def vlq():
            value = 0
            for _ in range(4):
                b = byte()
                value = (value << 7) | (b & 127)
                if not b & 128:
                    return value
            raise ValueError('Invalid MIDI VLQ')

        def payload(count):
            nonlocal p
            if count < 0 or p + count > len(chunk):
                raise ValueError('Truncated MIDI payload')
            value = chunk[p:p + count]
            p += count
            return value

        while p < len(chunk):
            tick += vlq()
            status = byte()
            if status < 128:
                if running is None:
                    raise ValueError('Running status without channel status')
                p -= 1
                status = running
            serial += 1
            event = {'tick': tick, 'track': track, 'order': serial}
            if status == 255:
                kind = byte()
                value = payload(vlq())
                if kind == 0x51:
                    if len(value) != 3 or int.from_bytes(value, 'big') == 0:
                        raise ValueError('Invalid MIDI tempo')
                    events.append(dict(event, type='tempo', value=int.from_bytes(value, 'big')))
                elif kind in (3, 6):
                    text = value.decode('utf-8', errors='replace')
                    if kind == 3:
                        names[track] = text
                    else:
                        events.append(dict(event, type='marker', value=text))
                elif kind == 0x2F:
                    if value or p != len(chunk):
                        raise ValueError('Invalid end-of-track event')
                    ended = True
                    break
            elif status in (0xF0, 0xF7):
                payload(vlq())
                running = None
            elif 0x80 <= status <= 0xEF:
                running = status
                kind, channel = status >> 4, status & 15
                a = byte()
                b = None if kind in (12, 13) else byte()
                if a > 127 or (b is not None and b > 127):
                    raise ValueError('Invalid channel data byte')
                events.append(dict(event, type=kind, channel=channel, a=a, b=b))
            else:
                raise ValueError(f'Unsupported MIDI status {status:#x}')
        if not ended:
            raise ValueError('Missing MIDI end-of-track')
        ends.append(tick)
    if position != len(data):
        raise ValueError('Unexpected data after final MIDI track')
    events.sort(key=lambda e: (e['tick'], e['track'], e['order']))
    # The last tempo at a tick controls the following interval.
    tempos = {0: 500000}
    for e in events:
        if e['type'] == 'tempo':
            tempos[e['tick']] = e['value']
    tempo_map, ticks, last_tick, seconds, tempo = [], [], 0, 0.0, 500000
    for t, value in sorted(tempos.items()):
        seconds += (t - last_tick) * tempo / ppq / 1_000_000
        tempo_map.append({'tick': t, 'seconds': seconds, 'microsecondsPerQuarter': value})
        ticks.append(t)
        last_tick, tempo = t, value

    def time_at(t):
        mark = tempo_map[bisect_right(ticks, t) - 1]
        return mark['seconds'] + (t - mark['tick']) * mark['microsecondsPerQuarter'] / ppq / 1_000_000

    programs, sustain = [0] * 16, [False] * 16
    active, deferred, notes = {}, defaultdict(list), []
    markers, unsupported_bends = [], 0
    track_ordinals = defaultdict(int)

    def end_note(n, t):
        n['endTick'] = t
        n['sourceEndSeconds'] = time_at(t)
        if t <= n['startTick']:
            raise ValueError('Zero or negative MIDI note duration')

    for e in events:
        kind, t = e['type'], e['tick']
        if kind == 'marker':
            markers.append({'name': e['value'], 'beginGT': half_up(time_at(t) * 20)})
            continue
        if not isinstance(kind, int):
            continue
        ch, key = e['channel'], (e['track'], e['channel'], e['a'])
        if kind == 12:
            programs[ch] = e['a']
        elif kind == 14:
            unsupported_bends += 1
        elif kind == 11 and e['a'] == 64:
            old = sustain[ch]
            sustain[ch] = e['b'] >= 64
            if old and not sustain[ch]:
                for n in deferred.pop(ch, []):
                    end_note(n, t)
        elif kind == 11 and e['a'] in (120, 123):
            for k in [k for k in active if k[1] == ch]:
                n = active.pop(k)
                n['keyReleaseTick'] = t
                end_note(n, t)
            for n in deferred.pop(ch, []):
                end_note(n, t)
        elif kind == 9 and e['b'] > 0:
            if key in active:
                raise ValueError(f'Overlapping unpaired note-on at track {e["track"]}, key {e["a"]}')
            # A rearticulation ends the preceding pedal-held instance of the same key.
            for n in list(deferred[ch]):
                if n['sourceTrack'] == e['track'] and n['sourceMidi'] == e['a']:
                    end_note(n, t)
                    deferred[ch].remove(n)
            ordinal = track_ordinals[e['track']]
            track_ordinals[e['track']] += 1
            ident = f't{e["track"]}n{ordinal}'
            n = {'id': ident, 'parentId': ident, 'sourceTrack': e['track'], 'channel': ch,
                 'program': programs[ch], 'trackName': names.get(e['track'], ''),
                 'family': family_for(names.get(e['track'], ''), programs[ch], ch, e['a']),
                 'sourceMidi': e['a'], 'startTick': t, 'sourceStartSeconds': time_at(t), 'velocity': e['b']}
            active[key] = n
            notes.append(n)
        elif kind == 8 or (kind == 9 and e['b'] == 0):
            if key not in active:
                raise ValueError(f'Unmatched note-off at track {e["track"]}, key {e["a"]}')
            n = active.pop(key)
            n['keyReleaseTick'] = t
            if sustain[ch]:
                deferred[ch].append(n)
            else:
                end_note(n, t)
    if active:
        raise ValueError(f'{len(active)} MIDI note-on events have no note-off')
    total_tick = max(ends)
    for pending in deferred.values():
        for n in pending:
            end_note(n, total_tick)
    if not notes:
        raise ValueError('MIDI contains no musical notes')
    duration = max(time_at(total_tick), max(n['sourceEndSeconds'] for n in notes))
    marker_map = {m['beginGT']: m['name'] for m in markers}
    marker_map.setdefault(0, 'INTRO' if markers else 'SONG')
    positions = sorted(marker_map)
    length = max(1, math.ceil(duration * 20))
    sections = [{'name': marker_map[p], 'beginGT': p, 'endGT': positions[i + 1] if i + 1 < len(positions) else length}
                for i, p in enumerate(positions) if p < length]
    return {'schemaVersion': 1, 'ppq': ppq, 'durationSeconds': duration, 'tempoMap': tempo_map,
            'sections': sections, 'notes': notes, 'format': fmt,
            'warnings': ([f'{unsupported_bends} pitch-bend events preserved in master MIDI; discrete note-block adaptation omits bends'] if unsupported_bends else []),
            'claims': {'structuralParsing': True, 'musicalAccuracyVerified': False, 'listeningVerified': False}}
