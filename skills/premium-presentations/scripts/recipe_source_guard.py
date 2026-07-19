#!/usr/bin/env python3
"""Recipe source guard — deterministic, stdlib-only source collection for
`/present-architecture` and `/present-postmortem`.

Owns ALL source collection for both recipes so trust-boundary enforcement is
a deterministic helper, not prose in a command file. Three modes:

- **scan** (architecture): enumerates git-tracked *regular* files only —
  symlinks and vendored/generated/secret paths (`node_modules/`, `dist/`,
  `build/`, `.env*`, `*.pem`, `*.key`, lockfiles) are excluded. Caps: 256 KB
  per file, 500 files, 10 MB total. Exceeding a cap truncates the result and
  records an explicit truncation note — it never fails silently. Binary or
  undecodable files are skipped and listed, not truncated.
- **validate-file** (incident doc / CI log): a single path must resolve
  (symlinks are followed, then the *resolved* target is re-checked and
  rejected if it is not a regular file), be readable, be <= 10 MB, and be
  decodable as UTF-8 text. Any failure is a loud, non-zero exit with a
  message on stderr — never a silent skip.
- **redact**: a text pass (used internally by scan/validate-file, and
  exposed standalone for other collected text such as `git diff` output)
  that strips explicitly recognizable credential and PII patterns.

Two supporting utilities complete the CLI surface consumed from a command
markdown's bash steps: **resolve-ref** (wraps `git rev-parse --verify`,
rejecting option-like refs — pass `--` before the ref per the standard git
end-of-options convention) and **check-args** (validates the
`/present-postmortem` argument contract: required incident file, optional
`--git-range <ref>..<ref>` / `--ci-log <file>` / `--keep-identifiers`,
rejecting missing values, option-like values, and conflicting repeats).

Every subcommand prints one JSON object to stdout on success (exit 0) or a
plain-text message to stderr on failure (non-zero exit) — nothing here ever
interprets the *content* it collects; embedded instructions in scanned or
validated text are inert data to every caller.

**Redaction is best-effort pattern matching, not a security guarantee.**
Only the explicitly recognized categories below are covered:

- Credentials: AWS access/session keys (`AKIA`/`ASIA` prefix), GitHub
  `ghp_`/`gho_` tokens, PEM private-key blocks, `Bearer` tokens, and
  passwords embedded in `scheme://user:pass@host` connection strings.
- PII: person names *only when introduced by a recognized label*
  (`Name:`, `Reporter:`, `Engineer:`, `Customer:`, etc.), email addresses,
  common phone-number formats, IPv4 addresses, and labeled
  customer/tenant/account identifiers.

Arbitrary unlabeled names, freeform PII prose, or novel credential formats
are NOT guaranteed to be caught. Ambiguous identities require manual review
or an explicit user-supplied pseudonymization map before a deck ships.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

MAX_FILE_BYTES = 256 * 1024
MAX_FILES = 500
MAX_TOTAL_BYTES = 10 * 1024 * 1024
MAX_VALIDATE_BYTES = 10 * 1024 * 1024

_EXCLUDED_DIR_NAMES = frozenset({"node_modules", "dist", "build"})
_LOCKFILE_NAMES = frozenset(
    {
        "package-lock.json",
        "npm-shrinkwrap.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "Pipfile.lock",
        "poetry.lock",
        "Cargo.lock",
        "composer.lock",
        "Gemfile.lock",
        "mix.lock",
        "go.sum",
    }
)


class GuardError(Exception):
    """A validation/collection failure — message goes to stderr, exit != 0."""


def _is_excluded(rel_posix: str) -> str | None:
    """Return an exclusion reason, or None if *rel_posix* is allowed."""
    parts = PurePosixPath(rel_posix).parts
    if any(part in _EXCLUDED_DIR_NAMES for part in parts[:-1]):
        return "excluded_directory"
    name = parts[-1] if parts else rel_posix
    if name.startswith(".env"):
        return "env_file"
    if name.endswith(".pem") or name.endswith(".key"):
        return "key_material"
    if name in _LOCKFILE_NAMES:
        return "lockfile"
    return None


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Pattern:
    category: str
    regex: re.Pattern[str]
    replacement: str


_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.DOTALL,
)

_REDACTION_PATTERNS: tuple[_Pattern, ...] = (
    _Pattern("private_key", _PRIVATE_KEY_RE, "[REDACTED:PRIVATE_KEY]"),
    _Pattern(
        "aws_key",
        re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
        "[REDACTED:AWS_KEY]",
    ),
    _Pattern(
        "github_token",
        re.compile(r"\bgh[po]_[A-Za-z0-9]{20,255}\b"),
        "[REDACTED:GITHUB_TOKEN]",
    ),
    _Pattern(
        "bearer_token",
        re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/]+=*"),
        "Bearer [REDACTED:TOKEN]",
    ),
    _Pattern(
        "connection_string_password",
        re.compile(r"([A-Za-z][A-Za-z0-9+.-]*://[^\s:/@]+:)([^\s@]+)(@)"),
        r"\1[REDACTED:PASSWORD]\3",
    ),
    _Pattern(
        "account_id",
        re.compile(
            r"(?i)\b(customer|tenant|account)([_\s-]?id)\s*[:=]\s*\"?([A-Za-z0-9\-_.]+)\"?"
        ),
        r"\1\2: [REDACTED:ACCOUNT_ID]",
    ),
    _Pattern(
        "person_name",
        re.compile(
            r"(?im)^(\s*(?:name|reporter|author|customer|client|engineer"
            r"|on-call|assignee|contact|owner)\s*:\s*)([^\n]+)$"
        ),
        r"\1[REDACTED:PERSON]",
    ),
    _Pattern(
        "email",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "[REDACTED:EMAIL]",
    ),
    _Pattern(
        "phone",
        re.compile(r"(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)"),
        "[REDACTED:PHONE]",
    ),
    _Pattern(
        "ip_address",
        re.compile(
            r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\b"
        ),
        "[REDACTED:IP]",
    ),
)


def redact_text(text: str) -> tuple[str, dict[str, int]]:
    """Apply every recognized redaction pattern; return (text, counts)."""
    counts: dict[str, int] = {}
    for pattern in _REDACTION_PATTERNS:
        text, n = pattern.regex.subn(pattern.replacement, text)
        counts[pattern.category] = n
    return text, counts


# ---------------------------------------------------------------------------
# Architecture mode: git-tracked repo scan
# ---------------------------------------------------------------------------


def _run_git(args: list[str], cwd: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise GuardError("git executable not found") from exc
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.decode("utf-8", errors="replace").strip()
        raise GuardError(f"git {' '.join(args)} failed: {message}") from exc
    return proc.stdout.decode("utf-8", errors="surrogateescape")


def scan_repo(repo_root: Path) -> dict:
    """Collect git-tracked regular files under *repo_root*, capped and redacted."""
    repo_root = repo_root.resolve()
    raw = _run_git(["ls-files", "-z"], repo_root)
    tracked = sorted(p for p in raw.split("\0") if p)

    files: list[dict] = []
    skipped: list[dict[str, str]] = []
    notes: list[str] = []
    total_bytes = 0
    redaction_totals: dict[str, int] = {}
    omitted_after_file_cap = 0
    omitted_after_total_cap = 0

    for rel in tracked:
        full = repo_root / rel
        reason = _is_excluded(rel)
        if reason:
            skipped.append({"path": rel, "reason": reason})
            continue
        if full.is_symlink() or not full.is_file():
            skipped.append({"path": rel, "reason": "not_regular_file"})
            continue
        if len(files) >= MAX_FILES:
            omitted_after_file_cap += 1
            continue
        if total_bytes >= MAX_TOTAL_BYTES:
            omitted_after_total_cap += 1
            continue

        size = full.stat().st_size
        read_len = min(size, MAX_FILE_BYTES)
        raw_bytes = full.read_bytes()[:read_len]
        if b"\x00" in raw_bytes:
            skipped.append({"path": rel, "reason": "binary"})
            continue
        truncated = size > MAX_FILE_BYTES
        try:
            text = raw_bytes.decode("utf-8", errors="ignore" if truncated else "strict")
        except UnicodeDecodeError:
            skipped.append({"path": rel, "reason": "undecodable"})
            continue

        text, counts = redact_text(text)
        for category, n in counts.items():
            redaction_totals[category] = redaction_totals.get(category, 0) + n

        total_bytes += len(raw_bytes)
        if truncated:
            notes.append(f"{rel}: truncated at {MAX_FILE_BYTES} bytes (per-file cap)")
        files.append(
            {"path": rel, "bytes": len(raw_bytes), "truncated": truncated, "content": text}
        )

    if omitted_after_file_cap:
        notes.append(
            f"{omitted_after_file_cap} additional tracked file(s) omitted: "
            f"{MAX_FILES}-file cap reached"
        )
    if omitted_after_total_cap:
        notes.append(
            f"{omitted_after_total_cap} additional tracked file(s) omitted: "
            f"{MAX_TOTAL_BYTES}-byte total-collection cap reached"
        )

    return {
        "repo": str(repo_root),
        "files": files,
        "skipped": skipped,
        "truncation_notes": notes,
        "redaction_totals": redaction_totals,
        "totals": {
            "files_included": len(files),
            "files_skipped": len(skipped),
            "files_omitted_by_cap": omitted_after_file_cap + omitted_after_total_cap,
            "total_bytes": total_bytes,
        },
    }


# ---------------------------------------------------------------------------
# File-validation mode: incident doc / CI log
# ---------------------------------------------------------------------------


def validate_file(path: Path) -> dict:
    """Validate + redact a single user-supplied file (incident doc / CI log)."""
    try:
        resolved = path.expanduser().resolve(strict=True)
    except OSError as exc:
        raise GuardError(f"path does not exist or cannot be resolved: {path}") from exc

    if not resolved.is_file():
        raise GuardError(f"not a regular file after resolving symlinks: {path}")

    if not os.access(resolved, os.R_OK):
        raise GuardError(f"path is not readable: {path}")

    size = resolved.stat().st_size
    if size > MAX_VALIDATE_BYTES:
        raise GuardError(
            f"file exceeds the {MAX_VALIDATE_BYTES}-byte validation cap: {path} ({size} bytes)"
        )

    try:
        raw = resolved.read_bytes()
    except OSError as exc:
        raise GuardError(f"path is not readable: {path}") from exc

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GuardError(f"file is not decodable as UTF-8 text: {path}") from exc

    text, counts = redact_text(text)
    return {"path": str(resolved), "bytes": size, "content": text, "redactions": counts}


# ---------------------------------------------------------------------------
# git ref resolution
# ---------------------------------------------------------------------------


def resolve_ref(repo_root: Path, ref: str) -> str:
    """Resolve *ref* to a verified commit SHA via `git rev-parse --verify`.

    Rejects option-like refs (anything starting with `-`) before ever
    invoking git — callers pass `--` ahead of the ref per the standard git
    end-of-options convention so option-like values reach this check
    instead of being swallowed as a CLI flag.
    """
    if not ref or ref.startswith("-"):
        raise GuardError(f"refusing option-like git ref: {ref!r}")
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
            capture_output=True,
        )
    except FileNotFoundError as exc:
        raise GuardError("git executable not found") from exc
    sha = proc.stdout.decode("utf-8", errors="replace").strip()
    if proc.returncode != 0 or not sha:
        raise GuardError(f"ref does not resolve to a commit: {ref!r}")
    return sha


# ---------------------------------------------------------------------------
# /present-postmortem argument contract
# ---------------------------------------------------------------------------

_RANGE_RE = re.compile(r"^(?P<from>[^.\s]+)\.\.(?P<to>[^.\s]+)$")
_USAGE = (
    "an incident-file argument is required — "
    "/present-postmortem <incident-file> [--git-range <ref>..<ref>] "
    "[--ci-log <file>] [--keep-identifiers]"
)


def check_postmortem_args(argv: list[str]) -> dict:
    """Validate the `/present-postmortem` argument contract, deterministically.

    Rejects: missing incident file, missing flag values, option-like values
    (`--git-range --foo..HEAD`), and conflicting repeats of the same flag
    with different values.
    """
    incident_file: str | None = None
    git_range: str | None = None
    ci_log: str | None = None
    keep_identifiers = False

    i = 0
    while i < len(argv):
        token = argv[i]
        if token == "--git-range":
            if i + 1 >= len(argv):
                raise GuardError("--git-range requires a value")
            value = argv[i + 1]
            if value.startswith("-"):
                raise GuardError(f"--git-range value looks like an option: {value!r}")
            match = _RANGE_RE.match(value)
            if not match:
                raise GuardError(f"--git-range value must look like <ref>..<ref>: {value!r}")
            for side in (match.group("from"), match.group("to")):
                if side.startswith("-"):
                    raise GuardError(f"--git-range contains an option-like ref: {side!r}")
            if git_range is not None and git_range != value:
                raise GuardError("conflicting --git-range values supplied")
            git_range = value
            i += 2
            continue
        if token == "--ci-log":
            if i + 1 >= len(argv):
                raise GuardError("--ci-log requires a value")
            value = argv[i + 1]
            if value.startswith("-"):
                raise GuardError(f"--ci-log value looks like an option: {value!r}")
            if ci_log is not None and ci_log != value:
                raise GuardError("conflicting --ci-log values supplied")
            ci_log = value
            i += 2
            continue
        if token == "--keep-identifiers":
            keep_identifiers = True
            i += 1
            continue
        if token.startswith("--"):
            raise GuardError(f"unrecognized flag: {token!r}")
        if token.startswith("-") and token != "-":
            raise GuardError(f"incident file argument looks like an option: {token!r}")
        if incident_file is not None and incident_file != token:
            raise GuardError("conflicting incident-file arguments supplied")
        incident_file = token
        i += 1

    if incident_file is None:
        raise GuardError(_USAGE)

    return {
        "incident_file": incident_file,
        "git_range": git_range,
        "ci_log": ci_log,
        "keep_identifiers": keep_identifiers,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_error(message: str) -> None:
    print(f"recipe_source_guard: {message}", file=sys.stderr)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="recipe_source_guard.py", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="scan a git repo's tracked files")
    scan_parser.add_argument("repo", type=Path, nargs="?", default=Path("."))

    validate_parser = subparsers.add_parser(
        "validate-file", help="validate + redact a single file (incident doc / CI log)"
    )
    validate_parser.add_argument("path", type=Path)

    resolve_parser = subparsers.add_parser(
        "resolve-ref", help="resolve a git ref to a verified commit SHA"
    )
    resolve_parser.add_argument("repo", type=Path)
    resolve_parser.add_argument("ref")

    redact_parser = subparsers.add_parser("redact", help="redact stdin or a file")
    redact_parser.add_argument("path", type=Path, nargs="?")

    check_parser = subparsers.add_parser(
        "check-args", help="validate the /present-postmortem argument contract"
    )
    check_parser.add_argument("rest", nargs=argparse.REMAINDER)

    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else list(argv)
    parser = _build_parser()
    try:
        options = parser.parse_args(arguments)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 2

    try:
        if options.command == "scan":
            result: dict | None = scan_repo(options.repo)
        elif options.command == "validate-file":
            result = validate_file(options.path)
        elif options.command == "resolve-ref":
            print(resolve_ref(options.repo, options.ref))
            return 0
        elif options.command == "redact":
            text = options.path.read_text(encoding="utf-8") if options.path else sys.stdin.read()
            content, counts = redact_text(text)
            result = {"content": content, "redactions": counts}
        else:
            result = check_postmortem_args(options.rest)
    except GuardError as exc:
        _print_error(str(exc))
        return 2
    except OSError as exc:
        _print_error(str(exc))
        return 2

    print(json.dumps(result, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
