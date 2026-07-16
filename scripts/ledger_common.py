#!/usr/bin/env python3
"""Shared parsing and rendering helpers for Codex Goal Ledger."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from html import escape, unescape
import json
from pathlib import Path
import re
from typing import Iterable


GOAL_STATUSES = {"draft", "active", "paused", "blocked", "complete", "abandoned"}
EXECUTION_HEALTH = {"healthy", "degraded", "interrupted", "blocked", "inactive"}
PHASE_STATES = {"pending", "active", "blocked", "complete", "skipped"}
CUSTODY_STATES = {"queued", "active", "waiting", "complete", "failed", "lost"}
EVIDENCE_RESULTS = {"pending", "pass", "fail", "blocked", "skipped"}
NO_GATES_MARKERS = {
    "none",
    "none open",
    "no open gates",
    "no blocking gates",
    "no open blocking gates",
    "not applicable",
    "n a",
}


class LedgerError(RuntimeError):
    """Raised when a ledger cannot be parsed or rendered safely."""


@dataclass(frozen=True)
class Document:
    path: Path
    metadata: dict[str, str]
    body: str
    sections: dict[str, str]


def normalize_key(value: str) -> str:
    """Normalize a heading or state for stable lookup."""
    value = re.sub(r"^\d+[.)]?\s*", "", value.strip().casefold())
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def normalize_state(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.strip().casefold()).strip("-") or "unknown"


def code_fences_balanced(value: str) -> bool:
    """Return whether the supported backtick fence markers occur in pairs."""
    return len(re.findall(r"^\s*```", value, flags=re.MULTILINE)) % 2 == 0


def escape_markdown_text(value: str) -> str:
    """Escape inline Markdown punctuation so a contract title renders as literal text."""
    return re.sub(r"([\\`*{}\[\]()<>#+\-.!_|])", r"\\\1", value)


def state_label(value: str) -> str:
    return normalize_state(value).replace("-", " ").title()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().casefold()).strip("-")
    if not slug:
        raise LedgerError("slug must contain at least one letter or number")
    return slug


def parse_frontmatter(text: str, path: Path) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise LedgerError(f"{path}: missing opening frontmatter delimiter")

    closing = next((index for index, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
    if closing is None:
        raise LedgerError(f"{path}: missing closing frontmatter delimiter")

    metadata: dict[str, str] = {}
    for number, line in enumerate(lines[1:closing], 2):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in line:
            raise LedgerError(f"{path}:{number}: frontmatter must use key: value pairs")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise LedgerError(f"{path}:{number}: empty frontmatter key")
        if key in metadata:
            raise LedgerError(f"{path}:{number}: duplicate frontmatter key: {key}")
        if len(value) >= 2 and value[0] == value[-1] == '"':
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                raise LedgerError(f"{path}:{number}: invalid double-quoted scalar") from exc
        elif len(value) >= 2 and value[0] == value[-1] == "'":
            value = value[1:-1].replace("''", "'")
        metadata[key] = value

    body = "\n".join(lines[closing + 1 :]).strip() + "\n"
    return metadata, body


def split_sections(body: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None

    for line in body.splitlines():
        match = re.match(r"^\s*##\s+(.+?)\s*$", line)
        if match:
            current = normalize_key(match.group(1))
            sections[current] = []
            continue
        if current is not None:
            sections[current].append(line)

    return {key: "\n".join(lines).strip() for key, lines in sections.items()}


def load_document(path: Path) -> Document:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise LedgerError(f"missing ledger file: {path}") from exc
    metadata, body = parse_frontmatter(text, path)
    return Document(path=path, metadata=metadata, body=body, sections=split_sections(body))


def get_section(document: Document, name: str) -> str:
    return document.sections.get(normalize_key(name), "")


def split_table_row(line: str) -> list[str]:
    stripped = line.strip().strip("|")
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", stripped)]


def parse_table(markdown: str) -> tuple[list[str], list[list[str]]]:
    lines = [line.strip() for line in markdown.splitlines() if line.strip()]
    for index in range(len(lines) - 1):
        if not lines[index].startswith("|") or not lines[index + 1].startswith("|"):
            continue
        separator = split_table_row(lines[index + 1])
        if not separator or not all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in separator):
            continue
        headers = split_table_row(lines[index])
        rows: list[list[str]] = []
        for line in lines[index + 2 :]:
            if not line.startswith("|"):
                break
            cells = split_table_row(line)
            rows.append(cells)
        return headers, rows
    return [], []


def list_items(markdown: str) -> list[str]:
    items: list[str] = []
    for line in markdown.splitlines():
        match = re.match(r"^\s*(?:[-*+] |\d+[.)] )(.+?)\s*$", line)
        if match:
            items.append(match.group(1).strip())
    return items


def strip_markdown(value: str) -> str:
    value = re.sub(r"```.*?```", " ", value, flags=re.DOTALL)
    value = re.sub(r"`([^`]+)`", r"\1", value)
    value = re.sub(r"!\[([^]]*)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"[*_~#>]", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def gate_items(markdown: str) -> list[str]:
    """Return actionable gates while ignoring canonical plain or bulleted no-gate markers."""
    plain = normalize_key(strip_markdown(markdown))
    if not plain or plain in NO_GATES_MARKERS:
        return []

    items: list[str] = []
    narrative: list[str] = []
    current: list[str] | None = None
    pending_blank = False
    for raw_line in markdown.splitlines():
        marker = re.match(r"^\s*(?:[-*+] |\d+[.)] )(.+?)\s*$", raw_line)
        if marker:
            if current:
                items.append(" ".join(current))
            current = [marker.group(1).strip()]
            pending_blank = False
            continue

        stripped = raw_line.strip()
        if not stripped:
            if current:
                pending_blank = True
            continue
        if current is not None and (not pending_blank or raw_line[:1].isspace()):
            current.append(stripped)
            pending_blank = False
            continue
        if current:
            items.append(" ".join(current))
            current = None
        narrative.append(stripped)
        pending_blank = False
    if current:
        items.append(" ".join(current))

    actionable = [
        item
        for item in items
        if normalize_key(strip_markdown(item)) not in NO_GATES_MARKERS
    ]
    if narrative:
        actionable.insert(0, strip_markdown(" ".join(narrative)))
    return actionable or [strip_markdown(markdown)]


def _safe_href(raw: str) -> str:
    href = unescape(raw).strip()
    if re.match(r"^(?:https?://|mailto:|#|/|\.{1,2}/)", href):
        return escape(href, quote=True)
    if ":" not in href:
        return escape(href, quote=True)
    return "#"


def inline_html(value: str) -> str:
    escaped = escape(value, quote=False)
    tokens: list[str] = []

    def stash(fragment: str) -> str:
        token = f"\x00{len(tokens)}\x00"
        tokens.append(fragment)
        return token

    escaped = re.sub(r"`([^`]+)`", lambda match: stash(f"<code>{match.group(1)}</code>"), escaped)

    def link(match: re.Match[str]) -> str:
        label = match.group(1)
        href = _safe_href(match.group(2))
        return stash(f'<a href="{href}">{label}</a>')

    escaped = re.sub(r"\[([^]]+)\]\(([^)]+)\)", link, escaped)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"__(.+?)__", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", escaped)
    escaped = re.sub(r"(?<!_)_([^_]+)_(?!_)", r"<em>\1</em>", escaped)

    for index, fragment in enumerate(tokens):
        escaped = escaped.replace(f"\x00{index}\x00", fragment)
    return escaped


def _is_table_separator(line: str) -> bool:
    if not line.strip().startswith("|"):
        return False
    cells = split_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells)


def markdown_to_html(markdown: str, heading_shift: int = 0) -> str:
    """Render the ledger's intentionally small Markdown subset safely."""
    lines = markdown.strip().splitlines()
    output: list[str] = []
    index = 0

    def structural(line: str, next_line: str = "") -> bool:
        stripped = line.strip()
        return (
            not stripped
            or stripped.startswith("```")
            or bool(re.match(r"^#{1,6}\s+", stripped))
            or bool(re.match(r"^(?:[-*+] |\d+[.)] )", stripped))
            or stripped.startswith(">")
            or (stripped.startswith("|") and _is_table_separator(next_line))
        )

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue

        if stripped.startswith("```"):
            language = stripped[3:].strip()
            code_lines: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index])
                index += 1
            if index < len(lines):
                index += 1
            language_attr = f' class="language-{escape(language, quote=True)}"' if language else ""
            output.append(f"<pre><code{language_attr}>{escape(chr(10).join(code_lines))}</code></pre>")
            continue

        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", stripped)
        if heading:
            level = min(6, len(heading.group(1)) + heading_shift)
            output.append(f"<h{level}>{inline_html(heading.group(2))}</h{level}>")
            index += 1
            continue

        if stripped.startswith("|") and index + 1 < len(lines) and _is_table_separator(lines[index + 1]):
            headers = split_table_row(stripped)
            index += 2
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                cells = split_table_row(lines[index])
                cells.extend([""] * max(0, len(headers) - len(cells)))
                rows.append(cells[: len(headers)])
                index += 1
            header_html = "".join(f"<th scope=\"col\">{inline_html(cell)}</th>" for cell in headers)
            rows_html = "".join(
                "<tr>" + "".join(f"<td>{inline_html(cell)}</td>" for cell in row) + "</tr>"
                for row in rows
            )
            output.append(f"<table><thead><tr>{header_html}</tr></thead><tbody>{rows_html}</tbody></table>")
            continue

        unordered = re.match(r"^[-*+]\s+(.+)$", stripped)
        ordered = re.match(r"^\d+[.)]\s+(.+)$", stripped)
        if unordered or ordered:
            tag = "ul" if unordered else "ol"
            items: list[str] = []
            pattern = r"^[-*+]\s+(.+)$" if unordered else r"^\d+[.)]\s+(.+)$"
            while index < len(lines):
                match = re.match(pattern, lines[index].strip())
                if not match:
                    break
                item = match.group(1)
                task = re.match(r"^\[([ xX])\]\s+(.+)$", item)
                if task:
                    checked = task.group(1).casefold() == "x"
                    mark = "✓" if checked else "○"
                    item_html = f'<span class="task-mark" aria-hidden="true">{mark}</span>{inline_html(task.group(2))}'
                    items.append(f'<li class="task-item" data-checked="{str(checked).lower()}">{item_html}</li>')
                else:
                    items.append(f"<li>{inline_html(item)}</li>")
                index += 1
            output.append(f"<{tag}>{''.join(items)}</{tag}>")
            continue

        if stripped.startswith(">"):
            quote: list[str] = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote.append(lines[index].strip()[1:].lstrip())
                index += 1
            output.append(f"<blockquote><p>{inline_html(' '.join(quote))}</p></blockquote>")
            continue

        paragraph = [stripped]
        index += 1
        while index < len(lines):
            next_line = lines[index + 1] if index + 1 < len(lines) else ""
            if structural(lines[index], next_line):
                break
            paragraph.append(lines[index].strip())
            index += 1
        output.append(f"<p>{inline_html(' '.join(paragraph))}</p>")

    return "\n".join(output)


def without_first_h1(markdown: str) -> str:
    return re.sub(r"^\s*#\s+.+?\n+", "", markdown, count=1)


def ledger_digest(goal_path: Path, progress_path: Path) -> str:
    digest = sha256()
    digest.update(goal_path.read_bytes())
    digest.update(b"\0")
    digest.update(progress_path.read_bytes())
    return digest.hexdigest()


def replace_template(template: str, values: dict[str, str]) -> str:
    pattern = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
    fields = set(pattern.findall(template))
    missing = sorted(fields - values.keys())
    if missing:
        raise LedgerError(f"unresolved template fields: {', '.join(missing)}")
    return pattern.sub(lambda match: values[match.group(1)], template)


def project_root_for(goal_dir: Path) -> Path:
    goal_dir = goal_dir.resolve()
    if goal_dir.parent.name == "goals" and goal_dir.parent.parent.name == "docs":
        return goal_dir.parent.parent.parent
    raise LedgerError(f"goal directory must be docs/goals/<slug>: {goal_dir}")


def unique_in_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
