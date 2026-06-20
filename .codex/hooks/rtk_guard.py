from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path

NOISY_COMMANDS = {
    "cp": "rtk run 'cp ...'",
    "date": "rtk run 'date ...'",
    "find": "rtk find ...",
    "jq": "rtk json ...",
    "ln": "rtk run 'ln ...'",
    "ls": "rtk ls ...",
    "mkdir": "rtk run 'mkdir ...'",
    "pwd": "rtk run 'pwd'",
    "rm": "rtk run 'rm ...'",
    "rg": "rtk grep ...",
    "sed": "rtk run 'sed ...'",
    "sqlite3": "rtk run 'sqlite3 ...'",
    "tee": "rtk run 'tee ...'",
}

PYTHON_JSON_TOOL = re.compile(r"(?:^|[/\\])python(?:3(?:\.\d+)?)?\s+-m\s+json\.tool(?:\s|$)")
PYTHON_PYRIGHT = re.compile(r"(?:^|[/\\])python(?:3(?:\.\d+)?)?\s+-m\s+pyright(?:\s|$)")
PYTHON_PYTEST = re.compile(r"(?:^|[/\\])python(?:3(?:\.\d+)?)?\s+-m\s+pytest(?:\s|$)")
PYTHON_COMMANDS = {"python", "python3"}
RTK_GIT_SUBCOMMANDS = {"add", "branch", "commit", "diff", "fetch", "log", "pull", "push", "rev-parse", "show", "status", "stash", "worktree"}
SHELL_OPERATORS = {";", "&&", "||", "|"}
REDIRECT_OPERATORS = {">", ">>", "1>", "1>>", "2>", "2>>", "&>", "&>>"}
COMMAND_SUBSTITUTION = re.compile(r"\$\(\s*([^()]+?)\s*\)")


def main() -> int:
    command = _read_command()
    if not command.strip():
        return 0

    violations = _find_violations(command)
    if not violations:
        return 0

    seen = []
    for raw_command, replacement in violations:
        item = f"{raw_command} -> {replacement}"
        if item not in seen:
            seen.append(item)

    reason = (
        "RTK obligatoire pour commandes potentiellement bruyantes: "
        + ", ".join(seen)
    )
    print(reason, file=sys.stderr)
    print(json.dumps({"permissionDecision": "deny", "permissionDecisionReason": reason}))
    return 2


def _read_command() -> str:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return ""

    if not isinstance(payload, dict):
        return ""

    tool_input = payload.get("tool_input") or payload.get("input") or payload
    if not isinstance(tool_input, dict):
        return ""

    command = tool_input.get("command") or tool_input.get("cmd")
    return str(command or "")


def _find_violations(command: str) -> list[tuple[str, str]]:
    violations: list[tuple[str, str]] = []
    violations.extend(_command_substitution_violations(command))
    for segment in _command_segments(command):
        violation = _segment_violation(segment)
        if violation is not None:
            violations.append(violation)
    return violations


def _command_segments(command: str) -> list[str]:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return [command]

    segments: list[list[str]] = [[]]
    for token in tokens:
        if token in SHELL_OPERATORS:
            segments.append([])
            continue
        segments[-1].append(token)
    return [" ".join(segment) for segment in segments if segment]


def _segment_violation(segment: str) -> tuple[str, str] | None:
    stripped = segment.strip()
    if not stripped:
        return None

    try:
        parts: list[str] = shlex.split(stripped, posix=True)
    except ValueError:
        return None

    while parts and _is_env_assignment(parts[0]):
        parts.pop(0)
    if not parts or parts[0] == "graphify":
        return None

    if parts[0] == "rtk":
        return _rtk_violation(parts)

    base_command = Path(parts[0]).name
    if base_command == "cat":
        return _cat_violation(parts)
    if base_command in PYTHON_COMMANDS:
        return _python_violation(stripped) or (
            "python direct",
            "rtk run 'python ...' ou rtk test .venv/bin/python -m pytest ...",
        )
    if base_command == "grep":
        return _grep_violation(parts)
    if base_command == "git":
        return _git_violation(parts)
    if base_command == "ruff":
        return _ruff_violation(parts)
    if base_command in NOISY_COMMANDS:
        return base_command, NOISY_COMMANDS[base_command]

    if PYTHON_PYTEST.search(stripped):
        return "python -m pytest", "rtk test .venv/bin/python -m pytest ..."
    if PYTHON_PYRIGHT.search(stripped):
        return "python -m pyright", "rtk run '.venv/bin/python -m pyright'"
    if PYTHON_JSON_TOOL.search(stripped):
        return "python -m json.tool", "rtk json ..."

    return None


def _python_violation(segment: str) -> tuple[str, str] | None:
    if PYTHON_PYTEST.search(segment):
        return "python -m pytest", "rtk test .venv/bin/python -m pytest ..."
    if PYTHON_PYRIGHT.search(segment):
        return "python -m pyright", "rtk run '.venv/bin/python -m pyright'"
    if PYTHON_JSON_TOOL.search(segment):
        return "python -m json.tool", "rtk json ..."
    return None


def _rtk_violation(parts: list[str]) -> tuple[str, str] | None:
    if len(parts) < 3 or parts[1] not in {"run", "proxy"}:
        return None

    command = " ".join(parts[2:])
    try:
        nested_parts = shlex.split(command, posix=True)
    except ValueError:
        nested_parts = parts[2:]

    if not nested_parts:
        return None

    if Path(nested_parts[0]).name == "cat":
        return _cat_violation(nested_parts, rtk_wrapped=True)
    return None


def _command_substitution_violations(command: str) -> list[tuple[str, str]]:
    violations: list[tuple[str, str]] = []
    for match in COMMAND_SUBSTITUTION.finditer(command):
        violation = _segment_violation(match.group(1))
        if violation is not None:
            violations.append(violation)
    return violations


def _grep_violation(parts: list[str]) -> tuple[str, str] | None:
    return "grep", "rtk grep ..."


def _git_violation(parts: list[str]) -> tuple[str, str] | None:
    if len(parts) < 2:
        return None
    subcommand = parts[1]
    if subcommand in RTK_GIT_SUBCOMMANDS:
        return f"git {subcommand}", f"rtk git {subcommand} ..."
    return None


def _ruff_violation(parts: list[str]) -> tuple[str, str] | None:
    if len(parts) >= 3 and parts[1] == "check" and _targets_broad_path(parts[2:]):
        return "ruff check", "rtk ruff check ..."
    return None


def _cat_violation(
    parts: list[str], *, rtk_wrapped: bool = False
) -> tuple[str, str] | None:
    has_path_operand = any(
        part not in REDIRECT_OPERATORS and not part.startswith("-") for part in parts[1:]
    )
    has_redirect = any(part in REDIRECT_OPERATORS for part in parts[1:])
    if not has_path_operand and not has_redirect:
        return None
    if rtk_wrapped:
        return "rtk cat bypass", "rtk read -l aggressive <fichier>"
    if has_redirect:
        return "cat redirect", "rtk run 'tee fichier >/dev/null' ou apply_patch"
    return "cat file", "rtk read -l aggressive <fichier>"


def _targets_broad_path(args: list[str]) -> bool:
    targets = [arg for arg in args if not arg.startswith("-")]
    return not targets or any(target in {".", "./"} or target.endswith("/") for target in targets)


def _is_env_assignment(value: str) -> bool:
    name, sep, _ = value.partition("=")
    return bool(sep) and bool(name) and name.replace("_", "").isalnum() and not name[0].isdigit()


if __name__ == "__main__":
    sys.exit(main())
