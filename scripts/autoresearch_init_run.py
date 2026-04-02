from __future__ import annotations

import argparse

try:
    from scripts.autoresearch_helpers import AutoresearchError, RunConfig, initialize_run, print_json
except ModuleNotFoundError:
    from autoresearch_helpers import AutoresearchError, RunConfig, initialize_run, print_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Initialize Codex autoresearch state and results artifacts.")
    parser.add_argument("--repo", help="Repository root. Defaults to the current working directory.")
    parser.add_argument("--results-path", help="Override the results TSV path.")
    parser.add_argument("--state-path", help="Override the state JSON path.")
    parser.add_argument("--goal", required=True, help="Human-readable outcome for the run.")
    parser.add_argument("--metric", required=True, help="Metric name tracked during the run.")
    parser.add_argument("--direction", required=True, choices=["lower", "higher"], help="Preferred metric direction.")
    parser.add_argument("--verify", required=True, help="Mechanical verify command.")
    parser.add_argument("--mode", default="foreground", choices=["foreground", "background"], help="Run mode.")
    parser.add_argument("--guard", help="Optional guard command.")
    parser.add_argument("--iterations", type=int, help="Optional iteration cap.")
    parser.add_argument("--run-tag", help="Optional human-readable run tag.")
    parser.add_argument("--stop-condition", help="Optional textual stop condition.")
    parser.add_argument("--baseline", help="Optional baseline metric value.")
    parser.add_argument("--fresh-start", action="store_true", help="Archive previous artifacts before initializing.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config = RunConfig(
        goal=args.goal,
        metric=args.metric,
        direction=args.direction,
        verify=args.verify,
        mode=args.mode,
        guard=args.guard,
        iterations=args.iterations,
        run_tag=args.run_tag,
        stop_condition=args.stop_condition,
        baseline=args.baseline,
    )
    try:
        payload = initialize_run(
            repo=args.repo,
            results_path_value=args.results_path,
            state_path_value=args.state_path,
            config=config,
            fresh_start=args.fresh_start,
        )
    except AutoresearchError as exc:
        parser.error(str(exc))
        return 2

    print_json(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
