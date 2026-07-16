#!/usr/bin/env python3
"""Idempotently configure the local side of Goal Ledger's Secure MCP Tunnel."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
BRIDGE_SCRIPT = SCRIPT_DIR / "run_review_bridge.py"
PROFILE_NAME = "goal-ledger-planning"
RUNTIME_ALIAS = "goal-ledger"
KEYCHAIN_SERVICE = "codex-goal-ledger-tunnel-client"
TUNNEL_ID_PATTERN = re.compile(r"^tunnel_[A-Za-z0-9]+$")
CONNECTOR_ID_PATTERN = re.compile(r"^asdk_app_[A-Za-z0-9]+$")


class SetupError(RuntimeError):
    """Raised when the safe bootstrap cannot complete."""


@dataclass(frozen=True)
class SetupPaths:
    profile_dir: Path
    state_dir: Path

    @property
    def profile_path(self) -> Path:
        return self.profile_dir / f"{PROFILE_NAME}.yaml"

    @property
    def state_path(self) -> Path:
        return self.state_dir / "review-bridge.json"


def default_paths() -> SetupPaths:
    return SetupPaths(
        profile_dir=Path.home() / ".config" / "tunnel-client",
        state_dir=Path.home() / ".config" / "codex-goal-ledger",
    )


def _run(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
    allow_failure: bool = False,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.run(
        command,
        env=env,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if process.returncode and not allow_failure:
        detail = process.stderr.strip() or process.stdout.strip() or "no diagnostic"
        raise SetupError(f"command failed ({shlex.join(command)}): {detail}")
    return process


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def _validate_tunnel_id(value: str) -> str:
    if not TUNNEL_ID_PATTERN.fullmatch(value):
        raise SetupError("tunnel id must have the form tunnel_<identifier>")
    return value


def _bridge_command() -> str:
    return shlex.join(
        [sys.executable, str(BRIDGE_SCRIPT), "serve", "--transport", "stdio"]
    )


def _profile_tunnel_id(path: Path) -> str | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    try:
        profile = json.loads(text)
    except json.JSONDecodeError:
        profile = None
    if isinstance(profile, dict):
        control_plane = profile.get("control_plane")
        if isinstance(control_plane, dict):
            tunnel_id = control_plane.get("tunnel_id")
            if isinstance(tunnel_id, str):
                return tunnel_id
    match = re.search(r'(?m)^\s*tunnel_id:\s*["\']?([^\s"\']+)', text)
    return match.group(1) if match else None


def profile_problems(path: Path, tunnel_id: str | None = None) -> list[str]:
    if not path.is_file():
        return [f"missing tunnel-client profile: {path}"]
    text = path.read_text(encoding="utf-8")
    problems: list[str] = []
    expected_tunnel = tunnel_id or _profile_tunnel_id(path)
    if expected_tunnel and expected_tunnel not in text:
        problems.append("profile tunnel id does not match the requested tunnel")
    if "env:CONTROL_PLANE_API_KEY" not in text:
        problems.append("profile must reference env:CONTROL_PLANE_API_KEY")
    if re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}", text):
        problems.append("profile contains a raw API credential")
    command = _bridge_command()
    if command not in text:
        problems.append("profile MCP command does not match this installed skill")
    return problems


def _keychain_account() -> str:
    return getpass.getuser()


def keychain_has_credential(security_bin: str, service: str) -> bool:
    if sys.platform != "darwin":
        return False
    process = _run(
        [security_bin, "find-generic-password", "-a", _keychain_account(), "-s", service],
        allow_failure=True,
    )
    return process.returncode == 0


def _keychain_secret(security_bin: str, service: str) -> str:
    if sys.platform != "darwin":
        value = os.environ.get("CONTROL_PLANE_API_KEY", "")
        if not value:
            raise SetupError(
                "non-macOS bootstrap requires CONTROL_PLANE_API_KEY in the current environment"
            )
        return value
    process = _run(
        [
            security_bin,
            "find-generic-password",
            "-w",
            "-a",
            _keychain_account(),
            "-s",
            service,
        ]
    )
    value = process.stdout.strip()
    if not value.startswith("sk-") or len(value) < 40:
        raise SetupError("Keychain item does not contain a plausible OpenAI runtime key")
    return value


def store_clipboard_key(
    *, security_bin: str, pbpaste_bin: str, pbcopy_bin: str, service: str
) -> None:
    if sys.platform != "darwin":
        raise SetupError("--key-from-clipboard is supported only with macOS Keychain")
    secret = _run([pbpaste_bin]).stdout.strip()
    if not secret.startswith("sk-") or len(secret) < 40:
        raise SetupError("clipboard does not contain a plausible OpenAI runtime key")
    try:
        _run(
            [
                security_bin,
                "add-generic-password",
                "-U",
                "-a",
                _keychain_account(),
                "-s",
                service,
                "-w",
                secret,
            ]
        )
    finally:
        _run([pbcopy_bin], input_text="", allow_failure=True)
        secret = ""


def configure_profile(
    *,
    tunnel_client_bin: str,
    paths: SetupPaths,
    tunnel_id: str,
    replace: bool,
) -> bool:
    tunnel_id = _validate_tunnel_id(tunnel_id)
    problems = profile_problems(paths.profile_path, tunnel_id)
    if not problems:
        return False
    if paths.profile_path.exists() and not replace:
        raise SetupError(
            "; ".join(problems) + "; rerun bootstrap with --replace-profile"
        )
    command = [
        tunnel_client_bin,
        "init",
        "--sample",
        "sample_mcp_stdio_local",
        "--profile",
        PROFILE_NAME,
        "--profile-dir",
        str(paths.profile_dir),
        "--tunnel-id",
        tunnel_id,
        "--mcp-command",
        _bridge_command(),
        "--health-listen-addr",
        "127.0.0.1:0",
    ]
    if paths.profile_path.exists():
        _run(
            [tunnel_client_bin, "runtimes", "stop", RUNTIME_ALIAS, "--json"],
            allow_failure=True,
        )
        command.append("--force")
    _run(command)
    remaining = profile_problems(paths.profile_path, tunnel_id)
    if remaining:
        raise SetupError("generated tunnel profile is invalid: " + "; ".join(remaining))
    return True


def start_runtime(
    *,
    tunnel_client_bin: str,
    security_bin: str,
    keychain_service: str,
    paths: SetupPaths,
) -> dict[str, Any]:
    tunnel_id = _profile_tunnel_id(paths.profile_path)
    if tunnel_id is None:
        raise SetupError("cannot start review bridge without a configured tunnel profile")
    _validate_tunnel_id(tunnel_id)
    secret = _keychain_secret(security_bin, keychain_service)
    environment = os.environ.copy()
    environment["CONTROL_PLANE_API_KEY"] = secret
    try:
        _run(
            [
                tunnel_client_bin,
                "doctor",
                "--profile",
                PROFILE_NAME,
                "--profile-dir",
                str(paths.profile_dir),
                "--explain",
            ],
            env=environment,
        )
        result = _run(
            [
                tunnel_client_bin,
                "runtimes",
                "connect",
                "--alias",
                RUNTIME_ALIAS,
                "--profile",
                PROFILE_NAME,
                "--profile-dir",
                str(paths.profile_dir),
                "--tunnel-id",
                tunnel_id,
                "--mcp-command",
                _bridge_command(),
                "--runtime-api-key",
                "env:CONTROL_PLANE_API_KEY",
                "--json",
            ],
            env=environment,
        )
    finally:
        environment.pop("CONTROL_PLANE_API_KEY", None)
        secret = ""
    try:
        status = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SetupError("tunnel-client returned invalid runtime JSON") from exc
    if not all(status.get(key) is True for key in ("process_running", "healthy", "ready")):
        raise SetupError("managed review-bridge runtime did not become running, healthy, and ready")
    return status


def record_chatgpt_app(
    *, paths: SetupPaths, tunnel_id: str, connector_id: str, app_name: str
) -> None:
    _validate_tunnel_id(tunnel_id)
    if not CONNECTOR_ID_PATTERN.fullmatch(connector_id):
        raise SetupError("connector id must have the form asdk_app_<identifier>")
    _atomic_json(
        paths.state_path,
        {
            "schema_version": 1,
            "app_name": app_name,
            "connector_id": connector_id,
            "tunnel_id": tunnel_id,
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "verification": "record only after visible ChatGPT connected state and tool discovery",
        },
    )


def setup_status(
    *,
    tunnel_client_bin: str,
    security_bin: str,
    keychain_service: str,
    paths: SetupPaths,
) -> dict[str, Any]:
    tunnel_client = shutil.which(tunnel_client_bin) or (
        tunnel_client_bin if Path(tunnel_client_bin).is_file() else None
    )
    tunnel_id = _profile_tunnel_id(paths.profile_path)
    app_record: dict[str, Any] | None = None
    if paths.state_path.is_file():
        try:
            loaded = json.loads(paths.state_path.read_text(encoding="utf-8"))
            app_record = loaded if isinstance(loaded, dict) else None
        except json.JSONDecodeError:
            app_record = None
    result: dict[str, Any] = {
        "schema_version": 1,
        "tunnel_client": tunnel_client,
        "profile_path": str(paths.profile_path),
        "profile_ready": not profile_problems(paths.profile_path, tunnel_id),
        "tunnel_id": tunnel_id,
        "credential_store": "macOS Keychain" if sys.platform == "darwin" else "environment",
        "credential_ready": keychain_has_credential(security_bin, keychain_service)
        if sys.platform == "darwin"
        else bool(os.environ.get("CONTROL_PLANE_API_KEY")),
        "chatgpt_app": app_record,
        "runtime": None,
    }
    if tunnel_client:
        process = _run(
            [
                tunnel_client,
                "runtimes",
                "status",
                RUNTIME_ALIAS,
                "--json",
            ],
            allow_failure=True,
        )
        if process.returncode == 0:
            try:
                result["runtime"] = json.loads(process.stdout)
            except json.JSONDecodeError:
                result["runtime"] = {"error": "invalid status JSON"}
    return result


def status_problems(status: dict[str, Any], *, require_app: bool) -> list[str]:
    problems: list[str] = []
    if not status.get("tunnel_client"):
        problems.append("tunnel-client is not installed or not on PATH")
    if not status.get("profile_ready"):
        problems.append("Goal Ledger tunnel profile is missing or stale")
    if not status.get("credential_ready"):
        problems.append("Tunnels-only runtime credential is not available in the secret store")
    runtime = status.get("runtime")
    if not isinstance(runtime, dict) or not all(
        runtime.get(key) is True for key in ("process_running", "healthy", "ready")
    ):
        problems.append("managed Goal Ledger tunnel runtime is not running, healthy, and ready")
    if require_app and not status.get("chatgpt_app"):
        problems.append("verified ChatGPT Goal Ledger app connection is not recorded")
    return problems


def _add_path_arguments(parser: argparse.ArgumentParser) -> None:
    defaults = default_paths()
    parser.add_argument("--profile-dir", type=Path, default=defaults.profile_dir)
    parser.add_argument("--state-dir", type=Path, default=defaults.state_dir)
    parser.add_argument("--tunnel-client-bin", default="tunnel-client")
    parser.add_argument("--security-bin", default="security")
    parser.add_argument("--keychain-service", default=KEYCHAIN_SERVICE)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Configure and verify Goal Ledger's local Secure MCP Tunnel runtime."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check")
    _add_path_arguments(check)
    check.add_argument("--require-chatgpt-app", action="store_true")
    check.add_argument("--json", action="store_true")

    bootstrap = subparsers.add_parser("bootstrap")
    _add_path_arguments(bootstrap)
    bootstrap.add_argument("--tunnel-id", required=True)
    bootstrap.add_argument("--key-from-clipboard", action="store_true")
    bootstrap.add_argument("--pbpaste-bin", default="pbpaste")
    bootstrap.add_argument("--pbcopy-bin", default="pbcopy")
    bootstrap.add_argument("--replace-profile", action="store_true")
    bootstrap.add_argument("--no-start", action="store_true")
    bootstrap.add_argument("--json", action="store_true")

    start = subparsers.add_parser("start")
    _add_path_arguments(start)
    start.add_argument("--json", action="store_true")

    record = subparsers.add_parser("record-chatgpt-app")
    _add_path_arguments(record)
    record.add_argument("--tunnel-id", required=True)
    record.add_argument("--connector-id", required=True)
    record.add_argument("--app-name", default="Codex Goal Ledger")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    paths = SetupPaths(args.profile_dir.expanduser(), args.state_dir.expanduser())
    try:
        if args.command == "bootstrap":
            if args.key_from_clipboard:
                store_clipboard_key(
                    security_bin=args.security_bin,
                    pbpaste_bin=args.pbpaste_bin,
                    pbcopy_bin=args.pbcopy_bin,
                    service=args.keychain_service,
                )
            configure_profile(
                tunnel_client_bin=args.tunnel_client_bin,
                paths=paths,
                tunnel_id=args.tunnel_id,
                replace=args.replace_profile,
            )
            runtime = None if args.no_start else start_runtime(
                tunnel_client_bin=args.tunnel_client_bin,
                security_bin=args.security_bin,
                keychain_service=args.keychain_service,
                paths=paths,
            )
            result = {"configured": True, "runtime": runtime, **asdict(paths)}
            if args.json:
                print(json.dumps(result, indent=2, sort_keys=True, default=str))
            else:
                print(f"Review bridge profile configured: {paths.profile_path}")
                print("Managed runtime is ready." if runtime else "Managed runtime start skipped.")
            return 0
        if args.command == "start":
            runtime = start_runtime(
                tunnel_client_bin=args.tunnel_client_bin,
                security_bin=args.security_bin,
                keychain_service=args.keychain_service,
                paths=paths,
            )
            print(json.dumps(runtime, indent=2, sort_keys=True) if args.json else "Managed review bridge is ready.")
            return 0
        if args.command == "record-chatgpt-app":
            record_chatgpt_app(
                paths=paths,
                tunnel_id=args.tunnel_id,
                connector_id=args.connector_id,
                app_name=args.app_name,
            )
            print(f"Recorded verified ChatGPT app connection: {paths.state_path}")
            return 0

        status = setup_status(
            tunnel_client_bin=args.tunnel_client_bin,
            security_bin=args.security_bin,
            keychain_service=args.keychain_service,
            paths=paths,
        )
        problems = status_problems(status, require_app=args.require_chatgpt_app)
        if args.json:
            print(json.dumps({"ok": not problems, "problems": problems, **status}, indent=2, sort_keys=True))
        elif problems:
            for problem in problems:
                print(f"error: {problem}", file=sys.stderr)
        else:
            print("Goal Ledger review bridge is installed, connected, running, and ready.")
        return 0 if not problems else 1
    except (OSError, SetupError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
