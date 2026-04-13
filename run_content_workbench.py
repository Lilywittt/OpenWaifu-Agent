from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sidecar_control import (
    HttpSidecarSpec,
    sidecar_logs_root,
)
from http_sidecar_cli import (
    HttpSidecarCli,
    run_background_command,
    run_restart_command,
    run_status_command,
    run_stop_command,
)
from studio.content_workbench_service import (
    content_workbench_browser_url,
    fetch_existing_content_workbench_health,
    run_content_workbench_server,
)
from studio.content_workbench_store import (
    DEFAULT_CLEANUP_OLDER_THAN_DAYS,
    delete_workbench_run,
    generate_cleanup_report,
    migrate_legacy_content_workbench_state,
    workbench_inventory_paths,
)
from studio.content_workbench_worker import run_content_workbench_worker


def _configure_utf8_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _workbench_log_paths(project_dir: Path) -> tuple[Path, Path]:
    log_dir = sidecar_logs_root(project_dir, "content_workbench")
    return (
        log_dir / "server.stdout.log",
        log_dir / "server.stderr.log",
    )


def _build_sidecar_spec(args: argparse.Namespace) -> HttpSidecarSpec:
    stdout_path, stderr_path = _workbench_log_paths(PROJECT_DIR)
    return HttpSidecarSpec(
        sidecar_id="content_workbench",
        label="content-workbench",
        project_dir=PROJECT_DIR,
        browser_url=content_workbench_browser_url(args.host, args.port),
        port=int(args.port),
        stdout_log_path=stdout_path,
        stderr_log_path=stderr_path,
        fetch_health=fetch_existing_content_workbench_health,
    )


def _build_cli() -> HttpSidecarCli:
    return HttpSidecarCli(
        parser_builder=build_parser,
        spec_builder=_build_sidecar_spec,
        child_argv_builder=_background_child_argv,
        foreground_runner=_run_foreground,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local content workbench.")
    parser.add_argument("--foreground", action="store_true", help="Run in the current process for debugging.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--refresh-seconds", type=int, default=5)
    parser.add_argument("--history-limit", type=int, default=10)
    parser.add_argument("--open-browser", dest="open_browser", action="store_true")
    parser.add_argument("--no-open-browser", dest="open_browser", action="store_false")
    parser.set_defaults(open_browser=True)
    return parser


def _build_cleanup_report_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a cleanup report for content-workbench runs.")
    parser.add_argument("--older-than-days", type=int, default=DEFAULT_CLEANUP_OLDER_THAN_DAYS)
    parser.add_argument(
        "--statuses",
        nargs="*",
        default=["completed", "failed", "interrupted"],
        help="Run statuses to include in the cleanup report.",
    )
    return parser


def _build_delete_run_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Delete a specific content-workbench run directory.")
    parser.add_argument("--run-id", required=True)
    return parser


def _build_worker_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the content-workbench worker.")
    parser.add_argument("--request-id", default="")
    return parser


def _background_child_argv(args: argparse.Namespace) -> list[str]:
    return [
        str(Path(sys.executable).resolve()),
        str(PROJECT_DIR / "run_content_workbench.py"),
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
    run_content_workbench_server(
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


def _run_inventory() -> int:
    migrate_legacy_content_workbench_state(PROJECT_DIR)
    paths = workbench_inventory_paths(PROJECT_DIR)
    print("[content-workbench] inventory")
    print(f"stateRoot={paths['stateRoot']}")
    print(f"serverProcessPath={paths['serverProcessPath']}")
    print(f"generationSlot={paths['generationSlotPath']}")
    print(f"runIndexJsonl={paths['runIndexJsonlPath']}")
    print(f"runIndexCsv={paths['runIndexCsvPath']}")
    print(f"cleanupReportJson={paths['cleanupReportJsonPath']}")
    print(f"cleanupReportCsv={paths['cleanupReportCsvPath']}")
    print(
        "[content-workbench] cleanupCommand="
        f"python run_content_workbench.py cleanup-report --older-than-days {DEFAULT_CLEANUP_OLDER_THAN_DAYS}"
    )
    return 0


def _run_cleanup_report(argv: list[str]) -> int:
    parser = _build_cleanup_report_parser()
    args = parser.parse_args(argv)
    migrate_legacy_content_workbench_state(PROJECT_DIR)
    report = generate_cleanup_report(
        PROJECT_DIR,
        older_than_days=args.older_than_days,
        statuses=tuple(str(item) for item in args.statuses),
    )
    print("[content-workbench] cleanup report generated")
    print(f"candidateCount={report['candidateCount']}")
    print(f"indexJsonl={report['indexJsonlPath']}")
    print(f"indexCsv={report['indexCsvPath']}")
    paths = workbench_inventory_paths(PROJECT_DIR)
    print(f"cleanupReportJson={paths['cleanupReportJsonPath']}")
    print(f"cleanupReportCsv={paths['cleanupReportCsvPath']}")
    return 0


def _run_delete_run(argv: list[str]) -> int:
    parser = _build_delete_run_parser()
    args = parser.parse_args(argv)
    migrate_legacy_content_workbench_state(PROJECT_DIR)
    deleted = delete_workbench_run(PROJECT_DIR, args.run_id)
    print("[content-workbench] deleted run directory")
    print(f"runId={deleted['runId']}")
    print(f"runRoot={deleted['runRoot']}")
    print(f"deletedAt={deleted['deletedAt']}")
    return 0


def _run_worker(argv: list[str]) -> int:
    args = _build_worker_parser().parse_args(argv)
    migrate_legacy_content_workbench_state(PROJECT_DIR)
    return run_content_workbench_worker(PROJECT_DIR, request_id=args.request_id)


def main(argv: list[str] | None = None) -> int:
    _configure_utf8_stdio()
    args_list = list(argv if argv is not None else sys.argv[1:])
    if args_list:
        command = args_list[0].strip().lower()
        if command == "inventory":
            return _run_inventory()
        if command == "status":
            return _run_status(build_parser().parse_args(args_list[1:]))
        if command == "stop":
            return _run_stop(build_parser().parse_args(args_list[1:]))
        if command == "restart":
            return _run_restart(args_list[1:])
        if command == "cleanup-report":
            return _run_cleanup_report(args_list[1:])
        if command == "delete-run":
            return _run_delete_run(args_list[1:])
        if command == "worker":
            return _run_worker(args_list[1:])

    args = build_parser().parse_args(args_list)
    if args.foreground:
        return _run_foreground(args)
    return _run_background(args)


if __name__ == "__main__":
    raise SystemExit(main())
