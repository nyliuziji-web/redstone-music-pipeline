"""Commands for music work before the reproducible build."""
import json
from pathlib import Path

from . import composition_tools as composition
from . import timbre_tools as timbre
from . import transcription_tools as audio


def add_renderer_options(parser):
    parser.add_argument('--gm-engine', choices=('auto', 'tinysoundfont', 'fluidsynth'), default='auto')
    parser.add_argument('--fluidsynth', help='Explicit FluidSynth executable')


def _render_options(args):
    return dict(soundfont=args.soundfont, gm_engine=args.gm_engine, fluidsynth=args.fluidsynth)


def _render_arguments(parser):
    parser.add_argument('--soundfont')
    add_renderer_options(parser)


def _interval(parser):
    parser.add_argument('--begin', type=float, default=0)
    parser.add_argument('--end', type=float)


def _recipe_commands(sub):
    tools = (
        ('design-timbre', 'recipe', timbre.design_timbre, 'Render one sound recipe'),
        ('build-palette', 'spec', timbre.build_palette, 'Build a calibrated palette and resource pack'),
        ('timbre-study', None, timbre.create_timbre_study, 'Generate the original Minecraft timbre comparison'),
    )
    for name, input_name, action, help_text in tools:
        p = sub.add_parser(name, help=help_text)
        if input_name:
            p.add_argument(input_name)
            p.add_argument('--out', required=True)
            p.set_defaults(_music_action=lambda a, k=input_name, f=action: f(getattr(a, k), a.out))
        else:
            p.add_argument('out')
            p.set_defaults(_music_action=lambda a, f=action: f(a.out))
    p = sub.add_parser('audit-palette', help='Check all tuning steps and event routing')
    p.add_argument('profile'); p.add_argument('--events'); p.add_argument('--out')
    p.set_defaults(_music_action=lambda a: timbre.audit_palette(a.profile, a.events, a.out))
    p = sub.add_parser('compare-timbres', help='Render one score through several palettes')
    p.add_argument('source'); p.add_argument('--palette', required=True); p.add_argument('--out', required=True)
    _interval(p)
    p.set_defaults(_music_action=lambda a: timbre.compare_timbres(a.source, a.palette, a.out, a.begin, a.end))


def _audio_commands(sub):
    group = sub.add_parser('audio', help='Local source separation, beat tracking and transcription candidates')
    commands = group.add_subparsers(dest='audio_command', required=True)
    p = commands.add_parser('capabilities')
    p.add_argument('--python')
    p.set_defaults(_music_action=lambda a: audio.transcription_capabilities(a.python))
    p = commands.add_parser('transcribe')
    p.add_argument('source'); p.add_argument('--out', required=True); p.add_argument('--python')
    p.add_argument('--backend', choices=('basic-pitch', 'muscriptor'), default='basic-pitch')
    p.add_argument('--model'); p.add_argument('--instrument', action='append')
    p.set_defaults(_music_action=lambda a: audio.transcribe_audio(
        a.source, a.out, a.backend, a.python, a.model, instruments=a.instrument))
    p = commands.add_parser('beats')
    p.add_argument('source'); p.add_argument('--out', required=True); p.add_argument('--python')
    p.add_argument('--checkpoint', required=True); p.add_argument('--model-dir')
    p.add_argument('--allow-download', action='store_true')
    p.set_defaults(_music_action=lambda a: audio.track_beats(
        a.source, a.out, a.checkpoint, a.python, a.model_dir, a.allow_download))
    p = commands.add_parser('separate')
    p.add_argument('source'); p.add_argument('--out', required=True); p.add_argument('--python')
    p.add_argument('--model', required=True); p.add_argument('--model-dir', required=True)
    p.add_argument('--allow-download', action='store_true')
    p.set_defaults(_music_action=lambda a: audio.separate_audio(
        a.source, a.out, a.model, a.model_dir, a.python, a.allow_download))
    p = commands.add_parser('compare')
    p.add_argument('reference'); p.add_argument('candidates', nargs='+'); p.add_argument('--out', required=True)
    _interval(p); _render_arguments(p)
    p.set_defaults(_music_action=lambda a: audio.compare_transcriptions(
        a.reference, a.candidates, a.out, a.begin, a.end, **_render_options(a)))


def _composition_commands(sub):
    group = sub.add_parser('composition', help='Edit and render an arrangement while protecting source notes')
    commands = group.add_subparsers(dest='composition_command', required=True)
    p = commands.add_parser('import')
    p.add_argument('midi'); p.add_argument('--out', required=True); p.add_argument('--roles')
    freeze = p.add_mutually_exclusive_group()
    freeze.add_argument('--freeze-role', action='append')
    freeze.add_argument('--no-freeze', action='store_true')
    p.set_defaults(_music_action=lambda a: composition.import_composition(
        a.midi, a.out, [] if a.no_freeze else a.freeze_role, a.roles))
    p = commands.add_parser('revise')
    p.add_argument('project'); p.add_argument('--patch', required=True); p.add_argument('--out', required=True)
    p.set_defaults(_music_action=lambda a: composition.revise_composition(a.project, a.patch, a.out))
    p = commands.add_parser('export')
    p.add_argument('project'); p.add_argument('--out', required=True)
    p.set_defaults(_music_action=lambda a: composition.export_composition(a.project, a.out))
    p = commands.add_parser('review')
    p.add_argument('project'); p.add_argument('--out')
    p.set_defaults(_music_action=lambda a: composition.review_composition(a.project, a.out))
    p = commands.add_parser('render')
    p.add_argument('project'); p.add_argument('--out', required=True); _render_arguments(p)
    p.set_defaults(_music_action=lambda a: composition.render_composition(a.project, a.out, **_render_options(a)))
    p = commands.add_parser('study')
    p.add_argument('out'); _render_arguments(p)
    p.set_defaults(_music_action=lambda a: composition.create_arrangement_study(a.out, **_render_options(a)))
    p = commands.add_parser('voicelead')
    p.add_argument('chords', nargs='+'); p.add_argument('--out'); p.add_argument('--against')
    p.add_argument('--voices', type=int, default=3)
    p.add_argument('--low', type=int, default=48); p.add_argument('--high', type=int, default=72)
    p.add_argument('--keep-root', action='store_true'); p.add_argument('--avoid-parallels', action='store_true')
    p.set_defaults(_music_action=lambda a: composition.plan_voicings(
        a.chords, a.out, a.voices, a.low, a.high,
        json.loads(Path(a.against).read_text(encoding='utf-8-sig')) if a.against else None,
        a.keep_root, a.avoid_parallels))


def add_music_commands(sub):
    _audio_commands(sub)
    _composition_commands(sub)
    _recipe_commands(sub)
