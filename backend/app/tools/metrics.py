from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from app.config import METRICS_CSV
from app.db import db
from app.tools.registry import ToolResult, register
from app.tools import todos as todos_tool


@register("metrics_update")
def metrics_update() -> ToolResult:
    """Aggiorna metriche locali reali (attività). CSV opzionale se presente."""
    today = datetime.now().astimezone().date().isoformat()
    open_count = len((todos_tool.list_todos().data or {}).get("todos") or [])
    done_today = len(todos_tool.completed_today())
    with db() as conn:
        for name, value in (("todos_open", open_count), ("todos_done_today", done_today)):
            conn.execute(
                """
                INSERT INTO metrics(day, name, value, source)
                VALUES (?, ?, ?, 'local')
                ON CONFLICT(day, name, source) DO UPDATE SET value=excluded.value
                """,
                (today, name, float(value)),
            )
    imported = 0
    if METRICS_CSV.exists():
        imported = _import_csv(METRICS_CSV)
    return ToolResult(
        ok=True,
        summary=f"Metriche aggiornate (CSV importati: {imported})",
        data={
            "day": today,
            "todos_open": open_count,
            "todos_done_today": done_today,
            "csv_imported": imported,
            "social": "non_configurato",
        },
    )


def _import_csv(path: Path) -> int:
    """
    Formato CSV documentato:
    day,name,value
    2026-10-11,passi,8000
    """
    count = 0
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        with db() as conn:
            for row in reader:
                day = (row.get("day") or "").strip()
                name = (row.get("name") or "").strip()
                try:
                    value = float(row.get("value"))
                except (TypeError, ValueError):
                    continue
                if not day or not name:
                    continue
                conn.execute(
                    """
                    INSERT INTO metrics(day, name, value, source)
                    VALUES (?, ?, ?, 'csv')
                    ON CONFLICT(day, name, source) DO UPDATE SET value=excluded.value
                    """,
                    (day, name, value),
                )
                count += 1
    return count


@register("metrics_stats")
def metrics_stats(limit: int = 30) -> ToolResult:
    with db() as conn:
        rows = conn.execute(
            "SELECT day, name, value, source FROM metrics ORDER BY day DESC, name ASC LIMIT ?",
            (limit,),
        ).fetchall()
    items = [dict(r) for r in rows]
    return ToolResult(ok=True, summary=f"{len(items)} metriche", data={"metrics": items})
