#!/usr/bin/env python3
"""Serve Goal Ledger planning controls and one immutable GPT Pro packet as an MCP App."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import shlex
import shutil
import sys
from typing import Any
import zipfile

from ledger_common import LedgerError
from run_pro_review import (
    mcp_read_progress,
    record_mcp_submission_claim,
    record_mcp_member_read,
    record_response_bytes,
    record_submission,
    record_transport_attempt,
)

try:
    from mcp.server.fastmcp import FastMCP
    from mcp.types import CallToolResult, TextContent, ToolAnnotations
except ImportError as exc:  # pragma: no cover - exercised by the runtime preflight.
    FastMCP = None  # type: ignore[assignment]
    CallToolResult = None  # type: ignore[assignment]
    TextContent = None  # type: ignore[assignment]
    ToolAnnotations = None  # type: ignore[assignment]
    MCP_IMPORT_ERROR: Exception | None = exc
else:
    MCP_IMPORT_ERROR = None


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
WIDGET_PATH = SKILL_ROOT / "assets" / "review-bridge.html"
WIDGET_URI = "ui://codex-goal-ledger/review-bridge.html"
MINIMUM_MCP_VERSION = (1, 27, 0)
MAX_RESPONSE_BYTES = 8 * 1024 * 1024


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LedgerError(f"missing review bridge artifact: {path}") from exc
    except json.JSONDecodeError as exc:
        raise LedgerError(f"invalid review bridge JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise LedgerError(f"review bridge JSON must be an object: {path}")
    return value


def _version_tuple(raw: str) -> tuple[int, int, int]:
    values: list[int] = []
    for part in raw.split(".")[:3]:
        digits = "".join(character for character in part if character.isdigit())
        values.append(int(digits or "0"))
    return tuple((values + [0, 0, 0])[:3])  # type: ignore[return-value]


def runtime_problems(*, require_tunnel_client: bool = False) -> list[str]:
    problems: list[str] = []
    if MCP_IMPORT_ERROR is not None:
        problems.append(
            "Python MCP SDK is unavailable; install mcp>=1.27,<2 in the selected Python runtime"
        )
    else:
        try:
            version = importlib.metadata.version("mcp")
        except importlib.metadata.PackageNotFoundError:
            problems.append("Python MCP SDK package metadata is unavailable")
        else:
            if _version_tuple(version) < MINIMUM_MCP_VERSION:
                problems.append(f"Python MCP SDK must be >=1.27; found {version}")
    if not WIDGET_PATH.is_file():
        problems.append(f"missing shipped MCP App widget: {WIDGET_PATH}")
    if require_tunnel_client and shutil.which("tunnel-client") is None:
        problems.append(
            "tunnel-client is unavailable; install the current OpenAI Secure MCP Tunnel client"
        )
    return problems


@dataclass(frozen=True)
class ReviewScope:
    goal_dir: Path
    stage: str
    round_number: int

    @property
    def round_dir(self) -> Path:
        return (
            self.goal_dir
            / "evidence"
            / "pro-review"
            / self.stage
            / f"round-{self.round_number:03d}"
        )

    @property
    def manifest_path(self) -> Path:
        return self.round_dir / "packet-manifest.json"

    @property
    def packet_path(self) -> Path:
        return self.round_dir / "context-packet.zip"

    @property
    def state_path(self) -> Path:
        return self.round_dir / "state.json"

    def verified_packet(self) -> tuple[dict[str, Any], dict[str, bytes]]:
        manifest = _json_object(self.manifest_path)
        packet = self.packet_path.read_bytes()
        expected_packet_hash = manifest.get("archive_sha256")
        if not isinstance(expected_packet_hash, str) or _sha(packet) != expected_packet_hash:
            raise LedgerError("review bridge packet hash does not match packet-manifest.json")

        declared = manifest.get("zip_members")
        if not isinstance(declared, list):
            raise LedgerError("review bridge manifest zip_members must be a list")
        declared_by_path: dict[str, dict[str, Any]] = {}
        for item in declared:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise LedgerError("review bridge manifest contains an invalid ZIP member")
            path = item["path"]
            if path in declared_by_path:
                raise LedgerError(f"review bridge manifest contains duplicate member: {path}")
            declared_by_path[path] = item

        try:
            with zipfile.ZipFile(self.packet_path) as archive:
                names = archive.namelist()
                if names != sorted(names) or len(names) != len(set(names)):
                    raise LedgerError("review bridge ZIP members must be unique and sorted")
                if set(names) != set(declared_by_path):
                    raise LedgerError("review bridge ZIP member set does not match the manifest")
                members = {name: archive.read(name) for name in names}
        except zipfile.BadZipFile as exc:
            raise LedgerError("review bridge packet is not a valid ZIP archive") from exc

        for name, data in members.items():
            declaration = declared_by_path[name]
            if declaration.get("bytes") != len(data) or declaration.get("sha256") != _sha(data):
                raise LedgerError(f"review bridge member hash or size mismatch: {name}")
        request = (self.round_dir / "request.md").read_bytes()
        if members.get("START-HERE.md") != request:
            raise LedgerError("review bridge request.md differs from ZIP START-HERE.md")
        if manifest.get("request_sha256") != _sha(request):
            raise LedgerError("review bridge request hash does not match the manifest")
        return manifest, members

    def summary(self) -> dict[str, Any]:
        manifest, _ = self.verified_packet()
        state = _json_object(self.state_path)
        return {
            "stage": self.stage,
            "round": self.round_number,
            "decision": manifest.get("decision"),
            "packet_sha256": manifest.get("archive_sha256"),
            "packet_bytes": manifest.get("archive_bytes"),
            "members": [
                {
                    "path": item["path"],
                    "bytes": item["bytes"],
                    "sha256": item["sha256"],
                }
                for item in manifest["zip_members"]
            ],
            "read_progress": mcp_read_progress(self.round_dir),
            "status": state.get("status"),
            "next_action": state.get("next_action"),
            "security": {
                "source": "immutable context-packet.zip only",
                "live_repository_access": False,
                "shell_access": False,
                "arbitrary_write_access": False,
                "permitted_write": "one immutable Pro response plus custody metadata",
            },
        }

    def read_member(self, member_path: str) -> str:
        _, members = self.verified_packet()
        if member_path not in members:
            raise LedgerError(
                "member_path must exactly match one member listed by open_goal_ledger"
            )
        try:
            return members[member_path].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise LedgerError(f"review bridge member is not UTF-8 text: {member_path}") from exc


PLANNING_SCHEMA: dict[str, Any] = {
    "review_choices": [
        {"key": "fable_feedback", "label": "Claude Fable planning review"},
        {"key": "fable_rescue", "label": "Claude Fable scientific rescue"},
        {"key": "pro_review", "label": "GPT Pro review"},
        {"key": "external_review_prompt", "label": "External LLM review prompt"},
        {"key": "codex_review", "label": "Additional Codex closeout review"},
        {"key": "clean_session_handoff", "label": "Clean-session handoff prompt"},
    ],
    "implementation_presets": [
        {"family": "Luna", "effort": "High", "agent": "goal-ledger-implementer-luna-high"},
        {"family": "Luna", "effort": "Max", "agent": "goal-ledger-implementer"},
        {"family": "Terra", "effort": "Ultra", "agent": "goal-ledger-implementer-terra-ultra"},
        {"family": "Sol", "effort": "Medium", "agent": "goal-ledger-implementer-sol-medium"},
        {"family": "Sol", "effort": "XHigh", "agent": "goal-ledger-implementer-sol-xhigh"},
        {"family": "Sol", "effort": "Ultra", "agent": "goal-ledger-implementer-sol-ultra"},
    ],
    "pro_deliveries": [
        "mcp-app",
        "auto-ui",
        "native-chat",
        "safari-assisted",
        "chrome-assisted",
        "owner-handoff",
    ],
}


def _tool_result(data: dict[str, Any], text: str) -> Any:
    if CallToolResult is None or TextContent is None:
        raise LedgerError("Python MCP SDK is unavailable")
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        structuredContent=data,
    )


def build_server(
    scope: ReviewScope | None,
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
) -> Any:
    problems = runtime_problems()
    if problems:
        raise LedgerError("; ".join(problems))
    assert FastMCP is not None and ToolAnnotations is not None
    if scope is not None:
        scope.verified_packet()

    server = FastMCP(
        "Codex Goal Ledger",
        instructions=(
            "In review mode, call open_workspace, read START-HERE.md and every file returned by "
            "list_files, use search when helpful, answer the embedded request, and call "
            "write_review once with the complete response. The workspace is immutable and "
            "manifest-bound; never infer shell or live repository access."
        ),
        host=host,
        port=port,
        stateless_http=True,
        json_response=True,
    )

    @server.resource(
        WIDGET_URI,
        name="goal-ledger-review-bridge",
        title="Goal Ledger controls and review bridge",
        description="Interactive planning controls and immutable GPT Pro review custody.",
        mime_type="text/html;profile=mcp-app",
        meta={"ui": {"prefersBorder": True}},
    )
    def review_bridge_widget() -> str:
        return WIDGET_PATH.read_text(encoding="utf-8")

    def ensure_mcp_submission_claim() -> dict[str, Any]:
        if scope is None:
            raise LedgerError("this Goal Ledger bridge is not bound to a prepared review round")
        submission_path = scope.round_dir / "submission.json"
        if submission_path.is_file():
            existing = _json_object(submission_path)
            if existing.get("transport") != "mcp-app":
                raise LedgerError("this round was already submitted through another transport")
            manifest, _ = scope.verified_packet()
            if existing.get("packet_sha256") != manifest.get("archive_sha256"):
                raise LedgerError("existing MCP submission claim names a different packet")
            return existing
        attempts_path = scope.round_dir / "transport-attempts.json"
        attempts = (
            _json_object(attempts_path).get("attempts", [])
            if attempts_path.is_file()
            else []
        )
        if not any(
            isinstance(item, dict)
            and item.get("surface") == "mcp-app"
            and item.get("result") == "ready"
            for item in attempts
        ):
            record_transport_attempt(
                scope.goal_dir,
                stage=scope.stage,
                round_number=scope.round_number,
                surface="mcp-app",
                result="ready",
                detail=(
                    "The bounded Goal Ledger workspace reached the manifest-bound local server; "
                    "first workspace access now owns this packet's transport custody."
                ),
            )
        record_mcp_submission_claim(
            scope.goal_dir,
            stage=scope.stage,
            round_number=scope.round_number,
        )
        return _json_object(submission_path)

    def read_member_result(member_path: str) -> Any:
        if scope is None:
            raise LedgerError("this Goal Ledger bridge is not bound to a prepared review round")
        ensure_mcp_submission_claim()
        text = scope.read_member(member_path)
        manifest, members = scope.verified_packet()
        record_mcp_member_read(
            scope.round_dir,
            packet_sha256=str(manifest["archive_sha256"]),
            member_path=member_path,
            member_sha256=_sha(members[member_path]),
        )
        return _tool_result(
            {
                "member_path": member_path,
                "sha256": _sha(text.encode("utf-8")),
                "text": text,
                "read_progress": mcp_read_progress(scope.round_dir),
            },
            text,
        )

    def begin_review_result(model_visible: str, thread_reference: str) -> Any:
        if scope is None:
            raise LedgerError("this Goal Ledger bridge is not bound to a prepared review round")
        submission_path = scope.round_dir / "submission.json"
        if submission_path.is_file():
            existing = _json_object(submission_path)
            if existing.get("transport") != "mcp-app":
                raise LedgerError("this round was already submitted through another transport")
            result = {
                "status": "already-submitted",
                "submission": existing,
                "review": scope.summary(),
            }
            return _tool_result(result, "The immutable MCP App submission was already recorded.")
        attempts_path = scope.round_dir / "transport-attempts.json"
        attempts = (
            _json_object(attempts_path).get("attempts", [])
            if attempts_path.is_file()
            else []
        )
        if not any(
            isinstance(item, dict)
            and item.get("surface") == "mcp-app"
            and item.get("result") == "ready"
            for item in attempts
        ):
            record_transport_attempt(
                scope.goal_dir,
                stage=scope.stage,
                round_number=scope.round_number,
                surface="mcp-app",
                result="ready",
                detail=(
                    "The bounded Goal Ledger workspace reached the manifest-bound local server; "
                    "the review is being completed in the connected Pro conversation."
                ),
            )
        record_submission(
            scope.goal_dir,
            stage=scope.stage,
            round_number=scope.round_number,
            model_visible=model_visible,
            transport="mcp-app",
            thread=thread_reference,
        )
        result = {
            "status": "submitted-waiting-response",
            "submission": _json_object(submission_path),
            "review": scope.summary(),
        }
        return _tool_result(
            result,
            "Submission custody recorded. Read every packet member and submit the complete response once.",
        )

    def submit_response_result(response: str) -> Any:
        if scope is None:
            raise LedgerError("this Goal Ledger bridge is not bound to a prepared review round")
        raw = response.encode("utf-8")
        if len(raw) > MAX_RESPONSE_BYTES:
            raise LedgerError(f"Pro response exceeds {MAX_RESPONSE_BYTES} bytes")
        response_path = scope.round_dir / "response.md"
        if response_path.is_file():
            if response_path.read_bytes() != raw:
                raise LedgerError("a different immutable Pro response is already recorded")
            metadata = _json_object(scope.round_dir / "response-metadata.json")
            result = {"status": "already-recorded", "response": metadata, "review": scope.summary()}
            return _tool_result(result, "The byte-identical Pro response was already recorded.")
        _, verdict = record_response_bytes(
            scope.goal_dir,
            stage=scope.stage,
            round_number=scope.round_number,
            raw=raw,
        )
        metadata = _json_object(scope.round_dir / "response-metadata.json")
        result = {
            "status": "response-received",
            "verdict": verdict,
            "response": metadata,
            "review": scope.summary(),
        }
        return _tool_result(
            result,
            f"Complete Pro response recorded with verdict {verdict}. Local reconciliation is now required.",
        )

    @server.tool(
        name="open_goal_ledger",
        title="Open Goal Ledger controls",
        description=(
            "Open the interactive Goal Ledger planning controls. When this server is bound to "
            "a prepared GPT Pro round, also return its exact immutable packet manifest, request, "
            "members, custody state, and security boundary."
        ),
        annotations=ToolAnnotations(
            title="Open Goal Ledger controls",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        meta={
            "ui": {"resourceUri": WIDGET_URI},
            "openai/toolInvocation/invoking": "Opening Goal Ledger…",
            "openai/toolInvocation/invoked": "Goal Ledger ready",
        },
    )
    def open_goal_ledger(scientific_or_high_risk: bool = False) -> Any:
        defaults = {
            "fable_feedback": scientific_or_high_risk,
            "fable_rescue": scientific_or_high_risk,
            "pro_review": scientific_or_high_risk,
            "external_review_prompt": True,
            "codex_review": True,
            "clean_session_handoff": True,
            "fable_rounds": 1,
            "pro_rounds": 1,
            "pro_stage": "plan",
            "pro_delivery": "auto-ui",
            "pro_gate": "required",
            "implementation_agent": "goal-ledger-implementer",
        }
        data: dict[str, Any] = {
            "mode": "review" if scope is not None else "planning",
            "planning": {"schema": PLANNING_SCHEMA, "defaults": defaults},
        }
        if scope is not None:
            ensure_mcp_submission_claim()
            data["review"] = scope.summary()
        return _tool_result(
            data,
            (
                "Goal Ledger review console is ready. Use only the bound immutable packet and "
                "submit the complete Pro response through the bridge."
                if scope is not None
                else "Goal Ledger planning controls are ready. Submit the form to post the selected values into this chat."
            ),
        )

    @server.tool(
        name="get_review_status",
        title="Get Goal Ledger review status",
        description="Return the bound immutable review packet and current custody status.",
        annotations=ToolAnnotations(
            title="Get Goal Ledger review status",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    def get_review_status() -> Any:
        if scope is None:
            raise LedgerError("this Goal Ledger bridge is not bound to a prepared review round")
        ensure_mcp_submission_claim()
        data = {"mode": "review", "review": scope.summary()}
        return _tool_result(data, f"Review status: {data['review']['status']}")

    @server.tool(
        name="read_review_file",
        title="Read immutable review packet member",
        description=(
            "Read one UTF-8 member from the bound immutable GPT Pro ZIP. The member_path must "
            "exactly match a path returned by open_goal_ledger. Read every listed member before "
            "issuing the review verdict."
        ),
        annotations=ToolAnnotations(
            title="Read immutable review packet member",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    def read_review_file(member_path: str) -> Any:
        return read_member_result(member_path)

    @server.tool(
        name="open_workspace",
        title="Open bounded review workspace",
        description=(
            "Open the currently bound Goal Ledger review workspace. This is a DevSpace-style "
            "workspace containing only immutable manifest-listed packet files, with no shell or "
            "live repository access."
        ),
        annotations=ToolAnnotations(
            title="Open bounded review workspace",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    def open_workspace() -> Any:
        if scope is None:
            raise LedgerError("this Goal Ledger bridge is not bound to a prepared review round")
        ensure_mcp_submission_claim()
        summary = scope.summary()
        data = {
            "workspace": {
                "id": f"{summary['stage']}-round-{summary['round']}",
                "instructions": (
                    "Read START-HERE.md first, inspect every listed file with read, use search "
                    "when helpful, then call write_review once with the complete verdict."
                ),
                **summary,
            }
        }
        return _tool_result(data, data["workspace"]["instructions"])

    @server.tool(
        name="list_files",
        title="List bounded review files",
        description="List every file available in the bound immutable review workspace.",
        annotations=ToolAnnotations(
            title="List bounded review files",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    def list_files() -> Any:
        if scope is None:
            raise LedgerError("this Goal Ledger bridge is not bound to a prepared review round")
        ensure_mcp_submission_claim()
        members = scope.summary()["members"]
        return _tool_result({"files": members}, "\n".join(item["path"] for item in members))

    @server.tool(
        name="read",
        title="Read bounded review file",
        description=(
            "Read one exact UTF-8 file from the bound review workspace. The path must come from "
            "list_files. Each read creates a packet-hash-bound audit receipt."
        ),
        annotations=ToolAnnotations(
            title="Read bounded review file",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    def read(path: str) -> Any:
        return read_member_result(path)

    @server.tool(
        name="search",
        title="Search bounded review workspace",
        description=(
            "Search all UTF-8 files in the bound review workspace for a literal case-insensitive "
            "query. Returns at most 100 matching lines and does not access the live repository."
        ),
        annotations=ToolAnnotations(
            title="Search bounded review workspace",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    def search(query: str) -> Any:
        if scope is None:
            raise LedgerError("this Goal Ledger bridge is not bound to a prepared review round")
        ensure_mcp_submission_claim()
        query = query.strip()
        if not query:
            raise LedgerError("search query must not be empty")
        _, members = scope.verified_packet()
        matches: list[dict[str, Any]] = []
        needle = query.casefold()
        for path, data in members.items():
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                continue
            for line_number, line in enumerate(text.splitlines(), 1):
                if needle in line.casefold():
                    matches.append(
                        {"path": path, "line": line_number, "text": line[:1000]}
                    )
                    if len(matches) == 100:
                        break
            if len(matches) == 100:
                break
        return _tool_result(
            {"query": query, "matches": matches, "truncated": len(matches) == 100},
            "\n".join(
                f"{item['path']}:{item['line']}: {item['text']}" for item in matches
            )
            or "No matches.",
        )

    @server.tool(
        name="begin_pro_review",
        title="Begin bound GPT Pro review",
        description=(
            "Record that the exact bound packet was opened in a visibly selected GPT Pro or Pro "
            "Extended conversation. Call once before reviewing files. This writes only immutable "
            "submission custody metadata inside the prepared round."
        ),
        annotations=ToolAnnotations(
            title="Begin bound GPT Pro review",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    def begin_pro_review(model_visible: str, thread_reference: str) -> Any:
        return begin_review_result(model_visible, thread_reference)

    @server.tool(
        name="submit_pro_review_response",
        title="Submit complete GPT Pro review response",
        description=(
            "Store the complete review response for the bound packet. It must begin with exactly "
            "Verdict: SIGNED OFF or Verdict: BLOCKED and include every finding, risk, test, and "
            "reasoning note. The response is immutable and retries must be byte-identical."
        ),
        annotations=ToolAnnotations(
            title="Submit complete GPT Pro review response",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    def submit_pro_review_response(response: str) -> Any:
        return submit_response_result(response)

    @server.tool(
        name="write_review",
        title="Save complete review",
        description=(
            "Save the complete GPT Pro review after every workspace file has been read. First "
            "workspace access already recorded transport custody; this stores the immutable response."
        ),
        annotations=ToolAnnotations(
            title="Save complete review",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    def write_review(response: str) -> Any:
        if scope is None:
            raise LedgerError("this Goal Ledger bridge is not bound to a prepared review round")
        ensure_mcp_submission_claim()
        return submit_response_result(response)

    return server


def _scope_from_args(args: argparse.Namespace) -> ReviewScope | None:
    if args.goal_dir is None:
        return None
    goal_dir = args.goal_dir.expanduser().resolve()
    if not goal_dir.is_dir() or goal_dir.is_symlink():
        raise LedgerError(f"goal directory must be a regular directory: {goal_dir}")
    return ReviewScope(goal_dir=goal_dir, stage=args.stage, round_number=args.round_number)


def _stdio_command(scope: ReviewScope | None) -> list[str]:
    command = [sys.executable, str(Path(__file__).resolve()), "serve", "--transport", "stdio"]
    if scope is not None:
        command.extend(
            [
                "--goal-dir",
                str(scope.goal_dir),
                "--stage",
                scope.stage,
                "--round",
                str(scope.round_number),
            ]
        )
    return command


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Goal Ledger's self-contained restricted MCP App review bridge."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("serve", "check", "print-command"):
        command = subparsers.add_parser(name)
        command.add_argument("--goal-dir", type=Path)
        command.add_argument("--stage", choices=("plan", "implementation"), default="plan")
        command.add_argument("--round", dest="round_number", type=int, default=1)
        if name == "serve":
            command.add_argument(
                "--transport", choices=("stdio", "streamable-http"), default="stdio"
            )
            command.add_argument("--host", default="127.0.0.1")
            command.add_argument("--port", type=int, default=8787)
        if name == "check":
            command.add_argument("--require-tunnel-client", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        scope = _scope_from_args(args)
        if args.command == "check":
            problems = runtime_problems(require_tunnel_client=args.require_tunnel_client)
            if scope is not None:
                scope.verified_packet()
            if problems:
                raise LedgerError("; ".join(problems))
            print("Goal Ledger MCP App runtime is ready.")
            print(
                "Security boundary: bounded immutable workspace reads/search; "
                "review-only custody write; no shell or live repo tools."
            )
            if scope is not None:
                summary = scope.summary()
                print(f"Packet: {summary['packet_sha256']} ({summary['packet_bytes']} bytes)")
            return 0
        if args.command == "print-command":
            print(shlex.join(_stdio_command(scope)))
            return 0
        server = build_server(scope, host=args.host, port=args.port)
        server.run(transport=args.transport)
        return 0
    except (LedgerError, OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
