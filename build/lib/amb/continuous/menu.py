from __future__ import annotations

import sys
from typing import Any

# (display label, command name without leading /)
MENU_ITEMS: list[tuple[str, str]] = [
    ("Inspect › status", "status"),
    ("Inspect › inbox", "inbox"),
    ("Inspect › deferred", "deferred"),
    ("Inspect › trail", "trail"),
    ("Inspect › tree", "tree"),
    ("Inspect › map", "map"),
    ("Inspect › tail", "tail"),
    ("Inspect › graph", "graph"),
    ("Inspect › score", "score"),
    ("Inspect › report", "report"),
    ("Inspect › ls", "ls"),
    ("Operator › inject … (queue next /run)", "inject"),
    ("Operator › curriculum (temp sweep)", "curriculum"),
    ("Operator › ask …", "ask"),
    ("Operator › open …", "open"),
    ("Operator › use …", "use"),
    ("Operator › settings", "settings"),
    ("Operator › set …", "set"),
    ("Run › run (use /settings)", "run"),
    ("Run › daemon (use /settings)", "daemon"),
    ("Run › stop", "stop"),
    ("Repo › pull", "pull"),
    ("Repo › reinstall", "reinstall"),
    ("Repo › update", "update"),
    ("Meta › help", "help"),
    ("Meta › quit", "quit"),
]

# Commands that need a follow-up text prompt after pick.
ARG_PROMPTS: dict[str, str] = {
    "inject": "Instruction text (queued for next /run)",
    "ask": "Question",
    "open": "Relative path under active run",
    "use": "Run directory path",
    "set": "key value  (e.g. model deepseek-r1:7b)",
}

_INSTALL_HINT = 'questionary not available — pip install -e ".[dev]" (or pip install questionary)'


def _load_questionary() -> Any | None:
    try:
        import questionary  # type: ignore[import-untyped]
    except ImportError:
        return None
    return questionary


def pick_command() -> str | None:
    """Arrow-key select a command name. None = cancel or unavailable."""
    q = _load_questionary()
    if q is None:
        print(_INSTALL_HINT, file=sys.stderr)
        return None
    choices = [q.Choice(title=label, value=name) for label, name in MENU_ITEMS]
    try:
        result = q.select(
            "Command (↑/↓, Enter; Ctrl+C cancel)",
            choices=choices,
            use_indicator=True,
            use_shortcuts=False,
        ).ask()
    except (KeyboardInterrupt, EOFError):
        print()
        return None
    if result is None:
        return None
    return str(result)


def prompt_args(command: str) -> str | None:
    """Prompt for remaining args. None = cancel. '' = no args needed / empty ok."""
    if command not in ARG_PROMPTS:
        return ""
    message = ARG_PROMPTS[command]
    q = _load_questionary()
    if q is not None:
        try:
            result = q.text(f"{message}:").ask()
        except (KeyboardInterrupt, EOFError):
            print()
            return None
        if result is None:
            return None
        return str(result).strip()
    # Fallback when questionary missing but caller still wants args.
    try:
        return input(f"{message}: ").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        return None


def build_slash_line(command: str, args_text: str) -> str:
    args_text = (args_text or "").strip()
    if not args_text:
        return f"/{command}"
    return f"/{command} {args_text}"
