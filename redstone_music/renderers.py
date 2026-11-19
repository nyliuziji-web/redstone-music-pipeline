"""Actual GM rendering with a binary FluidSynth fallback, independent of a C compiler."""
from pathlib import Path
import math
import shutil
import subprocess
import tempfile


def _tiny(source, soundfont, rate, end, tail):
    import numpy as np
    import mido
    import tinysoundfont
    synth=tinysoundfont.Synth(gain=-8,samplerate=rate)
    bank=synth.sfload(str(soundfont),max_voices=256)
    for ch in range(16):synth.program_select(ch,bank,0,0,is_drums=ch==9)
    audio=np.zeros((round((end+tail)*rate),2),dtype=np.float32)
    cursor=0;elapsed=0.;active=set();stop=round(end*rate)
    for msg in mido.MidiFile(source):
        elapsed+=msg.time;target=min(stop,round(elapsed*rate))
        if target>cursor:
            audio[cursor:target]=np.frombuffer(synth.generate_simple(target-cursor),dtype=np.float32).reshape(-1,2)
            cursor=target
        if cursor==stop:break
        if msg.is_meta:continue
        if msg.type=='program_change':synth.program_change(msg.channel,msg.program,is_drums=msg.channel==9)
        elif msg.type=='control_change':synth.control_change(msg.channel,msg.control,msg.value)
        elif msg.type=='pitchwheel':synth.pitchbend(msg.channel,msg.pitch+8192)
        elif msg.type=='note_on' and msg.velocity:
            synth.noteon(msg.channel,msg.note,msg.velocity);active.add((msg.channel,msg.note))
        elif msg.type in ('note_on','note_off'):
            synth.noteoff(msg.channel,msg.note);active.discard((msg.channel,msg.note))
    if cursor<stop:audio[cursor:stop]=np.frombuffer(synth.generate_simple(stop-cursor),dtype=np.float32).reshape(-1,2)
    for ch in range(16):synth.control_change(ch,64,0)
    for ch,key in active:synth.noteoff(ch,key)
    audio[stop:]=np.frombuffer(synth.generate_simple(len(audio)-stop),dtype=np.float32).reshape(-1,2)
    return audio


def _bounded_midi(source,out,end,tail):
    """Preserve the original tempo/control timeline; never trigger notes in the tail."""
    import mido
    from .midi import parse_midi
    score=parse_midi(Path(source).read_bytes())
    def tempo_at(seconds):
        row=score['tempoMap'][0]
        for item in score['tempoMap']:
            if item['seconds']>seconds:break
            row=item
        return row
    tempo=tempo_at(end)
    ticks_per_second=score['ppq']*1_000_000/tempo['microsecondsPerQuarter']
    cutoff=round(tempo['tick']+(end-tempo['seconds'])*ticks_per_second)
    final=cutoff+round(tail*ticks_per_second)
    midi=mido.MidiFile(source); clipped=mido.MidiFile(type=1,ticks_per_beat=midi.ticks_per_beat)
    for original in midi.tracks:
        track=mido.MidiTrack();absolute=0;last=0
        for msg in original:
            absolute+=msg.time
            if absolute>cutoff:break
            if msg.type=='end_of_track' or absolute==cutoff and msg.type=='note_on' and msg.velocity:continue
            track.append(msg.copy(time=absolute-last));last=absolute
        track.append(mido.MetaMessage('end_of_track',time=max(0,final-last)))
        clipped.tracks.append(track)
    release=mido.MidiTrack()
    for ch in range(16):
        release.append(mido.Message('control_change',channel=ch,control=64,value=0,time=cutoff if ch==0 else 0))
        release.append(mido.Message('control_change',channel=ch,control=123,value=0,time=0))
    release.append(mido.MetaMessage('end_of_track',time=max(0,final-cutoff)))
    clipped.tracks.append(release);clipped.save(out)


def gm_buffer(source,soundfont,rate,end,tail=1.,engine='auto',fluidsynth=None):
    import numpy as np
    import soundfile as sf
    if engine not in ('auto','tinysoundfont','fluidsynth'):raise ValueError('Unknown GM renderer')
    if not math.isfinite(end) or not math.isfinite(tail) or end<=0 or tail<0:raise ValueError('Invalid GM interval')
    source=Path(source).resolve(strict=True);soundfont=Path(soundfont).resolve(strict=True)
    tiny_error=None
    if engine=='tinysoundfont' or engine=='auto' and not fluidsynth:
        try:
            return _tiny(source,soundfont,rate,end,tail),{'engine':'tinysoundfont','effects':'renderer defaults'}
        except (ImportError,OSError,RuntimeError) as error:
            tiny_error=str(error)
            if engine=='tinysoundfont':raise ValueError('TinySoundFont unavailable; use a supported Python wheel or the FluidSynth binary backend: '+tiny_error) from error
    executable=Path(fluidsynth).resolve(strict=True) if fluidsynth else shutil.which('fluidsynth')
    if not executable:
        raise ValueError('No GM renderer available. Install the render-tiny extra on supported Python, or supply --gm-engine fluidsynth --fluidsynth /path/to/fluidsynth. '+(tiny_error or ''))
    # Build scratch work under the user's working directory if a wheel installation
    # lives in a read-only site-packages directory.
    with tempfile.TemporaryDirectory(prefix='redstone-gm-') as folder:
        folder=Path(folder);bounded=folder/'clip.mid';wav=folder/'render.wav'
        _bounded_midi(source,bounded,end,tail)
        command=[str(executable),'-ni','-F',str(wav),'-T','wav','-r',str(rate),'-g','0.4',
                 '-o','synth.reverb.active=0','-o','synth.chorus.active=0',str(soundfont),str(bounded)]
        try:
            run=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=max(60,end*2+30))
        except subprocess.TimeoutExpired as error:
            raise ValueError('FluidSynth render timed out; try a shorter excerpt') from error
        if run.returncode or not wav.is_file():raise ValueError('FluidSynth rendering failed: '+run.stderr[-1000:])
        samples,sr=sf.read(wav,dtype='float32',always_2d=True)
    if sr!=rate or samples.shape[1]!=2 or not np.isfinite(samples).all():raise ValueError('Unexpected FluidSynth audio format')
    target=round((end+tail)*rate)
    if len(samples)<target:samples=np.pad(samples,((0,target-len(samples)),(0,0)))
    return samples[:target],{'engine':'fluidsynth','executable':str(executable),'effects':'reverb/chorus disabled',
                             'tinyFallbackReason':tiny_error}
