"""Deterministic vanilla adaptation or lossless approved-event import.

The event layer is separate from the MIDI master. Dynamics are proxies, not a
claim that vanilla note blocks execute MIDI velocity or stop at note-off.
"""
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import zipfile

from .midi import half_up


TONAL = [
    ('bass', 30, 'minecraft:oak_planks'), ('guitar', 42, 'minecraft:white_wool'),
    ('harp', 54, 'minecraft:dirt'), ('bit', 54, 'minecraft:emerald_block'),
    ('banjo', 54, 'minecraft:hay_block'), ('iron_xylophone', 54, 'minecraft:iron_block'),
    ('flute', 66, 'minecraft:clay'), ('bell', 78, 'minecraft:gold_block')]
PREFER = {'sub_bass': 'bass', 'mid_bass': 'guitar', 'theme_attack': 'banjo', 'theme_body': 'bit',
          'voice': 'harp', 'echo': 'harp', 'chords': 'harp', 'pad': 'flute', 'arp': 'iron_xylophone',
          'answer': 'iron_xylophone', 'piano': 'harp'}
DRUMS = {'kick': ('basedrum', 'minecraft:stone', 0), 'snare': ('snare', 'minecraft:sand', 0),
         'hats': ('hat', 'minecraft:glass', 0), 'fx': ('basedrum', 'minecraft:stone', 12)}


def fingerprint_inputs(ctx):
    """Nested profile samples are real inputs, not just an optional JSON label."""
    value = ctx['config'].get('inputs', {}).get('soundProfile')
    if not value:
        return []
    from .music_tools import sound_profile_dependencies
    path = Path(value)
    path = path if path.is_absolute() else Path(ctx['project']) / path
    return sound_profile_dependencies(path)


def _write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _validate_event(event):
    if type(event['gt']) is not int or event['gt'] < 0:
        raise ValueError('Event gt must be a nonnegative integer')
    if type(event['note']) is not int or not 0 <= event['note'] <= 24:
        raise ValueError('Event note must be 0..24')
    if event['kind'] not in ('onset', 'retrigger', 'carry'):
        raise ValueError('Unknown musical event kind')
    if not all(isinstance(event[k], (int, float)) and math.isfinite(event[k]) for k in ('sourceStartSeconds', 'sourceEndSeconds')):
        raise ValueError('Source note times must be finite numbers')
    if event['sourceStartSeconds'] < 0 or event['sourceEndSeconds'] <= event['sourceStartSeconds']:
        raise ValueError('Invalid source note interval')
    if not isinstance(event['id'], str) or not isinstance(event['parentId'], str):
        raise ValueError('Event IDs must be strings')
    if type(event['sourceMidi']) is not int or not 0 <= event['sourceMidi'] <= 127:
        raise ValueError('Source MIDI pitch must be 0..127')
    instruments = {x[0] for x in TONAL} | {'basedrum', 'snare', 'hat', 'xylophone', 'cow_bell', 'didgeridoo', 'chime', 'pling'}
    if event['instrument'] not in instruments or not re.fullmatch(r'minecraft:[a-z0-9_]+', event['baseBlock']):
        raise ValueError('Invalid Minecraft instrument or base block identifier')


