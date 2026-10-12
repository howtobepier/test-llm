"""Registro chiuso degli strumenti consentiti."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.db import log_action


@dataclass
class ToolResult:
    ok: bool
    summary: str
    data: dict[str, Any] | None = None
    error: str | None = None


ToolFn = Callable[..., ToolResult]

_REGISTRY: dict[str, ToolFn] = {}


def register(name: str):
    def deco(fn: ToolFn) -> ToolFn:
        _REGISTRY[name] = fn
        return fn

    return deco


def list_tools() -> list[str]:
    return sorted(_REGISTRY)


# Letture usate dalla dashboard: non intasare il log azioni.
_SILENT_OK_TOOLS = {
    "list_todos",
    "list_agenda",
    "list_reminders",
    "list_recent_notes",
    "list_routines",
    "daily_priorities",
    "search_notes",
    "open_note",
    "list_apps",
}


def execute(name: str, *, _log: bool = True, **kwargs: Any) -> ToolResult:
    if name not in _REGISTRY:
        log_action("tool", "failed", f"Strumento non consentito: {name}")
        return ToolResult(ok=False, summary="Strumento non consentito", error=name)
    try:
        result = _REGISTRY[name](**kwargs)
        should_log = _log and not (result.ok and name in _SILENT_OK_TOOLS)
        if should_log:
            log_action(
                f"tool.{name}",
                "ok" if result.ok else "failed",
                result.summary,
                result.error,
            )
        return result
    except Exception as exc:  # noqa: BLE001 - superficie strumento
        log_action(f"tool.{name}", "failed", "Errore strumento", str(exc))
        return ToolResult(ok=False, summary="Errore durante l'esecuzione", error=str(exc))


def import_all() -> None:
    # Import lazy per registrare i decorator.
    from app.tools import (  # noqa: F401
        apps,
        briefing,
        calendar_local,
        metrics,
        notes,
        preferences,
        reminders,
        routines_tool,
        system_info,
        todos,
    )
