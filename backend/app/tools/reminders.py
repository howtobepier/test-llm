from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.db import db, utc_now
from app.tools.calendar_local import parse_italian_datetime
from app.tools.registry import ToolResult, register


def _row(r) -> dict[str, Any]:
    return {
        "id": r["id"],
        "title": r["title"],
        "due_at": r["due_at"],
        "notified_at": r["notified_at"],
        "done": bool(r["done"]),
    }


@register("add_reminder")
def add_reminder(title: str, when: str) -> ToolResult:
    title = title.strip()
    if not title:
        return ToolResult(ok=False, summary="Titolo promemoria obbligatorio", error="args")
    dt = parse_italian_datetime(when)
    if dt is None:
        return ToolResult(
            ok=False,
            summary="Orario ambiguo. Esempio: 'promemoria chiama Marco domani alle 10:00'",
            error="ambiguous_date",
        )
    rid = uuid.uuid4().hex
    with db() as conn:
        conn.execute(
            """
            INSERT INTO reminders(id, title, due_at, notified_at, done, created_at)
            VALUES (?, ?, ?, NULL, 0, ?)
            """,
            (rid, title, dt.isoformat(), utc_now()),
        )
    return ToolResult(
        ok=True,
        summary=f"Promemoria impostato: {title} alle {dt.strftime('%d/%m/%Y %H:%M')}",
        data={"id": rid, "title": title, "due_at": dt.isoformat()},
    )


@register("list_reminders")
def list_reminders(include_done: bool = False) -> ToolResult:
    with db() as conn:
        if include_done:
            rows = conn.execute("SELECT * FROM reminders ORDER BY due_at ASC").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM reminders WHERE done=0 ORDER BY due_at ASC"
            ).fetchall()
    return ToolResult(ok=True, summary=f"{len(rows)} promemoria", data={"reminders": [_row(r) for r in rows]})


def due_reminders(now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now().astimezone()
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM reminders WHERE done=0 AND notified_at IS NULL AND due_at <= ? ORDER BY due_at ASC",
            (now.isoformat(),),
        ).fetchall()
    return [_row(r) for r in rows]


def mark_notified(reminder_id: str) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE reminders SET notified_at=? WHERE id=? AND notified_at IS NULL",
            (utc_now(), reminder_id),
        )


def mark_done(reminder_id: str) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE reminders SET done=1, notified_at=COALESCE(notified_at, ?) WHERE id=?",
            (utc_now(), reminder_id),
        )