def run(ctx):
    out = Path(ctx['out'])
    out.mkdir(parents=True, exist_ok=True)
    music = Path(ctx['deps']['music'])
    score = json.loads((music / 'score.json').read_text(encoding='utf-8'))
    settings = ctx['config'].get('sound', {})
    resources = ctx['config'].get('inputs', {}).get('soundPack')
    profile_path = ctx['config'].get('inputs', {}).get('soundProfile')
    adaptation_path = ctx['config'].get('inputs', {}).get('adaptationPlan')
    report = {'schemaVersion': 1, 'profile': settings.get('profile', 'vanilla'), 'sourceMode': score['sourceMode'],
              'listeningVerified': False, 'soundPackProvided': bool(resources), 'transformations': [],
              'limitations': ['Vanilla note-off and per-note velocity are not implemented by the game sound engine',
                              'Generated arrangement and mix require listening; structural success is not artistic approval']}
    adapter=settings.get('adapter','role-consistent')
    if adapter not in ('role-consistent','legacy-vanilla'):
        raise ValueError('sound.adapter must be role-consistent or explicit legacy-vanilla')
    if settings.get('profile', 'vanilla') != 'vanilla' and not resources:
        raise ValueError('A custom sound profile requires an explicit input soundPack')
    if profile_path or adaptation_path or (score['sourceMode']!='approved_events' and adapter!='legacy-vanilla'):
        from .music_tools import plan_noteblocks, validate_sound_profile, validate_soundpack
        path, profile = None, None
        if profile_path:
            path = Path(profile_path)
            path = path if path.is_absolute() else Path(ctx['project']) / path
            profile = validate_sound_profile(path)
        if score['sourceMode'] == 'approved_events':
            raise ValueError('An exact approved-event baseline cannot be silently remapped by a sound profile; import the MIDI for explicit re-adaptation')
        if profile_path and not resources:
            raise ValueError('A calibrated sound profile requires its explicit soundPack')
        if resources and not profile_path:
            raise ValueError('An explicit adaptation with custom soundPack needs its calibrated soundProfile')
        adaptation = None
        if adaptation_path:
            adaptation = Path(adaptation_path)
            adaptation = adaptation if adaptation.is_absolute() else Path(ctx['project']) / adaptation
        events = plan_noteblocks(score, profile=path, adaptation_plan=adaptation,
                                consistency=settings.get('consistency','role'))
        if not settings.get('retrigger',True):
            events['candidates']=[n for n in events['candidates'] if n['kind']!='retrigger']
        for decision in events['phraseDecisions']:
            if decision['transpose']:
                report['transformations'].append({'family':decision['role'],
                    'type':'whole-role-octave-transpose' if events.get('consistency')=='role' else 'whole-phrase-octave-transpose',
                    'semitones':decision['transpose'],'noteIds':decision['noteIds']})
        if not profile_path:
            report['limitations'].append('Vanilla sample envelopes are unmeasured here; no fixed 5/6 GT retrigger is invented. Long notes need a calibrated sound profile and listening.')
        report.update(profile=events['profileId'], phraseDecisions=events['phraseDecisions'],
                      adapter=adapter, consistency=events.get('consistency'),
                      sustainStrategy='explicit per-slot profile; no fixed global retrigger interval',
                      events=len(events['candidates']), onsets=sum(n['kind'] == 'onset' for n in events['candidates']),
                      retriggers=sum(n['kind'] == 'retrigger' for n in events['candidates']),
                      sourceOnsetsMapped=len(score['notes']),
                      soundPackRuntimeVerified=False)
        if adaptation:
            report.update(explicitAdaptationApplied=True, adaptationPlanSha256=hashlib.sha256(adaptation.read_bytes()).hexdigest())
            shutil.copyfile(adaptation, out / 'adaptation_plan.json')
        else:
            _write(out/'adaptation_plan.json',{'schemaVersion':1,'profileId':events['profileId'],
                'sourceMidiSha256':events.get('sourceMidiSha256'),'decisions':events['phraseDecisions'],
                'listeningVerified':False})
        if profile_path:
            pack = Path(resources)
            pack = pack if pack.is_absolute() else Path(ctx['project']) / pack
            report['soundPackValidation'] = validate_soundpack(pack, path)
            report['profileSha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            report['soundPackSha256'] = hashlib.sha256(pack.read_bytes()).hexdigest()
            shutil.copyfile(pack, out / 'resources.zip')
            # Keep the artifact profile self-contained for later candidate audition.
            (out / 'samples').mkdir()
            for key, slot in profile['slots'].items():
                sample = Path(slot['sample'])
                sample = sample if sample.is_absolute() else path.parent / sample
                shutil.copyfile(sample, out / 'samples' / (key + '.ogg'))
                slot['sample'] = 'samples/' + key + '.ogg'
            _write(out / 'sound_profile.json', profile)
        _write(out / 'events.json', events)
        _write(out / 'sound_report.json', report)
        return {'events': report['events'], 'onsets': report['onsets'], 'retriggers': report['retriggers'],
                'profileId': events['profileId'], 'listeningVerified': False}
    if score['sourceMode'] == 'approved_events':
        baseline = json.loads((music / 'approved_events.json').read_text(encoding='utf-8-sig'))
        candidates = baseline['notes']
        merged = []
        report['approvedEventsPreservedExactly'] = True
        report['limitations'].append('Imported instrument slots do not prove the corresponding custom sound pack is enabled')
    else:
        candidates, merged, shifts = [], [], {}
        grouped = {}
        for n in score['notes']:
            if n['family'] not in DRUMS:
                grouped.setdefault(n['family'], []).append(n['sourceMidi'])
        # One shift per role, never a silent octave fold per note.
        for family, pitches in grouped.items():
            valid = [v for v in range(-120, 121, 12) if min(pitches) + v >= 30 and max(pitches) + v <= 102]
            if not valid:
                raise ValueError(f'Role {family} exceeds supported 73-semitone vanilla span; specialist must split or revise the arrangement')
            shift = min(valid, key=lambda v: (abs(v), v))
            shifts[family] = shift
            if shift:
                report['transformations'].append({'family': family, 'type': 'whole-role-octave-transpose', 'semitones': shift})
        for n in score['notes']:
            family, source_midi = n['family'], n['sourceMidi']
            transpose = shifts.get(family, 0)
            mapped = source_midi + transpose
            if family in DRUMS:
                instrument, base, note = DRUMS[family]
                approximation = 'GM percussion approximated with vanilla percussion'
            else:
                options = [x for x in TONAL if x[1] <= mapped <= x[1] + 24]
                preferred = PREFER.get(family, 'harp')
                instrument, low, base = min(options, key=lambda x: (x[0] != preferred, abs(mapped - x[1] - 12), TONAL.index(x)))
                note = mapped - low
                approximation = None if instrument == preferred and transpose == 0 else 'Register-aware vanilla orchestration; source master unchanged'
            gt = half_up(n['sourceStartSeconds'] * 20)
            event = {'id': n['id'], 'parentId': n['parentId'], 'sourceTrack': n['sourceTrack'], 'family': family,
                     'gt': gt, 'phase': gt % 2, 'kind': 'onset', 'sourceMidi': source_midi,
                     'sourceStartSeconds': n['sourceStartSeconds'], 'sourceEndSeconds': n['sourceEndSeconds'],
                     'mappedMidi': mapped, 'instrument': instrument, 'note': note, 'baseBlock': base,
                     'gainProxy': round(n['velocity'] / 127, 6), 'transpose': transpose, 'approximation': approximation}
            candidates.append(event)
            if settings.get('retrigger', True) and family in ('voice', 'echo', 'theme_body', 'pad'):
                end = half_up(n['sourceEndSeconds'] * 20)
                step = 6 if family == 'pad' else 5
                for i, t in enumerate(range(gt + step, end - 1, step), 1):
                    candidates.append(dict(event, id=f'{event["id"]}_r{i}', gt=t, phase=t % 2,
                                           kind='retrigger', gainProxy=round(event['gainProxy'] * .65, 6)))
        report['sourceOnsetsMapped'] = len(score['notes'])
    candidates.sort(key=lambda x: (x['gt'], x['id'])) if score['sourceMode'] != 'approved_events' else None
    ids = set()
    for event in candidates:
        _validate_event(event)
        if event['id'] in ids:
            raise ValueError('Duplicate musical event ID')
        ids.add(event['id'])
    if resources:
        path = Path(resources)
        if not path.is_absolute():
            path = Path(ctx['project']) / path
        with zipfile.ZipFile(path) as z:
            if 'pack.mcmeta' not in z.namelist() or z.testzip() is not None:
                raise ValueError('Invalid sound resource pack ZIP/root metadata')
            for info in z.infolist():
                parts = info.filename.replace('\\', '/').split('/')
                if info.filename.startswith(('/', '\\')) or '..' in parts:
                    raise ValueError('Unsafe path in sound resource pack')
        shutil.copyfile(path, out / 'resources.zip')
        report['soundPackSha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        report['soundPackRuntimeVerified'] = False
    duration = score['durationSeconds']
    cut_gt = score.get('sourceOffsetGT', 0)
    events = {'schemaVersion': 1, 'sourceMidiSha256': score.get('sourceMidiSha256'), 'durationSeconds': duration,
              'sourceOffsetGT': cut_gt,
              'musicGT': max(math.ceil(duration * 20), max(n.get('q', n['gt'] - cut_gt) for n in candidates) + 1),
              'candidates': candidates, 'merged': merged}
    if score['sourceMode'] == 'approved_events':
        events['sourceInfo'] = baseline.get('info', {})
    report.update(events=len(candidates), onsets=sum(n['kind'] != 'retrigger' for n in candidates),
                  retriggers=sum(n['kind'] == 'retrigger' for n in candidates), quantization='nonnegative-half-up at 20 Hz')
    _write(out / 'events.json', events)
    _write(out / 'sound_report.json', report)
    return {'events': len(candidates), 'onsets': report['onsets'], 'retriggers': report['retriggers'],
            'approvedEventsPreservedExactly': report.get('approvedEventsPreservedExactly', False), 'listeningVerified': False}
