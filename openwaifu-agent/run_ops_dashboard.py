from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ops.dashboard_service import (
    dashboard_browser_url,
    fetch_existing_dashboard_health,
    run_dashboard_server,
)
from http_sidecar_cli import (
    HttpSidecarCli,
    run_background_command,
    run_restart_command,
    run_status_command,
    run_stop_command,
)
from sidecar_control import (
    HttpSidecarSpec,
    sidecar_logs_root,
)


def _configure_utf8_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _dashboard_log_paths(project_dir: Path) -> tuple[Path, Path]:
    log_dir = sidecar_logs_root(project_dir, "ops_dashboard")
    return (
        log_dir / "server.stdout.log",
        log_dir / "server.stderr.log",
    )


def _build_sidecar_spec(args: argparse.Namespace) -> HttpSidecarSpec:
    stdout_path, stderr_path = _dashboard_log_paths(PROJECT_DIR)
    return HttpSidecarSpec(
        sidecar_id="ops_dashboard",
        label="ops-dashboard",
        project_dir=PROJECT_DIR,
        browser_url=dashboard_browser_url(args.host, args.port),
        port=int(args.port),
        stdout_log_path=stdout_path,
        stderr_log_path=stderr_path,
        fetch_health=fetch_existing_dashboard_health,
    )


def _build_cli() -> HttpSidecarCli:
    return HttpSidecarCli(
        parser_builder=build_parser,
        spec_builder=_build_sidecar_spec,
        child_argv_builder=_background_child_argv,
        foreground_runner=_run_foreground,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local operations dashboard.")
    parser.add_argument("--foreground", action="store_true", help="Run in the current process for debugging.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--refresh-seconds", type=int, default=5)
    parser.add_argument("--queue-limit", type=int, default=20)
    parser.add_argument("--recent-job-limit", type=int, default=12)
    parser.add_argument("--event-limit", type=int, default=40)
    parser.add_argument("--run-limit", type=int, default=8)
    parser.add_argument("--log-tail-lines", type=int, default=30)
    parser.add_argument("--open-browser", dest="open_browser", action="store_true")
    parser.add_argument("--no-open-browser", dest="open_browser", action="store_false")
    parser.set_defaults(open_browser=True)
    return parser


def _background_child_argv(args: argparse.Namespace) -> list[str]:
    return [
        str(Path(sys.executable).resolve()),
        str(PROJECT_DIR / "run_ops_dashboard.py"),
        "--foreground",
        "--host",
        str(args.host),
        "--port",
        str(args.port),
        "--refresh-seconds",
        str(args.refresh_seconds),
        "--queue-limit",
        str(args.queue_limit),
        "--recent-job-limit",
        str(args.recent_job_limit),
        "--event-limit",
        str(args.event_limit),
        "--run-limit",
        str(args.run_limit),
        "--log-tail-lines",
        str(args.log_tail_lines),
        "--no-open-browser",
    ]


def _run_foreground(args: argparse.Namespace) -> int:
    run_dashboard_server(
        PROJECT_DIR,
        host=args.host,
        port=args.port,
        refresh_seconds=args.refresh_seconds,
        queue_limit=args.queue_limit,
        recent_job_limit=args.recent_job_limit,
        event_limit=args.event_limit,
        run_limit=args.run_limit,
        log_tail_lines=args.log_tail_lines,
        open_browser=bool(args.open_browser),
    )
    return 0


def _run_background(args: argparse.Namespace) -> int:
    return run_background_command(args, cli=_build_cli())


def _run_status(args: argparse.Namespace) -> int:
    return run_status_command(args, cli=_build_cli())


def _run_stop(args: argparse.Namespace) -> int:
    return run_stop_command(args, cli=_build_cli())


def _run_restart(argv: list[str]) -> int:
    return run_restart_command(argv, cli=_build_cli())


def main(argv: list[str] | None = None) -> int:
    _configure_utf8_stdio()
    args_list = list(argv if argv is not None else sys.argv[1:])
    if args_list:
        command = args_list[0].strip().lower()
        if command == "status":
            return _run_status(build_parser().parse_args(args_list[1:]))
        if command == "stop":
            return _run_stop(build_parser().parse_args(args_list[1:]))
        if command == "restart":
            return _run_restart(args_list[1:])

    args = build_parser().parse_args(args_list)
    if args.foreground:
        return _run_foreground(args)
    return _run_background(args)


if __name__ == "__main__":
    raise SystemExit(main())
