"""Small command line conductor; all outputs are structured JSON."""
import argparse
import json
import sys
from .core import (PipelineError, STAGES, ROLES, initialize, run_pipeline, status,
                   list_tasks, create_task, claim_task, complete_task, doctor, summarize_run)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m redstone_music")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Create a new independent project")
    init.add_argument("project")
    init.add_argument("--title")
    init.add_argument("--slug")
    init.add_argument("--midi")
    init.add_argument("--approved-events")
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
    args = parser.parse_args(argv)
    try:
        if args.command == "build-trace":
            from .trace import build
            result = build(args.jdk, args.asm, args.out)
        elif args.command == "init":
            result = initialize(args.project, args.title, args.midi, args.approved_events, args.slug)
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
            result = create_task(args.project, args.role, args.objective)
        elif args.command == "claim-task":
            result = claim_task(args.project, args.task_id, args.agent)
        elif args.command == "complete-task":
            result = complete_task(args.project, args.task_id, args.result)
        else:
            result = doctor(args.project)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (PipelineError, OSError, ValueError, KeyError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
