from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.db import db, utc_now
from app.tools.registry import ToolResult, register


def _row(r) -> dict[str, Any]:
    return {
        "id": r["id"],
        "title": r["title"],
        "priority": r["priority"],
        "due_at": r["due_at"],
        "done": bool(r["done"]),
        "created_at": r["created_at"],
        "completed_at": r["completed_at"],
    }


@register("add_todo")
def add_todo(title: str, priority: int = 2, due_at: str | None = None) -> ToolResult:
    title = title.strip()
    if not title:
        return ToolResult(ok=False, summary="Titolo attività obbligatorio", error="args")
    priority = max(1, min(int(priority), 3))
    todo_id = uuid.uuid4().hex
    with db() as conn:
        conn.execute(
            """
            INSERT INTO todos(id, title, priority, due_at, done, created_at)
            VALUES (?, ?, ?, ?, 0, ?)
            """,
            (todo_id, title, priority, due_at, utc_now()),
        )
    return ToolResult(
        ok=True,
        summary=f"Attività aggiunta: {title}",
        data={"id": todo_id, "title": title, "priority": priority, "due_at": due_at},
    )


@register("complete_todo")
def complete_todo(title_or_id: str) -> ToolResult:
    key = title_or_id.strip()
    if not key:
        return ToolResult(ok=False, summary="Specifica l'attività da completare", error="args")
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM todos WHERE done=0 AND (id=? OR lower(title)=lower(?)) ORDER BY created_at DESC LIMIT 1",
            (key, key),
        ).fetchone()
        if not row:
            row = conn.execute(
                "SELECT * FROM todos WHERE done=0 AND lower(title) LIKE ? ORDER BY priority ASC, created_at ASC LIMIT 1",
                (f"%{key.lower()}%",),
            ).fetchone()
        if not row:
            return ToolResult(ok=False, summary="Attività aperta non trovata", error="not_found")
        completed = utc_now()
        conn.execute(
            "UPDATE todos SET done=1, completed_at=? WHERE id=?",
            (completed, row["id"]),
        )
        data = _row(row)
        data["done"] = True
        data["completed_at"] = completed
    return ToolResult(ok=True, summary=f"Completata: {row['title']}", data=data)


@register("list_todos")
def list_todos(include_done: bool = False, limit: int = 50) -> ToolResult:
    with db() as conn:
        if include_done:
            rows = conn.execute(
                "SELECT * FROM todos ORDER BY done ASC, priority ASC, due_at IS NULL, due_at ASC LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM todos WHERE done=0 ORDER BY priority ASC, due_at IS NULL, due_at ASC LIMIT ?",
                (limit,),
            ).fetchall()
    items = [_row(r) for r in rows]
    return ToolResult(ok=True, summary=f"{len(items)} attività", data={"todos": items})


@register("daily_priorities")
def daily_priorities() -> ToolResult:
    """Tre priorità del giorno da dati reali, senza modello."""
    with db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM todos
            WHERE done=0
            ORDER BY priority ASC,
                     CASE WHEN due_at IS NULL THEN 1 ELSE 0 END,
                     due_at ASC,
                     created_at ASC
            LIMIT 3
            """
        ).fetchall()
    items = [_row(r) for r in rows]
    if not items:
        return ToolResult(ok=True, summary="Nessuna attività aperta: nessuna priorità da impostare", data={"priorities": []})
    return ToolResult(ok=True, summary="Priorità del giorno pronte", data={"priorities": items})


def completed_today() -> list[dict[str, Any]]:
    today = datetime.now().astimezone().date().isoformat()
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM todos WHERE done=1 AND completed_at LIKE ? ORDER BY completed_at DESC",
            (f"{today}%",),
        ).fetchall()
    return [_row(r) for r in rows]
