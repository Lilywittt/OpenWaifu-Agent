from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Callable

from sidecar_control import HttpSidecarSpec, start_http_sidecar, status_http_sidecar, stop_http_sidecar


@dataclass(frozen=True)
class HttpSidecarCli:
    parser_builder: Callable[[], argparse.ArgumentParser]
    spec_builder: Callable[[argparse.Namespace], HttpSidecarSpec]
    child_argv_builder: Callable[[argparse.Namespace], list[str]]
    foreground_runner: Callable[[argparse.Namespace], int]


def run_background_command(args: argparse.Namespace, cli: HttpSidecarCli) -> int:
    spec = cli.spec_builder(args)
    result = start_http_sidecar(
        spec,
        child_argv=cli.child_argv_builder(args),
        open_browser=bool(args.open_browser),
    )
    label = spec.label
    if not result["ok"]:
        print(f"[{label}] background start failed, check logs.", flush=True)
        print(f"[{label}] stdout={spec.stdout_log_path}", flush=True)
        print(f"[{label}] stderr={spec.stderr_log_path}", flush=True)
        return 1
    if result["alreadyRunning"]:
        print(f"[{label}] already running: {spec.browser_url}", flush=True)
        print(f"[{label}] pid={result['pid']}", flush=True)
        return 0
    print(f"[{label}] ready: {spec.browser_url}", flush=True)
    print(f"[{label}] pid={result['pid']}", flush=True)
    print(f"[{label}] stdout={spec.stdout_log_path}", flush=True)
    print(f"[{label}] stderr={spec.stderr_log_path}", flush=True)
    return 0


def run_status_command(args: argparse.Namespace, cli: HttpSidecarCli) -> int:
    spec = cli.spec_builder(args)
    status = status_http_sidecar(spec)
    label = spec.label
    print(f"[{label}] url={status['browserUrl']}")
    print(f"[{label}] healthy={status['healthy']}")
    print(f"[{label}] pid={status['pid']}")
    print(f"[{label}] pidAlive={status['pidAlive']}")
    return 0 if status["healthy"] else 1


def run_stop_command(args: argparse.Namespace, cli: HttpSidecarCli) -> int:
    spec = cli.spec_builder(args)
    result = stop_http_sidecar(spec)
    label = spec.label
    if result["stopped"]:
        print(f"[{label}] stopped")
        return 0
    print(f"[{label}] stop failed: listener still active")
    return 1


def run_restart_command(argv: list[str], cli: HttpSidecarCli) -> int:
    args = cli.parser_builder().parse_args(argv)
    stop_result = run_stop_command(args, cli)
    if stop_result != 0:
        return stop_result
    return run_background_command(args, cli)
