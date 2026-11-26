"""An authored performance score for note blocks, bound to an untouched MIDI master."""
from collections import Counter, defaultdict
from pathlib import Path
import struct

from .core import atomic_json, read_json

PROTECTED = ('theme_attack', 'voice')


def arrange(score, profile=None, routing=None, decisions=None, consistency='role', retrigger=True):
    """Apply explicit editorial decisions, then the game's pitch/clock constraints."""
    from .music_tools import plan_noteblocks
    from .sound import DRUMS, PREFER

    if decisions is not None and not isinstance(decisions, dict):
        raise ValueError('Game arrangement must be a JSON object')
    authored = decisions is not None
    rules = decisions or {}
    allowed = {'schemaVersion', 'sourceMidiSha256', 'protectedRoles', 'edits'}
    if authored and (rules.get('schemaVersion') != 1 or rules.keys()-allowed
                     or not score.get('sourceMidiSha256')
                     or rules.get('sourceMidiSha256') != score['sourceMidiSha256']):
        raise ValueError('Game arrangement must bind the exact MIDI master SHA-256')
    valid_roles = set(DRUMS) | set(PREFER)
    protected = rules.get('protectedRoles', list(PROTECTED) if authored else [])
    edits = rules.get('edits', [])
    if (not isinstance(protected, list) or not all(isinstance(x,str) and x in valid_roles for x in protected)
            or not isinstance(edits, list)):
        raise ValueError('Game arrangement needs a list of known protected roles and an edits array')

    notes = {n['id']: n for n in score['notes']}
    changes, omitted = {}, set()
    working = {k:v for k,v in score.items() if k!='notes'}
    ordered = []
    for edit in edits:
        if not isinstance(edit,dict) or set(edit)-{'noteId','midi','role','shiftGT','omit','reason'}:
            raise ValueError('Invalid game arrangement edit fields')
        key = edit.get('noteId')
        if not isinstance(key,str) or key not in notes or key in changes:
            raise ValueError(f'Unknown or repeated game arrangement note: {key}')
        reason = edit.get('reason')
        if not isinstance(reason,str) or not reason.strip():
            raise ValueError(f'{key}: explain the intended musical effect of this edit')
        src = notes[key]
        if src['family'] in protected:
            raise ValueError(f'{key}: role {src["family"]} is protected in the game arrangement')
        pitch, role = edit.get('midi',src['sourceMidi']), edit.get('role',src['family'])
        delta, omit = edit.get('shiftGT',0), edit.get('omit',False)
        if (type(pitch) is not int or not 0<=pitch<=127 or not isinstance(role,str) or role not in valid_roles
                or type(delta) is not int or abs(delta)>40 or type(omit) is not bool):
            raise ValueError(f'{key}: invalid pitch, role, time shift (maximum 40 GT) or omission')
        if (role in DRUMS)!=(src['family'] in DRUMS):
            raise ValueError(f'{key}: use a separate percussion arrangement for pitched/drum conversions')
        if omit and set(edit)-{'noteId','omit','reason'}:
            raise ValueError(f'{key}: an omitted note cannot also be changed')
        if not omit and (pitch,role,delta)==(src['sourceMidi'],src['family'],0):
            raise ValueError(f'{key}: edit has no effect')
        if src['sourceStartSeconds']+delta/20 < score.get('sourceOffsetGT',0)/20-1e-9:
            raise ValueError(f'{key}: shift starts before the beginning of this arrangement')
        changes[key] = {**edit,'midi':pitch,'role':role,'shiftGT':delta,'omit':omit}
        if omit:
            omitted.add(key)
    for src in score['notes']:
        key = src['id']
        if key in omitted:
            continue
        row = dict(src)
        if key in changes:
            edit = changes[key]
            row.update(sourceMidi=edit['midi'], family=edit['role'],
                       sourceStartSeconds=src['sourceStartSeconds']+edit['shiftGT']/20,
                       sourceEndSeconds=src['sourceEndSeconds']+edit['shiftGT']/20)
        ordered.append(row)
    if not ordered:
        raise ValueError('Game arrangement has no surviving notes')
    working['notes'] = ordered
    cut = score.get('sourceOffsetGT',0)
    working['durationSeconds'] = max(score['durationSeconds'],
                                     max(n['sourceEndSeconds'] for n in ordered)-cut/20)
    events = plan_noteblocks(working, profile=profile, adaptation_plan=routing,consistency=consistency)
    if not retrigger:
        events['candidates'] = [n for n in events['candidates'] if n['kind']!='retrigger']
    review_lines, onsets = [], {}
    for event in events['candidates']:
        original = notes[event['parentId']]
        if original['family'] in protected and event['mappedMidi']!=original['sourceMidi']:
            raise ValueError(f'{original["id"]}: protected role requires a slot that preserves its register')
        if event['kind']=='onset':
            onsets[original['id']] = event
        event['arrangedStartSeconds'] = event['sourceStartSeconds']
        event['arrangedEndSeconds'] = event['sourceEndSeconds']
        event['arrangedMidi'] = event['sourceMidi']
        event['sourceFamily'] = original['family']
        for field in ('sourceStartSeconds','sourceEndSeconds','sourceMidi'):
            event[field] = original[field]
    for key, src in notes.items():
        event = onsets.get(key)
        if event is None and key not in omitted:
            raise ValueError(f'Missing onset after arrangement: {key}')
        review_lines.append({
            'noteId': key, 'sourceMidi': src['sourceMidi'], 'sourceRole':src['family'],
            'sourceStartSeconds': src['sourceStartSeconds'], 'status':'omitted' if event is None else 'placed',
            'reason':changes.get(key,{}).get('reason'),
            'mappedMidi':None if event is None else event['mappedMidi'],
            'role':None if event is None else event['family'],
            'slot':None if event is None else event['slot'],
            'triggerGT':None if event is None else event['gt'],
            'onsetDeltaMs':None if event is None else round((event['gt']/20-src['sourceStartSeconds'])*1000,3),
            'gridDeltaMs':None if event is None else round((event['gt']/20-event['arrangedStartSeconds'])*1000,3),
        })
    events['omitted'] = [{'id': key,'reason':changes[key]['reason']} for key in notes if key in omitted]
    by_tick = Counter(n['gt'] for n in events['candidates'])
    summary = {'schemaVersion':1,'sourceMidiSha256':score.get('sourceMidiSha256'),
               'protectedRoles':protected,'authoredEdits':len(changes),'sourceOnsets':len(notes),
               'placedOnsets':len(onsets),'omissions':len(omitted),'events':len(events['candidates']),
               'peakStartsPerGameTick':max(by_tick.values()),
               'maxGridDeltaMs':max(abs(n['gridDeltaMs']) for n in review_lines if n['gridDeltaMs'] is not None),
               'notes':review_lines,
               'artisticApproval':False}
    return events, summary


