"""Editable single-note recipes and honest palette auditions for physical note blocks.

No Minecraft assets, external model, private runtime or game mod is required.
Generated waves are original MC-inspired materials, never called stock Minecraft.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path


RATE = 22050
KINDS = {'wood', 'pluck', 'sustain', 'bass', 'vowel', 'bell', 'kick', 'snare', 'hat'}


def _read(value):
    if isinstance(value, (str, Path)):
        path = Path(value).resolve(strict=True)
        return json.loads(path.read_text(encoding='utf-8-sig')), path.parent
    return deepcopy(value), Path.cwd()


def _write(path, data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def _sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _number(value, name, low, high):
    if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:
        raise ValueError(f'{name} must be finite within {low}..{high}')
    return float(value)


def _new_dir(path):
    path=Path(path).resolve()
    if path.exists():raise ValueError('Refusing to overwrite timbre output')
    path.mkdir(parents=True)
    return path


def _validate(recipe):
    if not isinstance(recipe,dict) or recipe.get('schemaVersion',1)!=1:
        raise ValueError('Timbre recipe requires schemaVersion 1')
    allowed={'schemaVersion','kind','rootMidi','seconds','gain','attackSeconds','releaseSeconds',
             'decaySeconds','sustainLevel','brightnessHz','detuneCents','formants','seed',
             'attackWeight','bodyWeight','attackSample','bodySample','description'}
    if recipe.keys()-allowed:raise ValueError('Unknown timbre fields: '+str(sorted(recipe.keys()-allowed)))
    if recipe.get('kind','wood') not in KINDS:raise ValueError('Unknown timbre kind')
    if type(recipe.get('rootMidi')) is not int or not 12<=recipe['rootMidi']<=115:
        raise ValueError('Recipe rootMidi must be integer 12..115')
    limits={'seconds':(.03,12,1.2),'gain':(0,.9,.22),'attackSeconds':(.001,.5,.006),
            'releaseSeconds':(.003,2,.08),'decaySeconds':(.015,10,.35),'sustainLevel':(0,1,.7),
            'brightnessHz':(80,10000,7000),'detuneCents':(0,25,3),
            'attackWeight':(0,2,.18),'bodyWeight':(0,2,.82)}
    for key,(lo,hi,default) in limits.items():_number(recipe.get(key,default),key,lo,hi)
    if type(recipe.get('seed',17)) is not int:raise ValueError('Recipe seed must be integer')
    formants=recipe.get('formants',[700,1220,2600])
    if not isinstance(formants,list) or not 1<=len(formants)<=5:raise ValueError('Use 1..5 formant frequencies')
    for value in formants:_number(value,'formant',100,9000)
    for field in ('attackSample','bodySample'):
        if field not in recipe:continue
        sample=recipe[field]
        if not isinstance(sample,dict) or not {'path','rootMidi','license'}<=sample.keys():
            raise ValueError('Sample layer requires path, rootMidi and license/source rights declaration')
        if sample.keys()-{'path','rootMidi','license','startSeconds','seconds','gain','description'}:
            raise ValueError('Unknown sample-layer field')
        if type(sample['rootMidi']) is not int or not 0<=sample['rootMidi']<=127:
            raise ValueError('Sample rootMidi must be integer 0..127')
        if not isinstance(sample['path'],str) or not sample['path'] or not isinstance(sample['license'],str) or not sample['license']:
            raise ValueError('Sample path and license must be nonempty strings')
        _number(sample.get('gain',1),'sample gain',0,4)
        _number(sample.get('startSeconds',0),'sample startSeconds',0,300)
        if 'seconds' in sample:_number(sample['seconds'],'sample seconds',.003,30)
    return recipe


def _fit(data, count):
    import numpy as np
    result=np.zeros(count,dtype=np.float64);n=min(len(data),count);result[:n]=data[:n]
    return result


def _load_layer(sample, root, root_midi, rate, limit):
    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly
    path=Path(sample['path']);path=path if path.is_absolute() else root/path
    path=path.resolve(strict=True)
    info=sf.info(path)
    if not 8000<=info.samplerate<=192000 or info.duration>300 or info.channels>2:
        raise ValueError('Layer sample must be <=300s mono/stereo at 8..192kHz')
    with sf.SoundFile(path) as stream:
        start=round(sample.get('startSeconds',0)*info.samplerate)
        if start>=len(stream):raise ValueError('Sample layer start is beyond source')
        stream.seek(start)
        data=stream.read(min(len(stream)-start,round(sample.get('seconds',limit)*info.samplerate)),dtype='float64',always_2d=True).mean(axis=1)
    if not len(data) or not np.isfinite(data).all():raise ValueError('Layer sample is empty or non-finite')
    ratio=2**((root_midi-sample['rootMidi'])/12)
    factor=Fraction(rate/info.samplerate/ratio).limit_denominator(5000)
    data=resample_poly(data,factor.numerator,factor.denominator)*sample.get('gain',1)
    return data,{'path':str(path),'sha256':_sha(path),'declaredRootMidi':sample['rootMidi'],
                 'license':sample['license'],'downmixedStereo':info.channels==2,
                 'method':'explicit local single-note layer; source root is operator supplied'}


def _wave(recipe, root, rate=RATE):
    import numpy as np
    from scipy.signal import butter,sosfilt
    recipe=_validate(deepcopy(recipe))
    seconds=recipe.get('seconds',1.2);n=round(rate*seconds);t=np.arange(n)/rate
    f=440*2**((recipe['rootMidi']-69)/12);kind=recipe.get('kind','wood')
    rng=np.random.default_rng(recipe.get('seed',17));body=np.zeros(n)
    if kind in ('kick','snare','hat'):
        from .music_tools import _synthesize
        body=_synthesize({'kind':kind,'seconds':seconds,'gain':.55},recipe['rootMidi'],rate,recipe.get('seed',17),max_seconds=12).astype(float)
    elif kind=='bass':
        phase=2*np.pi*f*t+.16*np.sin(2*np.pi*f*2*t)*np.exp(-t*18)
        body=np.sin(phase)+.18*np.sin(4*np.pi*f*t)+.07*np.sin(6*np.pi*f*t)
        body*=.65+.35*np.exp(-t/recipe.get('decaySeconds',.35))
    elif kind=='vowel':
        formants=recipe.get('formants',[700,1220,2600]);body=np.sin(2*np.pi*f*t)
        for h in range(2,min(45,int(rate*.44/f))+1):
            weight=sum(math.exp(-.5*((h*f-v)/max(100,v*.13))**2) for v in formants)
            body+=min(.55,.06/h+.28*weight)*np.sin(2*np.pi*f*h*t+.035*h*np.sin(2*np.pi*3.8*t))
        body+=.012*rng.normal(0,1,n)
    elif kind=='bell':
        for h,weight in ((1,1),(2.01,.28),(2.76,.16),(4.02,.07)):
            if f*h<rate*.44:body+=weight*np.sin(2*np.pi*f*h*t)*np.exp(-t/(recipe.get('decaySeconds',.35)/(h**.35)))
    else:
        for h in range(1,min(18,int(rate*.44/f))+1):
            weight=1 if h==1 else (.20/h**1.25 if kind=='sustain' else .50/h**1.1)
            detune=recipe.get('detuneCents',3)/1200
            frequency=f*h*(1+.00012*h if kind=='wood' else 1)
            component=np.sin(2*np.pi*frequency*t)
            if kind=='sustain':component=.9*component+.1*np.sin(2*np.pi*frequency*2**detune*t)
            elif kind in ('wood','pluck'):component*=np.exp(-t/(recipe.get('decaySeconds',.35)/(h**.5)))
            body+=weight*component
    sources=[]
    if 'bodySample' in recipe:
        data,record=_load_layer(recipe['bodySample'],root,recipe['rootMidi'],rate,seconds)
        body=_fit(data,n);sources.append({'layer':'body',**record})
    attack=np.zeros(n)
    if 'attackSample' in recipe:
        data,record=_load_layer(recipe['attackSample'],root,recipe['rootMidi'],rate,min(.3,seconds))
        attack=_fit(data,n);sources.append({'layer':'attack',**record})
    else:
        # Original material: no stock Minecraft recording is imported implicitly.
        attack=(.8*np.sin(2*np.pi*f*t)+.22*np.sin(2*np.pi*3*f*t)+.10*rng.normal(size=n))*np.exp(-t/.024)
    attack*=np.exp(-t/.04)
    envelope=np.minimum(1,t/recipe.get('attackSeconds',.006))*np.minimum(1,np.maximum(0,seconds-t)/recipe.get('releaseSeconds',.08))
    if kind in ('sustain','vowel','bass') and 'bodySample' not in recipe:
        envelope*=recipe.get('sustainLevel',.7)+(1-recipe.get('sustainLevel',.7))*np.exp(-t/.12)
    wave=(recipe.get('bodyWeight',.82)*body+recipe.get('attackWeight',.18)*attack)*envelope
    cutoff=recipe.get('brightnessHz',7000)
    wave=sosfilt(butter(2,min(cutoff,rate*.44),fs=rate,output='sos'),wave)
    wave-=float(np.mean(wave));wave*=envelope
    # Synthesis normalization is part of the declared recipe, before mixing roles.
    # The role gain is never replaced by normalization of an isolated audition.
    peak=max(float(np.max(np.abs(wave))),1e-12)
    wave*=recipe.get('gain',.22)/peak
    return wave.astype(np.float32),{'recipe':recipe,'sources':sources,'sampleRate':rate,
         'sourceKind':'explicit-local-sample-hybrid' if sources else 'original-Minecraft-inspired-synthesis',
         'license':'see explicit layer declarations' if sources else 'CC0-1.0',
         'externalAttackSampleUsed':bool('attackSample' in recipe),'actualMinecraftRecording':False,
         'noteOffImplemented':False,'listeningVerified':False}


def design_timbre(recipe, out):
    """Render one editable recipe to a finite mono OGG and retain provenance."""
    import numpy as np
    import soundfile as sf
    value,root=_read(recipe);wave,report=_wave(value,root)
    folder=_new_dir(out);path=folder/'sample.ogg'
    sf.write(path,wave,RATE,format='OGG',subtype='VORBIS')
    decoded,sr=sf.read(path,dtype='float32')
    report.update(schemaVersion=1,sample=str(path),sha256=_sha(path),seconds=len(decoded)/sr,
                  peak=float(np.max(np.abs(decoded))),rms=float(np.sqrt(np.mean(decoded**2))),
                  rootMidi=value['rootMidi'],recipeSha256=hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest())
    _write(folder/'recipe.json',value);_write(folder/'report.json',report)
    return report


def build_palette(spec, out):
    """Bake per-slot recipes into the existing calibrated profile/resource-pack contract."""
    from .music_tools import build_soundpack
    value,root=_read(spec)
    if not isinstance(value,dict) or value.get('schemaVersion')!=1 or not isinstance(value.get('slots'),dict) or not value['slots']:
        raise ValueError('Palette needs schemaVersion 1 and nonempty slots')
    recipes={}
    for key,slot in value['slots'].items():
        if not isinstance(slot,dict) or 'recipe' not in slot:raise ValueError('Every palette slot needs a recipe')
        recipe=deepcopy(slot['recipe']);recipe.setdefault('rootMidi',slot.get('rootMidi'))
        if recipe['rootMidi']!=slot.get('rootMidi'):raise ValueError('Recipe and slot rootMidi disagree')
        _validate(recipe)
        for field in ('attackSample','bodySample'):
            if field in recipe:
                p=Path(recipe[field]['path']);recipe[field]['path']=str((p if p.is_absolute() else root/p).resolve(strict=True))
        recipes[key]=recipe
    folder=_new_dir(out);pack_spec=deepcopy(value);rows={}
    for key,slot in pack_spec['slots'].items():
        if not isinstance(key,str) or not key.replace('_','').isalnum():raise ValueError('Invalid palette slot name')
        result=design_timbre(recipes[key],folder/'designs'/key);rows[key]=result
        slot.pop('recipe');slot['source']=result['sample'];slot['license']=result['license']
        slot['recipeSha256']=result['recipeSha256']
    _write(folder/'palette.json',value)
    # Explicit WAV/OGG sources are materialized here; no private runtime is a dependency.
    bank=build_soundpack(pack_spec,folder/'bank')
    audit=audit_palette(bank['profile'],out=folder/'range_audit.json')
    result={'schemaVersion':1,**bank,'designs':rows,'rangeAudit':str(folder/'range_audit.json'),
            'palette':str(folder/'palette.json'),'externalAttackSamplesProvided':any('attackSample' in r for r in recipes.values()),
            'actualMinecraftRecording':False,'listeningVerified':False,'artisticApproval':False}
    _write(folder/'report.json',result)
    return result


def _spectral_pitch(data, rate):
    import numpy as np
    if len(data)<128 or float(np.max(np.abs(data)))<1e-8:return None
    data=data[:min(len(data),rate*2)];size=2**math.ceil(math.log2(len(data)*4))
    spectrum=np.abs(np.fft.rfft(data*np.hanning(len(data)),size))
    lo=max(1,int(15*size/rate));hi=min(len(spectrum)-1,int(min(20000,rate*.47)*size/rate))
    index=lo+int(np.argmax(spectrum[lo:hi]));v=np.log(spectrum[index-1:index+2]+1e-20)
    denominator=v[0]-2*v[1]+v[2];delta=.5*(v[0]-v[2])/denominator if abs(denominator)>1e-12 else 0
    return (index+delta)*rate/size


def audit_palette(profile, events=None, out=None):
    """Measure all 25 decoded playback rates and expose tail/overlap risks."""
    import numpy as np
    import soundfile as sf
    from .music_tools import validate_sound_profile
    value=validate_sound_profile(profile);path=Path(profile).resolve();rows=[];lookup={}
    for slot_id,slot in value['slots'].items():
        p=Path(slot['sample']);p=p if p.is_absolute() else path.parent/p
        data,rate=sf.read(p,dtype='float32');energy=np.cumsum(data.astype(float)**2)
        t95=float(np.searchsorted(energy,energy[-1]*.95)/rate) if energy[-1]>0 else 0.
        notes=[]
        for note in range(25):
            ratio=2**((note-12)/12);playback_rate=max(48000,rate)
            step=rate/playback_rate*ratio
            resampled=np.interp(np.arange(0,len(data)-1,step),np.arange(len(data)),data)
            hz=None if slot['instrument'] in ('basedrum','snare','hat') else _spectral_pitch(resampled,playback_rate)
            expected=slot['rootMidi']+note-12
            cents=None if hz is None else (69+12*math.log2(hz/440)-expected)*100
            notes.append({'note':note,'expectedMidi':expected,'decodedSeconds':len(resampled)/playback_rate,
                          'energy95Seconds':t95/ratio,'spectralPitchCandidateHz':hz,'centsCandidateError':cents})
            lookup[slot_id,note]=notes[-1]
        rows.append({'slot':slot_id,'sampleSha256':_sha(p),'rootMidi':slot['rootMidi'],
                     'measurementPlaybackSampleRate':playback_rate,'notes':notes})
    risks=[]
    if events is not None:
        doc,_=_read(events);candidates=doc.get('candidates',doc.get('notes',[]))
        grouped=defaultdict(list)
        for event in candidates:
            slot_id=event.get('slot',value.get('roles',{}).get(event['family']))
            key=(slot_id,event.get('note'))
            if key not in lookup:raise ValueError('Event lacks a calibrated slot/tuning mapping')
            measured=lookup[key];duration=event['sourceEndSeconds']-event['sourceStartSeconds']
            if event.get('kind')!='retrigger' and duration>.5 and measured['energy95Seconds']<duration*.6:
                risks.append({'event':event['id'],'slot':slot_id,'kind':'sustain-underfill-candidate',
                              'sourceSeconds':duration,'sampleEnergy95Seconds':measured['energy95Seconds']})
            grouped[slot_id].append((event.get('q',event.get('gt',0))/20,measured['energy95Seconds'],event['id']))
        for slot_id,notes in grouped.items():
            notes.sort()
            for a,b in zip(notes,notes[1:]):
                if b[0]>a[0] and a[0]+a[1]>b[0]+.1:
                    risks.append({'slot':slot_id,'event':a[2],'nextEvent':b[2],
                                  'kind':'sample-overlap-candidate','overlapSeconds':a[0]+a[1]-b[0]})
    result={'schemaVersion':1,'profileId':value['id'],'slots':rows,'risks':risks,
            'all25NotesMeasured':True,'actualMinecraftRecording':False,'listeningVerified':False,
            'limitations':['Spectral peaks are candidates; overtones/formants can dominate the fundamental',
                           'Tail/overlap findings require phrase context; overlap is not automatically wrong',
                           'No measurement implements velocity, note-off or a looping game sampler']}
    if out:
        if Path(out).exists():raise ValueError('Refusing to overwrite range audit')
        _write(out,result)
    return result


def _mix(events, profile, begin, end):
    import numpy as np
    import soundfile as sf
    value,root=_read(profile);rate=RATE;tail=2.;audio=np.zeros(round((end-begin+tail)*rate),dtype=np.float32)
    solos={};cache={}
    for n in events['candidates']:
        start=n.get('q',n.get('gt',0))/20
        if start>=end:continue
        slot_id=n.get('slot',value.get('roles',{}).get(n['family']));slot=value['slots'][slot_id]
        key=slot_id,n['note']
        if key not in cache:
            p=Path(slot['sample']);p=p if p.is_absolute() else root/p
            data,sr=sf.read(p,dtype='float32');step=sr/rate*2**((n['note']-12)/12)
            cache[key]=np.interp(np.arange(0,len(data)-1,step),np.arange(len(data)),data)*slot.get('gain',1)
        wave=cache[key];cursor=round((start-begin)*rate)
        if cursor<0:wave=wave[-cursor:];cursor=0
        wave=wave[:max(0,len(audio)-cursor)]
        if not len(wave):continue
        audio[cursor:cursor+len(wave)]+=wave
        solo=solos.setdefault(n['family'],np.zeros_like(audio));solo[cursor:cursor+len(wave)]+=wave
    return audio,solos


def compare_timbres(source, palette_spec, out, begin=0, end=None):
    """Render same-note native/inspired, hybrid and body-first palettes at one gain."""
    import numpy as np
    import soundfile as sf
    from .music_tools import _score,plan_noteblocks
    value,root=_read(palette_spec);score=_score(source)
    begin=_number(begin,'begin',0,score['durationSeconds'])
    end=score['durationSeconds'] if end is None else _number(end,'end',0,score['durationSeconds'])
    if begin>=end or end-begin>120:raise ValueError('Choose a positive timbre comparison <=120 seconds')
    for slot in value.get('slots',{}).values():
        for field in ('attackSample','bodySample'):
            if field in slot.get('recipe',{}):
                sample=slot['recipe'][field];p=Path(sample['path']);sample['path']=str((p if p.is_absolute() else root/p).resolve(strict=True))
    folder=_new_dir(out);buffers={};reports={};reference_signature=None
    for variant in ('native','hybrid','body'):
        spec=deepcopy(value);spec['id']=value['id']+'_'+variant
        supplied=False
        for slot in spec['slots'].values():
            recipe=slot['recipe']
            if variant=='native':
                if 'attackSample' in recipe:
                    recipe['bodySample']=deepcopy(recipe['attackSample']);recipe['bodySample'].pop('seconds',None)
                    recipe['attackWeight']=0;recipe['bodyWeight']=1;supplied=True
                else:
                    recipe.pop('bodySample',None);recipe['kind']='bass' if slot['instrument']=='bass' else 'bell' if slot['instrument'] in ('bell','chime') else 'wood' if slot['instrument'] not in ('basedrum','snare','hat') else {'basedrum':'kick','snare':'snare','hat':'hat'}[slot['instrument']]
                    recipe['seconds']=.45 if recipe['kind'] not in ('bass','bell') else .7
                    recipe['attackWeight']=.35;recipe['bodyWeight']=.65
            elif variant=='body':recipe['attackWeight']=0;recipe['bodyWeight']=1
        bank=build_palette(spec,folder/variant)
        events=plan_noteblocks(score,profile=bank['profile'])
        signature=[(n['parentId'],n['gt'],n['sourceMidi'],n['note'],n['instrument'],n['kind']) for n in events['candidates']]
        if reference_signature is None:reference_signature=signature
        elif signature!=reference_signature:raise ValueError('Timbre comparison changed note/timing/slot decisions')
        _write(folder/variant/'events.json',events)
        audit_palette(bank['profile'],events,folder/variant/'phrase_audit.json')
        mix,solos=_mix(events,bank['profile'],begin,end);buffers[variant]=(mix,solos)
        reports[variant]={'profile':bank['profile'],'events':str(folder/variant/'events.json'),
                          'referenceKind':'supplied-local-sample' if variant=='native' and supplied else 'original-Minecraft-inspired-synthesis' if variant=='native' else 'recipe-hybrid' if variant=='hybrid' else 'body-first-recipe',
                          'eventsCount':len(events['candidates'])}
    peak=max(float(np.max(np.abs(audio))) for mix,solos in buffers.values() for audio in [mix,*solos.values()])
    gain=min(1,.89/max(peak,1e-12))
    for variant,(mix,solos) in buffers.items():
        path=folder/variant/'mix.wav';sf.write(path,np.stack([mix,mix],axis=1)*gain*.70710678,RATE,subtype='PCM_24')
        solo_paths={}
        for family,data in solos.items():
            p=folder/variant/(family+'_solo.wav');sf.write(p,np.stack([data,data],axis=1)*gain*.70710678,RATE,subtype='PCM_24');solo_paths[family]=str(p)
        reports[variant].update(mix=str(path),mixSha256=_sha(path),solos=solo_paths)
    result={'schemaVersion':1,'variants':reports,'beginSeconds':begin,'endSeconds':end,'tailSeconds':2,
            'oneCommonSafetyGain':gain,'soloGainMatchesMix':True,'noteDecisionsIdentical':True,
            'loudnessMatched':False,'actualMinecraftRecording':False,'spatialSimulation':False,'listeningVerified':False,
            'limitations':['Native without supplied sample is original MC-inspired synthesis, not stock Minecraft',
                           'Physical note-block preview ignores per-note MIDI velocity; balance is baked per slot',
                           'Use loudness-matched A/B as an additional view; retain these common-gain originals']}
    _write(folder/'comparison.json',result)
    return result


def create_timbre_study(out):
    """Original 20-second study: register 61..82, long voice, harmony/bass/drums."""
    import mido
    folder=_new_dir(out);midi=mido.MidiFile(type=1,ticks_per_beat=480)
    conductor=mido.MidiTrack([mido.MetaMessage('set_tempo',tempo=500000),mido.MetaMessage('time_signature',numerator=4,denominator=4)])
    conductor.append(mido.MetaMessage('end_of_track',time=40*480));midi.tracks.append(conductor)
    def track(name,channel,program,notes):
        tr=mido.MidiTrack([mido.MetaMessage('track_name',name=name),mido.Message('program_change',channel=channel,program=program)])
        events=[]
        for start,pitch,duration,velocity in notes:
            events.extend([(round(start*960),1,mido.Message('note_on',channel=channel,note=pitch,velocity=velocity)),(round((start+duration)*960),0,mido.Message('note_off',channel=channel,note=pitch,velocity=0))])
        previous=0
        for tick,_,message in sorted(events,key=lambda e:(e[0],e[1])):tr.append(message.copy(time=tick-previous));previous=tick
        tr.append(mido.MetaMessage('end_of_track',time=40*480-previous));midi.tracks.append(tr)
    motif=[61,64,68,73,76,80,82,80,76,73,68,64,66,69,73,78]
    track('Theme study',0,80,[(i*.5,motif[i%16],.38 if i<16 else .46,88+(i%4==0)*12) for i in range(32)]+[(16,73,1.6,94),(18,61,1.2,85)])
    track('Voice long tones',1,53,[(3,68,2.4,74),(9,73,2.7,80),(15,70,2.4,82)])
    track('Sub bass',2,33,[(i*2,[37,39,42,44][i%4],1.4,78) for i in range(10)])
    chords=[(61,65,68),(63,66,70),(61,66,70),(60,65,68)]
    track('Chords open',3,4,[(i*2,pitch,1.5,52) for i in range(10) for pitch in chords[i%4]])
    track('Drums',9,0,[(i*.5,36 if i%4==0 else 38 if i%4==2 else 42,.07,90 if i%4==0 else 58) for i in range(40)])
    midi.save(folder/'master.mid')
    settings=[('lead','banjo','hay_block',72,'pluck',1,.21,'theme_attack'),
              ('voice','flute','clay',72,'vowel',3.2,.14,'voice'),
              ('harmony','harp','dirt',66,'sustain',1.8,.075,'chords'),
              ('bass','bass','oak_planks',42,'bass',1.1,.18,'sub_bass'),
              ('kick','basedrum','stone',66,'kick',.3,.18,'kick'),
              ('snare','snare','sand',66,'snare',.22,.10,'snare'),
              ('hats','hat','glass',66,'hat',.12,.055,'hats')]
    slots={};roles={}
    for key,instrument,block,root,kind,seconds,gain,role in settings:
        slots[key]={'instrument':instrument,'baseBlock':'minecraft:'+block,'rootMidi':root,
                    'sustain':{'mode':'natural'},'recipe':{'schemaVersion':1,'rootMidi':root,'kind':kind,'seconds':seconds,'gain':gain,
                    'attackWeight':.24 if key=='lead' else .12,'bodyWeight':.88,'releaseSeconds':.06}}
        roles[role]=key
    spec={'schemaVersion':1,'id':'original_timbre_study','slots':slots,'roles':roles,
          'description':'Original CC0 recipe study; no stock Minecraft audio or third-party samples'}
    _write(folder/'palette_spec.json',spec)
    comparison=compare_timbres(folder/'master.mid',folder/'palette_spec.json',folder/'comparison')
    # A deliberately short continuous sample separates duration from retriggering.
    # The retry interval is derived from this sample's measured energy envelope,
    # not copied from one past work's five/six-GT setting.
    import shutil
    import numpy as np
    import soundfile as sf
    from .music_tools import plan_noteblocks
    short=deepcopy(spec);short['id']='original_sustain_study'
    short['slots']['voice']['recipe']['seconds']=.8
    natural=build_palette(short,folder/'sustain-natural')
    source_bank=Path(natural['profile']).parent
    repeat_bank=folder/'sustain-retrigger/bank'
    shutil.copytree(source_bank,repeat_bank)
    repeated=json.loads((repeat_bank/'profile.json').read_text(encoding='utf-8'))
    root_audit=audit_palette(natural['profile'])
    voice_audit=next(row for row in root_audit['slots'] if row['slot']=='voice')
    step=max(1,math.floor(voice_audit['notes'][12]['energy95Seconds']*.85*20))
    repeated['slots']['voice']['sustain']={'mode':'retrigger','stepGT':step}
    _write(repeat_bank/'profile.json',repeated)
    sustain_buffers={};sustain_report={}
    for name,profile in [('natural',Path(natural['profile'])),('retrigger',repeat_bank/'profile.json')]:
        events=plan_noteblocks(folder/'master.mid',profile=profile)
        parent=folder/('sustain-'+name)
        _write(parent/'events.json',events)
        audit_palette(profile,events,parent/'phrase_audit.json')
        mix,solos=_mix(events,profile,2.5,6)
        sustain_buffers[name]=(mix,solos['voice'])
        sustain_report[name]={'profile':str(profile),'events':str(parent/'events.json'),
            'onsets':sum(n['kind']=='onset' for n in events['candidates']),
            'retriggers':sum(n['kind']=='retrigger' for n in events['candidates'])}
    peak=max(float(np.max(np.abs(x))) for pair in sustain_buffers.values() for x in pair)
    common=min(1,.89/max(peak,1e-12))
    for name,(mix,solo) in sustain_buffers.items():
        parent=folder/('sustain-'+name)
        for key,data in [('mix',mix),('voice_solo',solo)]:
            path=parent/(key+'.wav');sf.write(path,np.stack([data,data],axis=1)*common*.70710678,RATE,subtype='PCM_24')
            sustain_report[name][key]=str(path)
    sustain={'variants':sustain_report,'oneCommonSafetyGain':common,'sameSampleBytes':True,
             'derivedRootIntervalGT':step,'intervalMethod':'85% of measured root-note energy95; pitch-dependent timing still needs review',
             'beginSeconds':2.5,'endSeconds':6,'actualMinecraftRecording':False,'listeningVerified':False}
    _write(folder/'sustain_comparison.json',sustain)
    result={'schemaVersion':1,'master':str(folder/'master.mid'),'paletteSpec':str(folder/'palette_spec.json'),
            'comparison':str(folder/'comparison/comparison.json'),'durationSeconds':20,'melodyRange':[61,82],
            'license':'CC0-1.0','listeningVerified':False,'variants':comparison['variants'],
            'sustainComparison':str(folder/'sustain_comparison.json')}
    _write(folder/'study.json',result)
    return result
