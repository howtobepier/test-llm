from __future__ import annotations

from app.scheduler.engine import load_routines, next_routines, run_routine
from app.tools.registry import ToolResult, register


@register("list_routines")
def list_routines() -> ToolResult:
    items = load_routines()
    upcoming = next_routines()
    return ToolResult(
        ok=True,
        summary=f"{len(items)} routine configurate",
        data={"routines": items, "upcoming": upcoming},
    )


@register("run_routine")
def run_routine_tool(routine_id: str) -> ToolResult:
    result = run_routine(routine_id, force=True)
    return ToolResult(
        ok=bool(result.get("ok")),
        summary=str(result.get("summary")),
        data=result.get("data"),
        error=result.get("error"),
    )
