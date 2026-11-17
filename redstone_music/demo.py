"""Original CC0 eight-second demo phrase, generated without external assets."""
from pathlib import Path
import struct

from .core import initialize, load_config, atomic_json


def _vlq(value):
    values = [value & 127]
    value >>= 7
    while value:
        values.insert(0, (value & 127) | 128)
        value >>= 7
    return bytes(values)


def demo_midi_bytes():
    conductor = [(0, b'\xff\x51\x03\x07\xa1\x20'), (0, b'\xff\x06\x05INTRO'),
                 (3840, b'\xff\x06\x04TAIL'), (3840, b'\xff\x2f\x00')]
    melody = [(0, b'\xff\x03\x05Theme'), (0, bytes([0xC0, 80]))]
    for i, pitch in enumerate((60, 64, 67, 72, 71, 67, 64, 60)):
        melody.extend([(0 if i == 0 else 120, bytes([0x90, pitch, 92])),
                       (840, bytes([0x80, pitch, 0]))])
    melody.append((120, b'\xff\x2f\x00'))
    bass = [(0, bytes([0xC1, 33])), (0, bytes([0x91, 36, 75])),
            (3840, bytes([0x81, 36, 0])), (0, bytes([0x91, 43, 75])),
            (3840, bytes([0x81, 43, 0]))]
    chunks = []
    for events in (conductor, melody, bass):
        raw = b''.join(_vlq(delta) + payload for delta, payload in events)
        if not raw.endswith(b'\xff\x2f\x00'):
            raw += b'\x00\xff\x2f\x00'
        chunks.append(b'MTrk' + struct.pack('>I', len(raw)) + raw)
    return b'MThd' + struct.pack('>IHHH', 6, 1, 3, 480) + b''.join(chunks)


def initialize_demo(project):
    project = Path(project).resolve()
    if project.exists():
        load_config(project)  # resume an existing project, never overwrite its sources/configuration
        return project
    initialize(project, title='Original C-major Demo')
    source = project / 'sources/demo.mid'
    source.write_bytes(demo_midi_bytes())
    config = load_config(project)
    config['inputs']['midi'] = 'sources/demo.mid'
    atomic_json(project / 'project.json', config)
    return project
