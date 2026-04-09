from __future__ import annotations

"""持续监听 QQ 私聊中的生成指令，触发产品运行并回发结果。"""

import argparse
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
TOOLS_DIR = Path(__file__).resolve().parent
SRC_DIR = PROJECT_DIR / "src"
for import_path in (TOOLS_DIR, SRC_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from common import configure_utf8_stdio

from publish.qq_bot_generate_service import (
    DEFAULT_HELP_COMMAND,
    DEFAULT_RECONNECT_DELAY_SECONDS,
    DEFAULT_STATUS_COMMAND,
    DEFAULT_TRIGGER_COMMAND,
    QQGenerateServiceAlreadyRunningError,
    qq_bot_generate_service_state_root,
    read_service_status,
    run_qq_bot_generate_service,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the QQ private-chat generate service. Send the trigger command in QQ DM to start one product run."
    )
    parser.add_argument("--config", default=str(PROJECT_DIR / "config" / "publish" / "qq_bot_message.json"))
    parser.add_argument("--trigger-command", default=DEFAULT_TRIGGER_COMMAND)
    parser.add_argument("--help-command", default=DEFAULT_HELP_COMMAND)
    parser.add_argument("--status-command", default=DEFAULT_STATUS_COMMAND)
    parser.add_argument("--wait-seconds", type=int, default=0)
    parser.add_argument("--ready-only", action="store_true")
    parser.add_argument("--reconnect-delay-seconds", type=float, default=DEFAULT_RECONNECT_DELAY_SECONDS)
    return parser


def log(message: str) -> None:
    print(message, flush=True)


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    state_root = qq_bot_generate_service_state_root(PROJECT_DIR)
    print(f"[qq-generate] 服务状态目录: {state_root}", flush=True)
    print(f"[qq-generate] 触发口令: {args.trigger_command}", flush=True)
    print(f"[qq-generate] 状态口令: {args.status_command}", flush=True)
    if args.ready_only:
        print("[qq-generate] 当前为 ready-only 模式。", flush=True)
    else:
        print("[qq-generate] 现在去 QQ 私聊机器人发送触发口令。", flush=True)
    try:
        run_qq_bot_generate_service(
            PROJECT_DIR,
            config_path=Path(args.config).resolve(),
            wait_seconds=args.wait_seconds,
            ready_only=args.ready_only,
            trigger_command=args.trigger_command,
            help_command=args.help_command,
            status_command=args.status_command,
            reconnect_delay_seconds=args.reconnect_delay_seconds,
            log=log,
        )
        return 0
    except KeyboardInterrupt:
        print("[qq-generate] 已收到退出请求，正在优雅关闭服务。", flush=True)
        return 0
    except QQGenerateServiceAlreadyRunningError as exc:
        print(f"[qq-generate] 后台服务已经在运行，pid={exc.pid}", flush=True)
        status = read_service_status(PROJECT_DIR)
        if status:
            print(f"[qq-generate] 当前状态: {status.get('status', 'unknown')}", flush=True)
            print(f"[qq-generate] 当前阶段: {status.get('stage', '')}", flush=True)
            run_id = str(status.get("runId", "")).strip()
            if run_id:
                print(f"[qq-generate] 当前 runId: {run_id}", flush=True)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
