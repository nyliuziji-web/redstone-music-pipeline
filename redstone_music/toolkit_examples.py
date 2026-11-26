"""Reproducible original learning material (CC0), independent of Nevada and game assets."""
from pathlib import Path
import hashlib
import json

from .music_tools import _write, _new_dir, build_soundpack, edit_music_region, plan_noteblocks
from .midi import parse_midi


def learning_sound_spec():
    rows = [
        ('lead', 'banjo', 'minecraft:hay_block', 72, 'pluck', .7, .25, 'natural', 0),
        ('voice', 'harp', 'minecraft:dirt', 66, 'sustain', 1.4, .24, 'retrigger', 18),
        ('bass', 'bass', 'minecraft:oak_planks', 42, 'bass', .9, .3, 'natural', 0),
        ('harmony', 'flute', 'minecraft:clay', 65, 'sustain', 1.2, .1, 'natural', 0),
        ('kick', 'basedrum', 'minecraft:stone', 66, 'kick', .3, .38, 'natural', 0),
        ('snare', 'snare', 'minecraft:sand', 66, 'snare', .25, .2, 'natural', 0),
        ('hats', 'hat', 'minecraft:glass', 66, 'hat', .12, .08, 'natural', 0),
    ]
    slots = {}
    for key, instrument, block, root, kind, seconds, gain, mode, step in rows:
        sustain = {'mode': mode}
        if mode == 'retrigger':
            sustain['stepGT'] = step
        slots[key] = {'instrument': instrument, 'baseBlock': block, 'rootMidi': root,
                      'synthesis': {'kind': kind, 'seconds': seconds, 'gain': gain},
                      'gain': 1, 'sustain': sustain}
    return {'schemaVersion': 1, 'id': 'original_learning',
            'description': 'Original CC0 learning sounds; not Minecraft stock samples', 'slots': slots,
            'roles': {'theme_attack': 'lead', 'voice': 'voice', 'sub_bass': 'bass', 'chords': 'harmony',
                      'kick': 'kick', 'snare': 'snare', 'hats': 'hats', 'fx': 'kick'}}


