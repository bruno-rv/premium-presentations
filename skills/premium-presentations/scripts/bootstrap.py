#!/usr/bin/env python3
"""Check and install the dependencies used by browser-backed validation.

The check path only inspects the active environment.  Installation is explicit
and uses the same Python interpreter that invoked this script, so a virtualenv
or user-managed Python receives both Playwright and its managed Chromium.
"""
from __future__ import annotations

import argparse
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence


MIN_PYTHON = (3, 10)
MIN_NODE = 18
REQUIREMENTS_PATH = Path(__file__).resolve().with_name("requirements.txt")


def python_version_supported(version_info: Sequence[int] | None = None) -> bool:
    """Return whether a Python version is supported by the skill."""
    version = version_info if version_info is not None else sys.version_info
    return tuple(version[:2]) >= MIN_PYTHON


def check_python_version(version_info: Sequence[int] | None = None) -> bool:
    """Compatibility alias for callers that prefer a check-style name."""
    return python_version_supported(version_info)


def parse_node_version(output: str) -> tuple[int, int, int] | None:
    """Parse ``node --version`` output, accepting the usual leading ``v``."""
    match = re.search(r"\bv?(\d+)\.(\d+)(?:\.(\d+))?\b", output.strip())
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3) or 0))


def node_version_supported(version: str | Sequence[int] | None) -> bool:
    """Return whether a parsed Node version meets the Node 18 requirement."""
    if isinstance(version, str):
        version = parse_node_version(version)
    return version is not None and int(version[0]) >= MIN_NODE


def check_node_version(version: str | Sequence[int] | None) -> bool:
    """Compatibility alias for callers that prefer a check-style name."""
    return node_version_supported(version)


def _node_version() -> tuple[int, int, int] | None:
    try:
        completed = subprocess.run(
            ["node", "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return parse_node_version(completed.stdout)


def _check_playwright() -> tuple[bool, str]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, "Playwright is not installed"

    try:
        with sync_playwright() as playwright:
            executable = Path(playwright.chromium.executable_path)
    except Exception as exc:  # pragma: no cover - driver errors vary by host
        return False, f"Playwright could not start: {exc}"
    if not executable.is_file():
        return False, "managed Chromium is not installed"
    return True, f"managed Chromium found at {executable}"


def _check_prerequisites() -> list[tuple[bool, str]]:
    checks: list[tuple[bool, str]] = []
    python_ok = python_version_supported()
    current_python = ".".join(str(part) for part in sys.version_info[:3])
    checks.append(
        (
            python_ok,
            f"Python {current_python} (requires >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]})",
        )
    )

    node = _node_version()
    if node is None:
        checks.append((False, "Node.js is missing or did not report a version (requires >= 18)"))
    else:
        checks.append(
            (
                node_version_supported(node),
                f"Node.js {node[0]}.{node[1]}.{node[2]} (requires >= 18)",
            )
        )

    bash = shutil.which("bash")
    checks.append((bash is not None, f"Bash {'found at ' + bash if bash else 'is missing'}"))
    checks.append(_check_playwright())
    return checks


def install_commands(requirements_path: Path | None = None) -> list[list[str]]:
    """Build the explicit, interpreter-bound dependency install commands."""
    requirements = Path(requirements_path or REQUIREMENTS_PATH)
    python = sys.executable
    return [
        [python, "-m", "pip", "install", "-r", str(requirements)],
        [python, "-m", "playwright", "install", "chromium"],
    ]


def run_command(command: Sequence[str]) -> None:
    """Run one generated install command, raising a useful subprocess error."""
    subprocess.run(list(command), check=True)


def _check() -> int:
    checks = _check_prerequisites()
    for ok, message in checks:
        print(f"{'OK' if ok else 'MISSING'}: {message}")
    return 0 if all(ok for ok, _ in checks) else 1


def _install_browser_deps() -> int:
    if not python_version_supported():
        current = ".".join(str(part) for part in sys.version_info[:3])
        print(
            f"Cannot install browser dependencies: Python {current} is unsupported; "
            f"use Python >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}.",
            file=sys.stderr,
        )
        return 1

    for command in install_commands():
        print(f"$ {shlex.join(command)}")
        try:
            run_command(command)
        except (OSError, subprocess.CalledProcessError) as exc:
            detail = getattr(exc, "returncode", None)
            suffix = f" (exit {detail})" if detail is not None else f": {exc}"
            print(f"Bootstrap failed while running {shlex.join(command)}{suffix}", file=sys.stderr)
            return 1
    print("Browser dependencies installed.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check", action="store_true", help="report prerequisites without changing files")
    modes.add_argument(
        "--install-browser-deps",
        action="store_true",
        help="install Playwright and its managed Chromium with the active Python",
    )
    args = parser.parse_args(argv)
    return _check() if args.check else _install_browser_deps()


if __name__ == "__main__":
    raise SystemExit(main())
