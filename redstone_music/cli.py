"""Small command line conductor; all outputs are structured JSON."""
import argparse
import json
import sys
from .core import (PipelineError, STAGES, ROLES, initialize, run_pipeline, status,
                   list_tasks, create_task, claim_task, complete_task, doctor, summarize_run, TASK_KINDS)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m redstone_music")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Create a new independent project")
    init.add_argument("project")
    init.add_argument("--title")
    init.add_argument("--slug")
    init.add_argument("--midi")
    init.add_argument("--approved-events")
    init.add_argument("--reference-audio", help="Local reference recording for the music task")
    run = sub.add_parser("run", help="Build or resume the pipeline")
    run.add_argument("project")
    run.add_argument("--until", choices=STAGES, default="release")
    run.add_argument("--force", action="store_true")
    demo = sub.add_parser('demo', help='Build or resume the original eight-second demonstration')
    demo.add_argument('--project', default='projects/demo')
    demo.add_argument('--until', choices=STAGES, default='release')
    for command in ("status", "tasks"):
        sub.add_parser(command).add_argument("project")
    task = sub.add_parser("create-task", help="Create a constrained specialist review or repair task")
    task.add_argument("project")
    task.add_argument("--role", choices=ROLES, required=True)
    task.add_argument("--objective", required=True)
    task.add_argument('--kind', choices=TASK_KINDS, default='review')
    claim = sub.add_parser("claim-task")
    claim.add_argument("project")
    claim.add_argument("task_id")
    claim.add_argument("--agent", required=True)
    complete = sub.add_parser("complete-task")
    complete.add_argument("project")
    complete.add_argument("task_id")
    complete.add_argument("--result", required=True)
    diagnose = sub.add_parser("doctor")
    diagnose.add_argument("project", nargs="?")
    trace = sub.add_parser("build-trace", help="Build the optional real-server test observer")
    trace.add_argument("--jdk", required=True)
    trace.add_argument("--asm", required=True)
    trace.add_argument("--out", required=True)
    caps = sub.add_parser('capabilities', help='Probe installed capabilities without downloading or launching games')
    caps.add_argument('--project')
    caps.add_argument('--probe', action='store_true')
    sub.add_parser('learn', help='Generate original learning music, profiles and failure cases').add_argument('out')
    for command in ('inspect-source', 'analyze-music', 'analyze-audio'):
        p = sub.add_parser(command)
        p.add_argument('source')
        p.add_argument('--out')
        if command == 'analyze-music':
            p.add_argument('--backend', choices=('builtin', 'music21', 'auto'), default='builtin')
    p = sub.add_parser('transcribe-melody'); p.add_argument('source'); p.add_argument('--out', required=True)
    p = sub.add_parser('edit-music-region')
    p.add_argument('source'); p.add_argument('--patch', required=True); p.add_argument('--out', required=True)
    p = sub.add_parser('plan-noteblocks')
    p.add_argument('source'); p.add_argument('--out', required=True); p.add_argument('--profile')
    p.add_argument('--adaptation-plan', help='Apply explicit reviewed note-to-slot decisions')
    p.add_argument('--consistency', choices=('role', 'phrase'), default='role')
    p = sub.add_parser('build-soundpack')
    p.add_argument('spec'); p.add_argument('--out', required=True)
    p = sub.add_parser('render-preview')
    p.add_argument('source'); p.add_argument('--out', required=True)
    p.add_argument('--mode', choices=('reference', 'gm', 'noteblock'), default='reference')
    p.add_argument('--soundfont'); p.add_argument('--profile')
    from .music_cli import add_music_commands, add_renderer_options
    add_renderer_options(p)
    p.add_argument('--begin', type=float, default=0); p.add_argument('--end', type=float)
    p = sub.add_parser('compare-candidates')
    p.add_argument('a'); p.add_argument('b'); p.add_argument('--out', required=True)
    p = sub.add_parser('preview-stage')
    p.add_argument('blueprint'); p.add_argument('--out', required=True); p.add_argument('--protection')
    p = sub.add_parser('compile-show')
    p.add_argument('score'); p.add_argument('--out', required=True); p.add_argument('--style')
    game = sub.add_parser('game').add_subparsers(dest='game_command', required=True)
    for command in ('inspect', 'import', 'build-client'):
        p = game.add_parser(command)
        p.add_argument('source'); p.add_argument('--java')
        if command != 'inspect': p.add_argument('--out', required=True)
        if command == 'build-client': p.add_argument('--gradle')
    p = sub.add_parser('brief'); p.add_argument('project'); p.add_argument('--text', required=True)
    p = sub.add_parser('decision'); p.add_argument('project'); p.add_argument('--summary', required=True); p.add_argument('--reason', required=True)
    p = sub.add_parser('review'); p.add_argument('project'); p.add_argument('--file', required=True)
    sub.add_parser('handoff').add_argument('project')
    sub.add_parser('bundle-check').add_argument('--root')
    p = sub.add_parser('bundle-export'); p.add_argument('out'); p.add_argument('--root')
    p = sub.add_parser('validate-contract'); p.add_argument('name'); p.add_argument('file')
    p = sub.add_parser('calibrate-profile'); p.add_argument('profile'); p.add_argument('--out')
    p = sub.add_parser('inspect-media'); p.add_argument('source'); p.add_argument('--out')
    p = sub.add_parser('clip-media'); p.add_argument('source'); p.add_argument('--out',required=True); p.add_argument('--begin',required=True,type=float); p.add_argument('--end',required=True,type=float)
    p = sub.add_parser('capture-evidence'); p.add_argument('project'); p.add_argument('source'); p.add_argument('--out',required=True); p.add_argument('--kind',choices=('sample','full'),default='sample')
    p = sub.add_parser('photon-plan'); p.add_argument('show'); p.add_argument('--out',required=True); p.add_argument('--mod-jar',required=True)
    add_music_commands(sub)
    args = parser.parse_args(argv)
    try:
        if hasattr(args, '_music_action'):
            result = args._music_action(args)
        elif args.command == 'capabilities':
            from .kit import capabilities
            result = capabilities(args.project, args.probe)
        elif args.command == 'calibrate-profile':
            from .music_tools import calibrate_sound_profile
            result = calibrate_sound_profile(args.profile,args.out)
        elif args.command == 'photon-plan':
            from .game_tools import plan_photon_comparison
            result = plan_photon_comparison(args.show,args.out,args.mod_jar)
        elif args.command in ('inspect-media','clip-media','capture-evidence'):
            from . import media_tools as mt
            if args.command == 'inspect-media': result = mt.inspect_media(args.source,args.out)
            elif args.command == 'clip-media': result = mt.clip_media(args.source,args.out,args.begin,args.end)
            else: result = mt.capture_evidence(args.project,args.source,args.out,args.kind)
        elif args.command == 'bundle-export':
            from .kit import export_bundle
            result = export_bundle(args.out,args.root)
        elif args.command == 'learn':
            from .toolkit_examples import create_learning_example
            result = create_learning_example(args.out)
        elif args.command in ('inspect-source', 'analyze-music', 'analyze-audio', 'transcribe-melody', 'edit-music-region', 'plan-noteblocks', 'build-soundpack', 'render-preview', 'compare-candidates'):
            from . import music_tools as mt
            if args.command == 'inspect-source': result = mt.inspect_source(args.source, args.out)
            elif args.command == 'analyze-music': result = mt.analyze_music(args.source, args.out, args.backend)
            elif args.command == 'analyze-audio': result = mt.analyze_audio(args.source, args.out)
            elif args.command == 'transcribe-melody': result = mt.transcribe_melody(args.source, args.out)
            elif args.command == 'edit-music-region': result = mt.edit_music_region(args.source, args.patch, args.out)
            elif args.command == 'plan-noteblocks': result = mt.plan_noteblocks(
                args.source, args.out, args.profile, args.adaptation_plan, args.consistency)
            elif args.command == 'build-soundpack': result = mt.build_soundpack(args.spec, args.out)
            elif args.command == 'render-preview': result = mt.render_preview(args.source, args.out, args.mode, args.soundfont, args.profile, args.begin, args.end, args.gm_engine, args.fluidsynth)
            else: result = mt.compare_candidates(args.a, args.b, args.out)
        elif args.command in ('preview-stage', 'compile-show'):
            from . import stage_tools as st
            result = st.preview_stage(args.blueprint, args.out, args.protection) if args.command == 'preview-stage' else st.compile_show(args.score, args.out, args.style)
        elif args.command == 'game':
            from . import game_tools as gt
            if args.game_command == 'inspect': result = gt.inspect_game(args.source, args.java)
            elif args.game_command == 'import': result = gt.import_game(args.source, args.out, args.java)
            else: result = gt.build_client(args.source, args.out, args.java, args.gradle)
        elif args.command in ('brief', 'decision', 'review', 'handoff', 'bundle-check'):
            from . import kit
            if args.command == 'brief': result = kit.set_brief(args.project, args.text)
            elif args.command == 'decision': result = kit.record_decision(args.project, args.summary, args.reason)
            elif args.command == 'review': result = kit.record_review(args.project, args.file)
            elif args.command == 'handoff': result = kit.handoff(args.project)
            else: result = kit.bundle_check(args.root)
        elif args.command == 'validate-contract':
            from .contracts import validate_contract
            from .core import read_json
            result = validate_contract(read_json(args.file), args.name)
        elif args.command == "build-trace":
            from .trace import build
            result = build(args.jdk, args.asm, args.out)
        elif args.command == "init":
            result = initialize(args.project, args.title, args.midi, args.approved_events, args.slug, args.reference_audio)
        elif args.command == "run":
            result = summarize_run(args.project, run_pipeline(args.project, args.until, args.force))
        elif args.command == 'demo':
            from .demo import initialize_demo
            project = initialize_demo(args.project)
            result = summarize_run(project, run_pipeline(project, args.until))
        elif args.command == "status":
            result = status(args.project)
        elif args.command == "tasks":
            result = list_tasks(args.project)
        elif args.command == "create-task":
            result = create_task(args.project, args.role, args.objective, args.kind)
        elif args.command == "claim-task":
            result = claim_task(args.project, args.task_id, args.agent)
        elif args.command == "complete-task":
            result = complete_task(args.project, args.task_id, args.result)
        else:
            result = doctor(args.project)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 2 if args.command == 'bundle-check' and not result['valid'] else 0
    except (RuntimeError, OSError, ValueError, KeyError, ImportError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