def learning_midi_bytes():
    import io
    import mido
    ppq, bars, end = 480, 16, 16 * 4 * 480
    midi = mido.MidiFile(type=1, ticks_per_beat=ppq)

    def add_track(name, channel, program, notes, extra=()):
        events = [(0, 0, mido.MetaMessage('track_name', name=name)),
                  (0, 1, mido.Message('program_change', channel=channel, program=program))]
        for i, (tick, pitch, duration, velocity) in enumerate(notes):
            events.extend([(tick, i * 2 + 10, mido.Message('note_on', channel=channel, note=pitch, velocity=velocity)),
                           (tick + duration, i * 2 + 11, mido.Message('note_off', channel=channel, note=pitch, velocity=0))])
        events.extend(extra)
        track, previous = mido.MidiTrack(), 0
        for tick, _, msg in sorted(events, key=lambda e: (e[0], e[1])):
            track.append(msg.copy(time=tick - previous))
            previous = tick
        track.append(mido.MetaMessage('end_of_track', time=end - previous))
        midi.tracks.append(track)

    conductor = mido.MidiTrack()
    previous = 0
    events = [(0, mido.MetaMessage('set_tempo', tempo=500000)),
              (0, mido.MetaMessage('time_signature', numerator=4, denominator=4)),
              (0, mido.MetaMessage('marker', text='INTRO')),
              (4 * 4 * ppq, mido.MetaMessage('marker', text='VOICE')),
              (8 * 4 * ppq, mido.MetaMessage('set_tempo', tempo=625000)),
              (8 * 4 * ppq, mido.MetaMessage('marker', text='BUILD')),
              (12 * 4 * ppq, mido.MetaMessage('marker', text='CHORUS'))]
    for tick, msg in events:
        conductor.append(msg.copy(time=tick - previous))
        previous = tick
    conductor.append(mido.MetaMessage('end_of_track', time=end - previous))
    midi.tracks.append(conductor)

    motif = [67, 69, 72, 71, 67, 64, 66, 69]
    theme, voice, bass, harmony, drums = [], [], [], [], []
    progression = [(48, 60, 64, 67), (45, 57, 60, 64), (41, 53, 57, 60), (43, 55, 59, 62)]
    for bar in range(bars):
        tick = bar * 4 * ppq
        bass_note, *chord = progression[bar % 4]
        for beat in range(4):
            pitch = motif[(bar * 2 + beat) % len(motif)] + (0 if bar < 12 else 5)
            theme.append((tick + beat * ppq, pitch, 360, 84 + bar // 4 * 5))
        if 4 <= bar < 8 or bar >= 12:
            voice.extend([(tick, 66 + bar % 3, 816, 100), (tick + 2 * ppq, 69 + bar % 3, 816, 94)])
        bass.extend([(tick, bass_note - 12, 840, 90), (tick + 2 * ppq, bass_note - 12, 840, 78)])
        if bar >= 2:
            harmony.extend((tick, n, 1680, 55 + (12 if bar >= 12 else 0)) for n in chord)
        for beat in range(4):
            drums.append((tick + beat * ppq, 36 if beat % 2 == 0 else 38, 70, 95 if beat % 2 == 0 else 76))
            if bar >= 4:
                drums.extend((tick + beat * ppq + sub * ppq // 2, 42, 45, 45 if sub else 55) for sub in range(2))
    add_track('Theme', 0, 80, theme)
    add_track('Voice', 1, 53, voice)
    add_track('Sub bass', 2, 33, bass)
    # A known CC64 episode exercises preservation in the local MIDI patch lesson.
    pedal = [(8 * ppq, 2, mido.Message('control_change', channel=3, control=64, value=127)),
             (11 * ppq + 360, 3, mido.Message('control_change', channel=3, control=64, value=0))]
    add_track('Chords', 3, 0, harmony, pedal)
    add_track('Drums', 9, 0, drums)
    buffer = io.BytesIO()
    midi.save(file=buffer)
    return buffer.getvalue()


def create_learning_example(out):
    """Create the full original 36-second learning package, refusing overwrite."""
    folder = _new_dir(out)
    master = folder / 'master.mid'
    master.write_bytes(learning_midi_bytes())
    score = parse_midi(master.read_bytes())
    source_hash = hashlib.sha256(master.read_bytes()).hexdigest()
    voice = next(n for n in score['notes'] if n['family'] == 'voice')
    interval = {'beginSeconds': voice['sourceStartSeconds'], 'endSeconds': voice['sourceEndSeconds']}
    bad_patch = {'schemaVersion': 1, 'sourceSha256': source_hash, **interval,
                 'operations': [{'id': voice['id'], 'pitch': voice['sourceMidi'] + 24}]}
    edit_music_region(master, bad_patch, folder / 'bad_octave.mid')
    fix = {'schemaVersion': 1, 'sourceSha256': hashlib.sha256((folder / 'bad_octave.mid').read_bytes()).hexdigest(), **interval,
           'operations': [{'id': voice['id'], 'pitch': voice['sourceMidi']}]}
    _write(folder / 'fix_octave.patch.json', fix)
    spec = learning_sound_spec()
    _write(folder / 'sound_spec.json', spec)
    bank = build_soundpack(folder / 'sound_spec.json', folder / 'sound_bank')
    plan = plan_noteblocks(master, folder / 'adaptation', profile=bank['profile'])
    shared = json.loads(json.dumps(spec))
    shared['slots']['voice']['instrument'] = shared['slots']['harmony']['instrument']
    _write(folder / 'bad_shared_slot.sound_spec.json', shared)
    wrong = json.loads((folder / 'sound_bank/profile.json').read_text(encoding='utf-8'))
    wrong['slots']['voice']['rootMidi'] += 12
    # This manifest is declaratively valid, intentionally acoustically wrong.
    # Its sample paths remain relative to the bank, avoiding a false path failure.
    _write(folder / 'sound_bank/bad_center.profile.json', wrong)
    manifest = {'schemaVersion': 1, 'title': 'Original learning phrase', 'license': 'CC0-1.0',
                'compositionProvenance': 'Original deterministic sixteen-bar study, no external melody/sample input',
                'durationSeconds': score['durationSeconds'], 'sourceSha256': source_hash,
                'roles': sorted({n['family'] for n in score['notes']}), 'sections': score['sections'],
                'expected': {'masterStructuralParsing': True, 'badOctaveDiagnosis': 'voice leap and register',
                             'sharedSlotMustBeRejected': True, 'badCenterNeedsFrequencyOrListeningCheck': True,
                             'pedalAndTempoMustSurvivePatch': True},
                'master': 'master.mid', 'events': 'adaptation/events.json', 'profile': 'sound_bank/profile.json',
                'soundPack': 'sound_bank/resources.zip', 'listeningVerified': False}
    _write(folder / 'lesson.json', manifest)
    (folder / 'BRIEF.md').write_text('# 原创学习曲\n\n这是一首36秒、16小节的原创练习。先辨认旋律、低音、和声、鼓和人声代奏，比较GM/参考合成与专用采样适配。\n\n检查 bad_octave.mid 的错八度，使用 fix_octave.patch.json 作局部修复；保持母版、tempo和CC64不变。bad_shared_slot.sound_spec.json 应因独立角色共享声音事件而拒绝。sound_bank/bad_center.profile.json 故意把人声参考音写错一个八度：文件格式正确仍不等于听到的音高正确。\n\n所有生成声音均为原创合成学习素材，不冒充Minecraft原版声音或专业成品。完成试听后请用户比较代表段落；听审状态保持未验收直到获得真实反馈。\n', encoding='utf-8')
    return {'schemaVersion': 1, 'directory': str(folder), 'master': str(master), 'profile': bank['profile'],
            'soundPack': bank['soundPack'], 'events': plan['eventsPath'], 'durationSeconds': score['durationSeconds'],
            'notes': len(score['notes']), 'license': 'CC0-1.0', 'listeningVerified': False}
