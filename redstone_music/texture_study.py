"""Reproducible original A/B for quiet orchestration in physical note blocks."""
from collections import Counter


DURATION = 16
TEXTURE_ROLES = ('pad', 'echo', 'fx')
IDENTITY = ('id', 'family', 'sourceMidi', 'sourceStartSeconds', 'sourceEndSeconds',
            'gt', 'note', 'kind', 'slot', 'instrument', 'baseBlock')


def _scores(base, layered):
    import mido

    score = mido.MidiFile(type=1, ticks_per_beat=480)
    score.add_track().extend([
        mido.MetaMessage('set_tempo', tempo=500000),
        mido.MetaMessage('end_of_track', time=DURATION*960),
    ])

    def track(name, channel, program, notes):
        lane = score.add_track(name)
        if channel != 9:
            lane.append(mido.Message('program_change', channel=channel, program=program))
        events = []
        for onset, key, length, velocity in notes:
            events.append((round(onset*960), 1, key, velocity))
            events.append((round((onset+length)*960), 0, key, 0))
        last = 0
        for tick, on, key, velocity in sorted(events):
            lane.append(mido.Message('note_on' if on else 'note_off',
                                     channel=channel, note=key, velocity=velocity, time=tick-last))
            last = tick
        lane.append(mido.MetaMessage('end_of_track', time=DURATION*960-last))

    roots = [38, 41, 43, 36, 38, 41, 43, 38]
    triads = [[53, 57, 60], [53, 57, 62], [55, 58, 62], [52, 55, 60],
              [53, 57, 60], [53, 57, 62], [55, 58, 62], [53, 57, 62]]
    phrases = [(69, 72, 74), (72, 69, 65), (67, 70, 74), (72, 67, 64),
               (69, 72, 77), (74, 72, 69), (70, 67, 65), (67, 64, 62)]
    track('Theme', 0, 10, [(2*i+t, key, .24, 93 if t==0 else 81)
                         for i, p in enumerate(phrases) for t, key in zip((0, .45, 1.10), p)])
    track('Sub bass', 1, 33, [(2*i+t, key+d, .28, 77)
                            for i, key in enumerate(roots) for t, d in [(0, 0), (.97, 7)]])
    track('Chords', 2, 4, [(2*i+t, key, .33, 62) for i, chord in enumerate(triads)
                          for t, key in zip((0, .22, .75), chord)])
    track('Drums', 9, 0, [(2*i+t, 36, .075, 78) for i in range(8) for t in (0, 1.36)])
    score.save(base)
    track('Pad', 3, 89, [(i*2+.32, chord[-1], .62, 47) for i, chord in enumerate(triads)])
    track('Echo', 4, 8, [(i*2+1.53, p[-1]-12, .23, 48) for i, p in enumerate(phrases)])
    track('Brush grains', 9, 0, [(i*2+t, 70, .06, 42) for i in range(3, 8)
                                  for t in ((.82, 1.69) if i % 2 else (.62, 1.82))])
    score.save(layered)


def _palette():
    rows = [
        ('theme_attack','lead','flute','clay',70,'pluck',.30,.35,{'decaySeconds':.28}),
        ('sub_bass','bass','bass','oak_planks',43,'bass',.46,.23,{'sustainLevel':.18}),
        ('chords','inner','harp','dirt',58,'pluck',.42,.14,{'brightnessHz':2400}),
        ('kick','kick','basedrum','stone',60,'kick',.20,.24,{'attackWeight':0.}),
        ('pad','wash','bit','emerald_block',60,'sustain',.74,.065,
         {'attackSeconds':.15,'releaseSeconds':.22,'brightnessHz':1250,'attackWeight':0.}),
        ('echo','shadow','banjo','hay_block',60,'wood',.27,.064,
         {'attackSeconds':.015,'decaySeconds':.13,'brightnessHz':2200}),
        ('fx','grain','hat','glass',60,'hat',.13,.081,
         {'attackSeconds':.018,'brightnessHz':4800,'attackWeight':0.}),
    ]
    roles, slots = {}, {}
    for role, key, instrument, block, root, kind, seconds, gain, shape in rows:
        roles[role] = key
        slots[key] = {'instrument':instrument,'baseBlock':'minecraft:'+block,'rootMidi':root,
                      'recipe':{'kind':kind,'rootMidi':root,'seconds':seconds,'gain':gain,**shape}}
    return {'schemaVersion':1,'id':'original_texture_study','roles':roles,'slots':slots}


def create_texture_study(out):
    """Write two runnable projects and common-gain sample previews."""
    from pathlib import Path
    import numpy as np
    import soundfile as sf
    from .core import atomic_json, hash_file, initialize
    from .music_tools import plan_noteblocks
    from .timbre_tools import RATE, _mix, _new_dir, _write, build_palette

    folder = _new_dir(out)
    sources = {k:folder/(k+'.mid') for k in ('base','layered')}
    _scores(sources['base'],sources['layered'])
    palette = _palette()
    _write(folder/'palette.json',palette)
    bank = build_palette(folder/'palette.json',folder/'sound-bank')
    layouts = {'theme_attack':(0,2),'chords':(-12,0),'sub_bass':(0,-9),
               'kick':(10,-14),'pad':(-9,9),'echo':(10,9),'fx':(-17,3)}
    mixes, events, outputs = {}, {}, {}
    for label, midi in sources.items():
        project = folder/label
        config = initialize(project,title=f'Original quiet texture study - {label}',midi=midi)['config']
        config['inputs'].update(soundProfile=bank['profile'],soundPack=bank['soundPack'])
        config['machine']['layout'] = {'families':[
            {'id':role,'x':x,'y':y} for role,(x,y) in layouts.items()]}
        config['visuals']['enabled'] = False
        atomic_json(project/'project.json',config)
        result = plan_noteblocks(midi,project/'preview-events',bank['profile'])
        events[label] = result['candidates']
        mix, solos = _mix(result,bank['profile'],0,DURATION)
        mixes[label] = mix
        if label=='layered':
            mixes['texture-only'] = sum(solos[role] for role in TEXTURE_ROLES)
        outputs[label] = {'project':str(project),'previewEvents':result['eventsPath']}
    signature = lambda rows: {tuple(n[k] for k in IDENTITY) for n in rows}
    original = signature(events['base'])
    retained = signature(n for n in events['layered'] if n['family'] not in TEXTURE_ROLES)
    if original != retained or not np.allclose(mixes['layered']-mixes['base'],mixes['texture-only'],atol=1e-6):
        raise ValueError('Texture study has changed the baseline')
    gain = min(1.,.89/max(float(abs(x).max()) for x in mixes.values()))
    media = {}
    for k, x in mixes.items():
        path = folder/(k+'.wav')
        sf.write(path,np.column_stack((x,x))*gain*(2**-.5),RATE,subtype='PCM_24')
        media[k] = {'path':str(path),'sha256':hash_file(path)}
    report = {'schemaVersion':1,'durationSeconds':DURATION,'tailSeconds':2,'musicAndSamplesLicense':'CC0-1.0',
              'projects':outputs,'auditions':media,'soundPack':bank['soundPack'],'commonGain':gain,
              'baselineNotesPreserved':len(original),'addedByRole':dict(Counter(
                  n['family'] for n in events['layered'] if n['family'] in TEXTURE_ROLES)),
              'peakStartsPerGameTick':{k:max(Counter(n['gt'] for n in rows).values()) for k,rows in events.items()},
              'actualMinecraftRecording':False,'artisticApproval':False}
    _write(folder/'study.json',report)
    return report
