from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from http_sidecar_cli import (
    HttpSidecarCli,
    run_background_command,
    run_restart_command,
    run_status_command,
    run_stop_command,
)
from public_web.entry import (
    fetch_existing_public_workbench_health,
    public_workbench_browser_url,
    run_public_workbench_server,
)
from sidecar_control import HttpSidecarSpec, sidecar_logs_root
from workbench.profile import PUBLIC_PROFILE, load_workbench_runtime_settings
from workbench.worker import run_workbench_worker


def _configure_utf8_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


DEFAULT_SETTINGS = load_workbench_runtime_settings(PROJECT_DIR, PUBLIC_PROFILE)


def _workbench_log_paths(project_dir: Path) -> tuple[Path, Path]:
    log_dir = sidecar_logs_root(project_dir, PUBLIC_PROFILE.sidecar_id)
    return (log_dir / "server.stdout.log", log_dir / "server.stderr.log")


def _build_sidecar_spec(args: argparse.Namespace) -> HttpSidecarSpec:
    stdout_path, stderr_path = _workbench_log_paths(PROJECT_DIR)
    return HttpSidecarSpec(
        sidecar_id=PUBLIC_PROFILE.sidecar_id,
        label="public-workbench",
        project_dir=PROJECT_DIR,
        browser_url=public_workbench_browser_url(args.host, args.port),
        port=int(args.port),
        stdout_log_path=stdout_path,
        stderr_log_path=stderr_path,
        fetch_health=fetch_existing_public_workbench_health,
    )


def _build_cli() -> HttpSidecarCli:
    return HttpSidecarCli(
        parser_builder=build_parser,
        spec_builder=_build_sidecar_spec,
        child_argv_builder=_background_child_argv,
        foreground_runner=_run_foreground,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the public content workbench.")
    parser.add_argument("--foreground", action="store_true", help="Run in the current process for debugging.")
    parser.add_argument("--host", default=DEFAULT_SETTINGS.host)
    parser.add_argument("--port", type=int, default=DEFAULT_SETTINGS.port)
    parser.add_argument("--refresh-seconds", type=int, default=DEFAULT_SETTINGS.refresh_seconds)
    parser.add_argument("--history-limit", type=int, default=DEFAULT_SETTINGS.history_limit)
    parser.add_argument("--open-browser", dest="open_browser", action="store_true")
    parser.add_argument("--no-open-browser", dest="open_browser", action="store_false")
    parser.set_defaults(open_browser=DEFAULT_SETTINGS.open_browser)
    return parser


def _build_worker_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the shared workbench worker.")
    parser.add_argument("--request-id", default="")
    return parser


def _background_child_argv(args: argparse.Namespace) -> list[str]:
    return [
        str(Path(sys.executable).resolve()),
        str(PROJECT_DIR / "run_public_workbench.py"),
        "--foreground",
        "--host",
        str(args.host),
        "--port",
        str(args.port),
        "--refresh-seconds",
        str(args.refresh_seconds),
        "--history-limit",
        str(args.history_limit),
        "--no-open-browser",
    ]


def _run_foreground(args: argparse.Namespace) -> int:
    run_public_workbench_server(
        PROJECT_DIR,
        host=args.host,
        port=args.port,
        refresh_seconds=args.refresh_seconds,
        history_limit=args.history_limit,
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


def _run_worker(argv: list[str]) -> int:
    args = _build_worker_parser().parse_args(argv)
    return run_workbench_worker(PROJECT_DIR, request_id=args.request_id)


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
        if command == "worker":
            return _run_worker(args_list[1:])
    args = build_parser().parse_args(args_list)
    if args.foreground:
        return _run_foreground(args)
    return _run_background(args)


if __name__ == "__main__":
    raise SystemExit(main())
