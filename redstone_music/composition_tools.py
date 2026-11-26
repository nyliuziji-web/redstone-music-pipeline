"""Editable composition workbench: frozen musical evidence, explicit new writing, real auditions.

The chosen voicing helper is pinned upstream MIT code. It supplies candidate
pitches, never an automatic claim of faithful transcription or good arrangement.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import sys
import warnings

from .midi import parse_midi
from .music_tools import _absolute_tracks, _hash, _json, _new_dir, _time_at, _write


def _digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def _note(n):
    return {'id':n['id'],'sourceId':n['id'],'channel':n['channel'],'pitch':n['sourceMidi'],
            'startTick':n['startTick'],'endTick':n['keyReleaseTick'],'velocity':n['velocity'],
            'origin':'source_reconstruction'}


def _controls(midi):
    return [[(t,m.hex()) for t,_,m in events if m.type not in ('note_on','note_off','end_of_track')]
            for events in _absolute_tracks(midi)]


def _read(project):
    if not isinstance(project,(str,Path)):
        raise ValueError('Composition must be a concrete composition.json path')
    path=Path(project).resolve(strict=True)
    doc=_json(path)
    if not isinstance(doc,dict) or doc.get('schemaVersion')!=1 or doc.get('kind')!='music-composition':
        raise ValueError('Expected music-composition schemaVersion 1')
    source=(path.parent/doc['source']['path']).resolve(strict=True)
    if not source.is_relative_to(path.parent) or _hash(source)!=doc['source']['sha256']:
        raise ValueError('Frozen source MIDI is outside project or its hash changed')
    binding=doc.get('contract',{})
    if not isinstance(binding.get('path'),str):raise ValueError('Composition lacks its frozen contract')
    contract=(path.parent/binding['path']).resolve(strict=True)
    if not contract.is_relative_to(path.parent) or _hash(contract)!=binding.get('sha256'):
        raise ValueError('Frozen composition contract changed')
    terms=_json(contract)
    for key,value in {'sourceMidiSha256':doc['source']['sha256'],
                      'frozenSourceNoteIds':doc['frozenSourceNoteIds'],
                      'sourceControlsSha256':doc['sourceControlsSha256']}.items():
        if terms.get(key)!=value:raise ValueError('Composition disagrees with its frozen contract: '+key)
    return path,doc,source


def _validate(doc, source):
    import mido
    _digest(doc)  # Reject NaN/Infinity even in descriptive fields.
    score=parse_midi(source.read_bytes())
    original={n['id']:_note(n) for n in score['notes']}
    source_by_id={n['id']:n for n in score['notes']}
    midi=mido.MidiFile(source)
    if doc.get('ppq')!=score['ppq'] or doc.get('tempoMap')!=score['tempoMap']:
        raise ValueError('Composition cannot silently overwrite the source tempo map or PPQ')
    if doc.get('sourceControlsSha256')!=_digest(_controls(midi)):
        raise ValueError('Original control/meta-event binding changed')
    if type(doc.get('lengthTicks')) is not int or not 1<=doc['lengthTicks']<=score['ppq']*4096:
        raise ValueError('Composition lengthTicks must be a bounded positive integer')
    original_end=max(sum(m.time for m in t) for t in midi.tracks)
    if doc['lengthTicks']<original_end:
        raise ValueError('Composition may not truncate the source timeline')
    tracks=doc.get('tracks')
    if not isinstance(tracks,list) or len(tracks)>64:
        raise ValueError('Composition needs at most 64 editable tracks')
    if sum(len(t.get('notes',[])) for t in tracks if isinstance(t,dict))>50000:
        raise ValueError('Composition exceeds the 50000-note workbench budget')
    ids=set();track_ids=set();seen_source=set();found={};source_tracks=set()
    channels={m.channel for t in midi.tracks for m in t if hasattr(m,'channel')}
    added_channels={}
    for track in tracks:
        tid=track.get('id')
        if not isinstance(tid,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}',tid) or tid in track_ids:
            raise ValueError('Track IDs must be unique short identifiers')
        track_ids.add(tid)
        source_track=track.get('sourceTrack')
        if source_track is not None:
            if type(source_track) is not int or source_track not in range(len(midi.tracks)) or source_track in source_tracks:
                raise ValueError('Invalid or duplicate original source track')
            source_tracks.add(source_track)
        else:
            if track.get('origin')!='new_arrangement':
                raise ValueError('Added tracks must explicitly declare new_arrangement')
            ch=track.get('channel')
            if type(ch) is not int or not 0<=ch<16 or ch!=9 and ch in channels:
                raise ValueError('New melodic track needs an unused MIDI channel')
            if ch!=9 and ch in added_channels:
                raise ValueError('Independent melodic tracks may not share one channel/program')
            added_channels[ch]=tid
            if ch!=9 and (type(track.get('program')) is not int or not 0<=track['program']<=127):
                raise ValueError('New pitched track requires a General MIDI program')
        ns=track.get('notes')
        if not isinstance(ns,list) or len(ns)>50000:raise ValueError('Invalid or excessive note list')
        bykey=defaultdict(list)
        for n in ns:
            ident=n.get('id')
            if not isinstance(ident,str) or not ident or ident in ids:raise ValueError('Note IDs must be globally unique')
            ids.add(ident);found[ident]=n
            for key,low,high in [('pitch',0,127),('velocity',1,127),('channel',0,15),('startTick',0,doc['lengthTicks']),('endTick',1,doc['lengthTicks'])]:
                if type(n.get(key)) is not int or not low<=n[key]<=high:raise ValueError('Invalid note '+key)
            if n['endTick']<=n['startTick']:raise ValueError('Note release must follow onset')
            sid=n.get('sourceId')
            if sid is not None:
                if sid not in original or sid in seen_source or ident!=sid:
                    raise ValueError('Source note IDs must remain stable and unique')
                seen_source.add(sid)
                actual=source_by_id[sid]
                if source_track!=actual['sourceTrack'] or n['channel']!=original[sid]['channel']:
                    raise ValueError('Source note cannot migrate track/channel and inherit unrelated controls')
                if n.get('origin')!='source_reconstruction':raise ValueError('Original notes must keep their provenance')
            else:
                if not ident.startswith('new:') or n.get('origin')!='new_arrangement':
                    raise ValueError('New notes require new: ID and new_arrangement provenance')
                if source_track is None and n['channel']!=track['channel']:
                    raise ValueError('New note channel differs from its track')
            bykey[(n['channel'],n['pitch'])].append(n)
        for seq in bykey.values():
            ordered=sorted(seq,key=lambda n:n['startTick'])
            if any(a['endTick']>b['startTick'] for a,b in zip(ordered,ordered[1:])):
                raise ValueError('Overlapping same-key notes in one track/channel')
    if source_tracks!=set(range(len(midi.tracks))):
        raise ValueError('Every original source track, including meta-only tracks, must remain')
    frozen=doc.get('frozenSourceNoteIds')
    if not isinstance(frozen,list) or len(set(frozen))!=len(frozen) or any(i not in original for i in frozen):
        raise ValueError('Invalid frozen source note contract')
    for ident in frozen:
        if found.get(ident)!=original[ident]:raise ValueError('Frozen source note changed or disappeared: '+ident)
    sections=doc.get('sections',[])
    if not isinstance(sections,list):raise ValueError('Sections must be an array')
    for section in sections:
        if (not isinstance(section.get('name'),str) or type(section.get('startTick')) is not int
                or type(section.get('endTick')) is not int or not 0<=section['startTick']<section['endTick']<=doc['lengthTicks']):
            raise ValueError('Section must have a name and bounded tick interval')
    return score


def import_composition(midi,out,freeze_roles=None,roles=None):
    """Import an exact MIDI and an editable note view without rounding its timeline."""
    import mido
    midi=Path(midi).resolve(strict=True)
    score=parse_midi(midi.read_bytes());parsed=mido.MidiFile(midi)
    freeze_all=freeze_roles is None
    freeze_roles=[] if freeze_all else freeze_roles
    if not isinstance(freeze_roles,(list,tuple)) or not all(isinstance(x,str) for x in freeze_roles):
        raise ValueError('freeze_roles must be a list of role names')
    roles={} if roles is None else roles
    if isinstance(roles,(str,Path)):roles=_json(roles)
    if not isinstance(roles,dict):raise ValueError('roles maps source track indices to semantic roles')
    tracks=[];frozen=[]
    for ti,track in enumerate(parsed.tracks):
        ns=[n for n in score['notes'] if n['sourceTrack']==ti]
        name=next((m.name for m in track if m.type=='track_name'),f'Track {ti}')
        family=roles.get(str(ti),roles.get(ti,ns[0]['family'] if ns else 'conductor'))
        if not isinstance(family,str):raise ValueError('Role name must be text')
        tracks.append({'id':f'source_{ti}','sourceTrack':ti,'name':name,'family':family,
                       'origin':'source_reconstruction','notes':[_note(n) for n in ns]})
        if freeze_all or family in freeze_roles:frozen.extend(n['id'] for n in ns)
    length=max(sum(m.time for m in t) for t in parsed.tracks)
    actual_roles={t['family'] for t in tracks if t['notes']}
    missing=set(freeze_roles)-actual_roles
    if missing:raise ValueError('No notes matched requested frozen roles: '+', '.join(sorted(missing)))
    if freeze_all:freeze_roles=sorted(actual_roles)
    doc={'schemaVersion':1,'kind':'music-composition','title':midi.stem,'ppq':score['ppq'],
         'lengthTicks':length,'source':{'path':'source.mid','sha256':_hash(midi)},
         'sourceControlsSha256':_digest(_controls(parsed)),'tempoMap':score['tempoMap'],
         'tracks':tracks,'frozenSourceNoteIds':frozen,'freezeRoles':list(freeze_roles),
         'sections':[{'name':'SOURCE','startTick':0,'endTick':length}],
         'decisions':[],'listeningVerified':False,'artisticApproval':False}
    _validate(doc,midi)
    folder=_new_dir(out);shutil.copyfile(midi,folder/'source.mid')
    contract={'schemaVersion':1,'sourceMidiSha256':doc['source']['sha256'],
              'frozenSourceNoteIds':frozen,'sourceControlsSha256':doc['sourceControlsSha256']}
    _write(folder/'frozen.json',contract)
    doc['contract']={'path':'frozen.json','sha256':_hash(folder/'frozen.json')}
    _write(folder/'composition.json',doc)
    return {'composition':str(folder/'composition.json'),'frozenSourceNotes':len(frozen),'sourceMidiSha256':_hash(midi),
            'notes':len(score['notes']),'sourceCopiedExactly':True,'listeningVerified':False}


def validate_composition(project):
    _,doc,source=_read(project);_validate(doc,source)
    return {'schemaVersion':1,'valid':True,'tracks':len(doc['tracks']),
            'notes':sum(len(t['notes']) for t in doc['tracks']), 'frozenSourceNotes':len(doc['frozenSourceNoteIds']),
            'sourceControlsPreserved':True,'listeningVerified':False,'artisticApproval':False}


def revise_composition(project,patch,out):
    """Revise a declared region; frozen notes and source controls cannot be changed."""
    path,original,source=_read(project);_validate(original,source)
    patch=_json(patch) if not isinstance(patch,dict) else patch
    if (not isinstance(patch,dict) or patch.get('schemaVersion')!=1 or patch.get('sourceProjectSha256')!=_hash(path)
            or set(patch)-{'schemaVersion','sourceProjectSha256','beginTick','endTick','operations','addNotes','addTracks','decision','sections'}):
        raise ValueError('Revision requires current sourceProjectSha256 and supported fields')
    begin,end=patch.get('beginTick'),patch.get('endTick')
    if type(begin) is not int or type(end) is not int or not 0<=begin<end<=original['lengthTicks']:
        raise ValueError('Revision tick interval is invalid')
    doc=copy.deepcopy(original);tracks={t['id']:t for t in doc['tracks']}
    changed=[];removed=[];added=[]
    operations=patch.get('operations',[])
    if not isinstance(operations,list) or not all(isinstance(x,dict) for x in operations) or len({(x.get('track'),x.get('note')) for x in operations})!=len(operations):
        raise ValueError('Revision operations must have unique track/note pairs')
    for op in operations:
        if not isinstance(op,dict) or set(op)-{'track','note','pitch','velocity','startTick','endTick','remove'}:
            raise ValueError('Unsupported composition note revision')
        if 'remove' in op and type(op['remove']) is not bool:raise ValueError('remove must be boolean')
        track=tracks.get(op.get('track'))
        if track is None:raise ValueError('Unknown revision track')
        note=next((n for n in track['notes'] if n['id']==op.get('note')),None)
        if note is None:raise ValueError('Unknown revision note')
        if note['id'] in doc['frozenSourceNoteIds']:raise ValueError('Cannot revise frozen source note '+note['id'])
        if note['startTick']<begin or note['endTick']>end:raise ValueError('Revision touches a note outside its region')
        if op.get('remove'):
            track['notes'].remove(note);removed.append(note['id']);continue
        for key in ('pitch','velocity','startTick','endTick'):
            if key in op:note[key]=op[key]
        if note['startTick']<begin or note['endTick']>end:raise ValueError('Revised note escapes its region')
        changed.append(note['id'])
    newtracks=patch.get('addTracks',[])
    if not isinstance(newtracks,list):raise ValueError('addTracks must be an array')
    for track in newtracks:
        if not isinstance(track,dict) or track.get('sourceTrack') is not None or track.get('id') in tracks:
            raise ValueError('Added track must have a new ID and no sourceTrack')
        for n in track.get('notes',[]):
            if n['startTick']<begin or n['endTick']>end:raise ValueError('New track note escapes revision region')
        doc['tracks'].append(copy.deepcopy(track));tracks[track['id']]=doc['tracks'][-1]
        added.extend(n['id'] for n in track.get('notes',[]))
    additions=patch.get('addNotes',[])
    if not isinstance(additions,list):raise ValueError('addNotes must be an array')
    for addition in additions:
        item=copy.deepcopy(addition);tid=item.pop('track',None)
        if tid not in tracks:raise ValueError('New note requires an existing track')
        if item['startTick']<begin or item['endTick']>end:raise ValueError('New note escapes revision region')
        tracks[tid]['notes'].append(item);added.append(item['id'])
    if 'sections' in patch:doc['sections']=copy.deepcopy(patch['sections'])
    if patch.get('decision'):
        if not isinstance(patch['decision'],str):raise ValueError('Decision must be text')
        doc['decisions'].append(patch['decision'])
    doc['parentProjectSha256']=_hash(path)
    doc['revision']={'beginTick':begin,'endTick':end,'changed':changed,'removed':removed,'added':added}
    _validate(doc,source)
    folder=_new_dir(out);shutil.copyfile(source,folder/'source.mid')
    shutil.copyfile(path.parent/original['contract']['path'],folder/'frozen.json')
    doc['contract']['path']='frozen.json'
    _write(folder/'composition.json',doc)
    report={'schemaVersion':1,'composition':str(folder/'composition.json'),'parentProjectSha256':_hash(path),
            'frozenSourceNotesPreserved':True,'sourceControlsPreserved':True,**doc['revision'],
            'listeningVerified':False,'artisticApproval':False}
    _write(folder/'revision.json',report)
    return report


def export_composition(project,out):
    import mido
    _,doc,source=_read(project);score=_validate(doc,source)
    out=Path(out).resolve()
    if out.exists() or out.with_suffix(out.suffix+'.json').exists():raise ValueError('Composition export must be new')
    original=mido.MidiFile(source);absolute=_absolute_tracks(original)
    bysource={t['sourceTrack']:t for t in doc['tracks'] if t.get('sourceTrack') is not None}
    original_notes={n['id']:_note(n) for n in score['notes']}
    changed_tracks=[];rendered=[]
    for ti,track in enumerate(original.tracks):
        ns=bysource[ti]['notes'];old=[_note(n) for n in score['notes'] if n['sourceTrack']==ti]
        if sorted(ns,key=lambda n:n['id'])==sorted(old,key=lambda n:n['id']):
            rendered.append(copy.deepcopy(track));continue
        changed_tracks.append(ti)
        events=[(t,index,m.copy(time=0)) for t,index,m in absolute[ti] if m.type not in ('note_on','note_off','end_of_track')]
        for index,n in enumerate(ns):
            events.extend([(n['startTick'],len(track)+index*2+1,mido.Message('note_on',channel=n['channel'],note=n['pitch'],velocity=n['velocity'])),
                           (n['endTick'],len(track)+index*2,mido.Message('note_off',channel=n['channel'],note=n['pitch'],velocity=0))])
        rendered.append(_to_track(events,max(doc['lengthTicks'],sum(m.time for m in track))))
    for track in doc['tracks']:
        if track.get('sourceTrack') is not None:continue
        ch=track['channel'];events=[(0,-2,mido.MetaMessage('track_name',name=track.get('name',track['id'])))]
        if ch!=9:events.append((0,-1,mido.Message('program_change',channel=ch,program=track['program'])))
        for index,n in enumerate(track['notes']):
            events.extend([(n['startTick'],index*2+1,mido.Message('note_on',channel=ch,note=n['pitch'],velocity=n['velocity'])),
                           (n['endTick'],index*2,mido.Message('note_off',channel=ch,note=n['pitch'],velocity=0))])
        rendered.append(_to_track(events,doc['lengthTicks']))
    result=mido.MidiFile(type=1 if len(rendered)>1 else original.type,ticks_per_beat=doc['ppq']);result.tracks.extend(rendered)
    buffer=io.BytesIO();result.save(file=buffer);candidate=buffer.getvalue()
    parsed=parse_midi(candidate)
    if parsed['tempoMap']!=score['tempoMap'] or _controls(result)[:len(original.tracks)]!=_controls(original):
        raise ValueError('Export changed original tempo/control/meta events')
    # Source-track note ordinals can change after deliberate removal, so compare frozen musical tuples.
    frozen=[original_notes[i] for i in doc['frozenSourceNoteIds']]
    def signature(n):return (n['channel'],n['pitch'],n['startTick'],n['endTick'],n['velocity'])
    actual=Counter((n['sourceTrack'],*signature(_note(n))) for n in parsed['notes'])
    for n in frozen:
        ti=next(x['sourceTrack'] for x in score['notes'] if x['id']==n['id'])
        if not actual[(ti,*signature(n))]:raise ValueError('Export changed frozen music')
    out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(candidate)
    report={'schemaVersion':1,'midi':str(out),'sha256':_hash(out),'sourceMidiSha256':_hash(source),
            'originalControlEventsPreserved':True,'frozenSourceNotesPreserved':True,'changedSourceTracks':changed_tracks,
            'newTracks':len(rendered)-len(original.tracks),'musicalAccuracyVerified':False,'listeningVerified':False}
    _write(out.with_suffix(out.suffix+'.json'),report);return report


def _to_track(events,end):
    import mido
    track=mido.MidiTrack();previous=0
    for tick,_,msg in sorted(events,key=lambda row:(row[0],row[1])):
        track.append(msg.copy(time=tick-previous));previous=tick
    track.append(mido.MetaMessage('end_of_track',time=max(0,end-previous)))
    return track


def _voicing_module():
    from .kit import resource_root
    root=resource_root()/'integrations/music-skill'
    provenance=_json(root/'provenance.json')
    for entry in provenance['files']:
        if _hash(root/entry['local'])!=entry['sha256']:raise ValueError('Pinned music-skill source changed')
    name='_rmp_music_skill'
    if name not in sys.modules:
        spec=importlib.util.spec_from_file_location(name,root/'musiclib/__init__.py',submodule_search_locations=[str(root/'musiclib')])
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    subname=name+'.voicing'
    if subname not in sys.modules:
        spec=importlib.util.spec_from_file_location(subname,root/'musiclib/voicing.py')
        module=importlib.util.module_from_spec(spec);sys.modules[subname]=module;spec.loader.exec_module(module)
    return sys.modules[subname],provenance


def plan_voicings(chords,out=None,voices=3,low=48,high=72,against=None,keep_root=False,avoid_parallels=False):
    """Return optional restrained voice-leading candidates using pinned MIT upstream."""
    if not isinstance(chords,list) or not chords or len(chords)>64 or not all(isinstance(c,str) for c in chords):
        raise ValueError('Supply 1..64 chord symbols')
    if type(voices) is not int or not 1<=voices<=4 or type(low) is not int or type(high) is not int or not 0<=low<high<=127 or high-low>36:
        raise ValueError('Invalid bounded voicing range/voice count')
    module,provenance=_voicing_module()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        notes=module.voice_lead(chords,voices=voices,low=low,high=high,against=against,
                                keep_root=keep_root,avoid_parallels=avoid_parallels)
    result={'schemaVersion':1,'chords':chords,'voicings':notes,'range':[low,high],
            'backend':'pinned music-skill voice_lead','upstreamCommit':provenance['commit'],
            'warnings':[str(w.message) for w in caught],
            'limitations':['Optional arranging heuristics; dissonance and parallel motion may be intentional',
                           'Pitches only: rhythm, articulation, form and listening remain the composer responsibility'],
            'artisticApproval':False}
    if out:_write(out,result)
    return result


def review_composition(project,out=None):
    _,doc,source=_read(project);_validate(doc,source)
    ppq=doc['ppq'];sections=doc.get('sections') or [{'name':'FULL','startTick':0,'endTick':doc['lengthTicks']}]
    parts=[];findings=[]
    for track in doc['tracks']:
        ns=track['notes']
        if not ns:continue
        groups=defaultdict(list)
        for n in ns:groups[(n['startTick'],n['endTick'])].append(n)
        chord_groups=[g for g in groups.values() if len(g)>=3]
        block_ratio=sum(len(g) for g in chord_groups)/len(ns)
        if block_ratio>.9:
            findings.append({'track':track['id'],'kind':'uniform-block-chords',
                'message':'Most notes strike/release as chord blocks; compare sustained inner voices, staggered entries or purposeful stabs. This may suit the style.'})
        if len(set(n['velocity'] for n in ns))==1 and len(ns)>16:
            findings.append({'track':track['id'],'kind':'uniform-velocity','message':'One MIDI velocity throughout; review accents and section shape rather than adding random jitter.'})
        metrics=[]
        for s in sections:
            selected=[n for n in ns if s['startTick']<=n['startTick']<s['endTick']]
            bars=(s['endTick']-s['startTick'])/(ppq*4)
            metrics.append({'section':s['name'],'notes':len(selected),'notesPerFourQuarterUnit':len(selected)/bars,
                'register':[min(n['pitch'] for n in selected),max(n['pitch'] for n in selected)] if selected else None,
                'velocityMean':sum(n['velocity'] for n in selected)/len(selected) if selected else None})
        parts.append({'track':track['id'],'role':track.get('family'),'origin':track['origin'],'notes':len(ns),
            'register':[min(n['pitch'] for n in ns),max(n['pitch'] for n in ns)],'blockChordNoteRatio':block_ratio,'sections':metrics})
    result={'schemaVersion':1,'compositionSha256':_digest(doc),'parts':parts,'findings':findings,
            'frozenSourceNotes':len(doc['frozenSourceNoteIds']),'tempoPreserved':True,
            'scope':'Measured arranging risks; four-quarter density is not an inferred meter or an artistic score',
            'listeningVerified':False,'artisticApproval':False}
    if out:_write(out,result)
    return result


def render_composition(project,out,soundfont=None,gm_engine='auto',fluidsynth=None):
    """Render the master and same-gain solos with a real supplied bank or explicit reference synth."""
    import mido
    import soundfile as sf
    from .music_tools import render_preview
    _,doc,source=_read(project);_validate(doc,source)
    if soundfont and not Path(soundfont).is_file():raise ValueError('Supply a real SoundFont file for GM audition')
    folder=_new_dir(out);midi=export_composition(project,folder/'master.mid')
    mode='gm' if soundfont else 'reference'
    render_options=dict(mode=mode,soundfont=soundfont,gm_engine=gm_engine,fluidsynth=fluidsynth)
    mix=render_preview(folder/'master.mid',folder/'mix.wav',**render_options)
    master=mido.MidiFile(folder/'master.mid');rendered=[(folder/'mix.wav',mix)]
    order=sorted([t for t in doc['tracks'] if t.get('sourceTrack') is not None],key=lambda t:t['sourceTrack'])
    order += [t for t in doc['tracks'] if t.get('sourceTrack') is None]
    solos=[]
    for ti,track in enumerate(order):
        if not track['notes']:continue
        solo=mido.MidiFile(type=master.type,ticks_per_beat=master.ticks_per_beat)
        for index,original in enumerate(master.tracks):
            if index==ti:solo.tracks.append(copy.deepcopy(original));continue
            tick=0;events=[]
            for serial,message in enumerate(original):
                tick+=message.time
                if message.type not in ('note_on','note_off','end_of_track'):
                    events.append((tick,serial,message.copy(time=0)))
            solo.tracks.append(_to_track(events,tick))
        solo_path=folder/('solo-'+track['id']+'.mid');solo.save(solo_path)
        wav=solo_path.with_suffix('.wav');row=render_preview(solo_path,wav,**render_options)
        rendered.append((wav,row));solos.append({'track':track['id'],'role':track.get('family'),'midi':str(solo_path),'audio':str(wav)})
    # Use one scale for mix and solos; do not make a weak part sound strong in isolation.
    gain=min(1.,.89/max(max(r['peakBeforeGain'] for _,r in rendered),1e-12))
    for wav,row in rendered:
        audio,rate=sf.read(wav,always_2d=True,dtype='float32')
        audio*=gain/row['commonSafetyGain']
        sf.write(wav,audio,rate,subtype='PCM_24')
        row.update(commonSafetyGain=gain,sha256=_hash(wav),gainScope='one gain shared by mix and all solos')
        wav.with_suffix(wav.suffix+'.json').write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    review=review_composition(project,folder/'arrangement-review.json')
    report={'schemaVersion':1,'midi':midi['midi'],'mix':str(folder/'mix.wav'),'preview':mix,
            'arrangementReview':str(folder/'arrangement-review.json'),'rendererMode':mode,
            'soundfontSha256':_hash(soundfont) if soundfont else None,'solos':solos,'sharedMixAndSoloSafetyGain':gain,
            'actualMinecraftRecording':False,'listeningVerified':False,'artisticApproval':False}
    _write(folder/'render.json',report);return report


def create_arrangement_study(out,soundfont=None,gm_engine='auto',fluidsynth=None):
    """Original 16-bar frozen-lead study: two intentionally different arrangements, not an auto-composer."""
    import mido
    from .music_tools import compare_candidates
    folder=_new_dir(out);ppq=480;length=16*4*ppq
    source=mido.MidiFile(type=1,ticks_per_beat=ppq)
    conductor=mido.MidiTrack([mido.MetaMessage('set_tempo',tempo=625000),mido.MetaMessage('time_signature',numerator=4,denominator=4)])
    conductor.append(mido.MetaMessage('end_of_track',time=length));source.tracks.append(conductor)
    melody=[];motifs=[[69,72,76,74,72],[67,71,74,72,67],[65,69,72,71,69],[64,68,71,69,64]]
    for bar in range(16):
        phrase=motifs[bar%4]
        # Repetition carries identity; bar-end gaps let an answering part speak.
        starts=[0,1,1.5,2.5,3] if bar%4!=3 else [0,1,2,2.5,3]
        for j,(beat,pitch) in enumerate(zip(starts,phrase)):
            if bar>=12 and j==4:continue
            if bar==15:pitch=[69,72,71,69,69][j]
            t=round((bar*4+beat)*ppq);duration=round((.42 if j<4 else .68)*ppq)
            melody.extend([(t,j*2+1,mido.Message('note_on',channel=0,note=pitch,velocity=88+(4 if j==0 else -j))),
                           (t+duration,j*2,mido.Message('note_off',channel=0,note=pitch,velocity=0))])
    source.tracks.append(_to_track([(0,-2,mido.MetaMessage('track_name',name='Theme - original frozen lead')),
                                    (0,-1,mido.Message('program_change',channel=0,program=10))]+melody,length))
    source.save(folder/'original-lead.mid')
    imported=import_composition(folder/'original-lead.mid',folder/'lead',freeze_roles=('theme_attack',))
    base=Path(imported['composition']);sha=_hash(base)
    chords=['Am','F','C','G']*3+['F','Dm','E7','Am']
    voicing=plan_voicings(chords,voices=3,low=48,high=67,keep_root=False)
    _write(folder/'voicing-plan.json',voicing)
    variants={}
    for mode in ('spacious','groove'):
        tracks=[]
        def add_track(tid,name,role,channel,program):
            item={'id':tid,'name':name,'family':role,'channel':channel,'program':program,
                  'origin':'new_arrangement','notes':[]};tracks.append(item);return item
        harmony=add_track('new_harmony','Chords - open inner voices','chords',1,4)
        bass=add_track('new_bass','Sub bass - phrase roots','sub_bass',2,33)
        answer=add_track('new_answer','Answer - fills in gaps','answer',3,11)
        drums=add_track('new_drums','Drums - written accents','drums',9,None)
        def note(track,bar,beat,pitch,duration,velocity):
            n=len(track['notes']);start=round((bar*4+beat)*ppq)
            track['notes'].append({'id':f'new:{mode}:{track["id"]}:{n}','channel':track['channel'],
                'pitch':pitch,'startTick':start,'endTick':min(length,start+round(duration*ppq)),
                'velocity':velocity,'origin':'new_arrangement'})
        roots=[45,41,36,43]*3+[41,38,40,45]
        for bar,v in enumerate(voicing['voicings']):
            lift=bar>=8 and bar<12
            if mode=='spacious':
                # Held voices enter separately; no 1/3-beat triad train.
                for j,pitch in enumerate(v):note(harmony,bar,.25+j*.25,pitch,2.5-j*.3,45+(8 if lift else 0))
                note(bass,bar,0,roots[bar],2.75,72+(5 if lift else 0))
                if bar%4 in (1,3):
                    note(answer,bar,3.5,v[-1]+12,.3,49)
                if 8<=bar<12:
                    note(drums,bar,0,36,.12,61);note(drums,bar,2,38,.12,40)
            else:
                # Offbeat comping with independent bass answers and a contrasting break.
                if 4<=bar<8:
                    for j,pitch in enumerate(v):note(harmony,bar,0,pitch,2.8,43)
                    note(bass,bar,0,roots[bar],2.6,66)
                else:
                    for beat in (.5,1.75,3.25):
                        for j,pitch in enumerate(v):note(harmony,bar,beat,pitch,.32,52+(8 if lift else 0)-j*3)
                    for beat,dur,pitch,vel in [(0,.6,roots[bar],83),(1.5,.35,roots[bar]+7,62),(2.75,.65,roots[bar],74)]:
                        note(bass,bar,beat,pitch,dur,vel)
                    if bar%4==3:note(answer,bar,3.75,v[-1]+12,.2,60)
                    if bar<14:
                        for beat in (0,2.5):note(drums,bar,beat,36,.12,85 if beat==0 else 68)
                        for beat in (1,3):note(drums,bar,beat,38,.12,72)
                        for j in range(8):note(drums,bar,j*.5,42,.10,53 if j%2 else 38)
        patch={'schemaVersion':1,'sourceProjectSha256':sha,'beginTick':0,'endTick':length,'addTracks':tracks,
               'sections':[{'name':'THEME','startTick':0,'endTick':ppq*16},{'name':'CONTRAST','startTick':ppq*16,'endTick':ppq*32},
                           {'name':'LIFT','startTick':ppq*32,'endTick':ppq*48},{'name':'CODA','startTick':ppq*48,'endTick':length}],
               'decision':'Original educational '+mode+' arrangement; preserve lead exactly and let accompaniment carry contrast.'}
        _write(folder/(mode+'.patch.json'),patch)
        revised=revise_composition(base,patch,folder/mode)
        rendered=render_composition(revised['composition'],folder/(mode+'-audition'),
                                    soundfont=soundfont,gm_engine=gm_engine,fluidsynth=fluidsynth)
        variants[mode]={'composition':revised['composition'],**rendered}
    comparison=compare_candidates(variants['spacious']['mix'],variants['groove']['mix'],folder/'comparison')
    report={'schemaVersion':1,'license':'CC0-1.0 original teaching notes; source code MIT',
            'bars':16,'sourceLead':str(folder/'original-lead.mid'),'variants':variants,'comparison':comparison,
            'frozenLeadPreserved':True,'purpose':'Study choices and revise; not a style-independent automatic arranger',
            'actualMinecraftRecording':False,'listeningVerified':False,'artisticApproval':False}
    _write(folder/'study.json',report);return report