def export_performance_midi(events, path):
    """Render the physical trigger score as MIDI, with short editorial note gates.

    MIDI programs are preview labels. Resource-pack timbre and physical timing
    remain in the event plan. Separate track records preserve overlapping
    identical strikes for inspection; their GM playback can vary by player.
    """
    from .demo import _vlq
    from .sound import DRUMS

    presets = {'theme_attack':10,'theme_body':89,'voice':73,'mid_bass':32,'sub_bass':33,
               'chords':8,'arp':25,'pad':88,'piano':0,'answer':9,'echo':11}
    channels = {key:ch for key,ch in zip(presets,(n for n in range(16) if n!=9))}
    tracks = defaultdict(list)
    length = events['musicGT'] * 48
    for n in events['candidates']:
        percussion = n['family'] in DRUMS
        ch = 9 if percussion else channels[n['family']]
        key = n.get('arrangedMidi',n['sourceMidi']) if percussion else n['mappedMidi']
        if type(key) is not int or not 0<=key<=127:
            raise ValueError('Game pitch cannot be represented in MIDI 0..127')
        at = n.get('q', n['gt']-events.get('sourceOffsetGT',0)) * 48
        group = (n['family'],n['slot'],ch)
        lanes = tracks[group]
        lane = next((lane for lane in lanes if lane[0].get(key,-1)<=at),None)
        if lane is None:
            lane = ({},[])
            lanes.append(lane)
        end = min(length,max(at+1,at+(72 if percussion else 144)))
        velocity = max(1,min(127,int(n.get('velocity',90))))
        lane[1].extend([(at,1,bytes([0x90+ch,key,velocity])),(end,0,bytes([0x80+ch,key,0]))])
        lane[0][key] = end

    def chunk(data):
        return b'MTrk'+struct.pack('>I',len(data))+data

    conductor = bytearray(b'\x00\xff\x51\x03\x07\xa1\x20')
    previous = 0
    for section in sorted(events.get('sections',[]),key=lambda s:s['beginGT']):
        tick = max(0,min(length,section['beginGT']*48))
        name = str(section['name']).encode()[:512]
        conductor.extend(_vlq(tick-previous)+b'\xff\x06'+_vlq(len(name))+name)
        previous = tick
    conductor.extend(_vlq(length-previous)+b'\xff\x2f\x00')
    parts = [chunk(conductor)]
    for (role,slot,ch), lanes in tracks.items():
        for i,(_, notes) in enumerate(lanes,1):
            label = f'{role} / {slot} / {i}'.encode()
            data = bytearray(b'\x00\xff\x03'+_vlq(len(label))+label)
            if ch!=9:
                data.extend((0,0xc0+ch,presets[role]))
            last = 0
            for tick,_,msg in sorted(notes):
                data.extend(_vlq(tick-last)+msg)
                last = tick
            data.extend(_vlq(length-last)+b'\xff\x2f\x00')
            parts.append(chunk(data))
    Path(path).write_bytes(b'MThd'+struct.pack('>IHHH',6,1,len(parts),480)+b''.join(parts))


def create_game_arrangement(source, out, profile=None, routing_path=None, decisions_path=None):
    from .music_tools import _new_dir, _score, render_preview

    score = _score(source)
    decisions = read_json(decisions_path) if decisions_path else None
    events, report = arrange(score,profile,routing_path,decisions)
    folder = _new_dir(out)
    atomic_json(folder/'events.json',events)
    if decisions is not None:
        atomic_json(folder/'decisions.json',decisions)
    export_performance_midi(events,folder/'game-performance.mid')
    report.update(events=str(folder/'events.json'),midi=str(folder/'game-performance.mid'),
                  midiMeaning='Physical start ticks and pitches; cue durations and GM timbres are editorial previews')
    if profile:
        render_preview(folder/'events.json',folder/'sample-preview.wav',mode='noteblock',profile=profile)
        report['samplePreview'] = str(folder/'sample-preview.wav')
    atomic_json(folder/'arrangement-report.json',report)
    return report
