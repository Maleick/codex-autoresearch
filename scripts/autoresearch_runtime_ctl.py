from __future__ import annotations

import argparse

try:
    from scripts.autoresearch_helpers import (
        AutoresearchError,
        DEFAULT_LAUNCH_PATH,
        RunConfig,
        build_supervisor_snapshot,
        initialize_run,
        mark_background_active,
        print_json,
        resume_background_run,
        resolve_path,
        set_stop_requested,
        write_launch_manifest,
    )
except ModuleNotFoundError:
    from autoresearch_helpers import (
        AutoresearchError,
        DEFAULT_LAUNCH_PATH,
        RunConfig,
        build_supervisor_snapshot,
        initialize_run,
        mark_background_active,
        print_json,
        resume_background_run,
        resolve_path,
        set_stop_requested,
        write_launch_manifest,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Codex autoresearch background control artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    launch = subparsers.add_parser("launch", help="Initialize a background run and write the launch manifest.")
    launch.add_argument("--repo", help="Repository root. Defaults to the current working directory.")
    launch.add_argument("--results-path", help="Override the results TSV path.")
    launch.add_argument("--state-path", help="Override the state JSON path.")
    launch.add_argument("--launch-path", help="Override the launch manifest path.")
    launch.add_argument("--goal", required=True)
    launch.add_argument("--metric", required=True)
    launch.add_argument("--direction", required=True, choices=["lower", "higher"])
    launch.add_argument("--verify", required=True)
    launch.add_argument("--guard")
    launch.add_argument("--iterations", type=int)
    launch.add_argument("--run-tag")
    launch.add_argument("--stop-condition")
    launch.add_argument("--baseline")
    launch.add_argument("--fresh-start", action="store_true")

    status = subparsers.add_parser("status", help="Read the current background run status.")
    status.add_argument("--repo", help="Repository root. Defaults to the current working directory.")
    status.add_argument("--results-path", help="Override the results TSV path.")
    status.add_argument("--state-path", help="Override the state JSON path.")

    stop = subparsers.add_parser("stop", help="Request that the background run stop.")
    stop.add_argument("--repo", help="Repository root. Defaults to the current working directory.")
    stop.add_argument("--state-path", help="Override the state JSON path.")

    resume = subparsers.add_parser("resume", help="Resume a previously launched background run.")
    resume.add_argument("--repo", help="Repository root. Defaults to the current working directory.")
    resume.add_argument("--state-path", help="Override the state JSON path.")

    return parser


def command_launch(args: argparse.Namespace) -> dict:
    config = RunConfig(
        goal=args.goal,
        metric=args.metric,
        direction=args.direction,
        verify=args.verify,
        mode="background",
        guard=args.guard,
        iterations=args.iterations,
        run_tag=args.run_tag,
        stop_condition=args.stop_condition,
        baseline=args.baseline,
    )
    state = initialize_run(
        repo=args.repo,
        results_path_value=args.results_path,
        state_path_value=args.state_path,
        config=config,
        fresh_start=args.fresh_start,
    )
    launch = write_launch_manifest(
        repo=args.repo,
        launch_path_value=args.launch_path,
        config=config,
        results_path_value=args.results_path,
        state_path_value=args.state_path,
    )
    mark_background_active(repo=args.repo, state_path_value=args.state_path, active=True)
    return {
        "status": "launched",
        "launch_path": str(resolve_path(args.repo, args.launch_path, DEFAULT_LAUNCH_PATH)),
        "state": state,
        "launch_manifest": launch,
    }


def command_status(args: argparse.Namespace) -> dict:
    return build_supervisor_snapshot(
        repo=args.repo,
        results_path_value=args.results_path,
        state_path_value=args.state_path,
    )


def command_stop(args: argparse.Namespace) -> dict:
    state = set_stop_requested(repo=args.repo, state_path_value=args.state_path)
    return {
        "status": "stop_requested",
        "run_id": state["run_id"],
        "state": state,
    }


def command_resume(args: argparse.Namespace) -> dict:
    state = resume_background_run(repo=args.repo, state_path_value=args.state_path)
    return {
        "status": "resumed",
        "run_id": state["run_id"],
        "state": state,
    }


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "launch":
            payload = command_launch(args)
        elif args.command == "status":
            payload = command_status(args)
        elif args.command == "stop":
            payload = command_stop(args)
        elif args.command == "resume":
            payload = command_resume(args)
        else:
            parser.error(f"Unsupported command: {args.command}")
            return 2
    except AutoresearchError as exc:
        parser.error(str(exc))
        return 2

    print_json(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
