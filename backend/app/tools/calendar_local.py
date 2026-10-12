from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.db import db, utc_now
from app.tools.registry import ToolResult, register


def local_tz():
    return datetime.now().astimezone().tzinfo or ZoneInfo("UTC")


def parse_italian_datetime(text: str) -> datetime | None:
    """Parser esplicito per date/ore italiane non ambigue."""
    text = " ".join(text.strip().lower().split())
    now = datetime.now().astimezone()
    # oggi/domani alle HH:MM
    for label, days in (("oggi", 0), ("domani", 1)):
        prefix = f"{label} alle "
        if text.startswith(prefix):
            hm = text[len(prefix) :].strip()
            try:
                hour, minute = _parse_hm(hm)
            except ValueError:
                return None
            base = (now + timedelta(days=days)).replace(hour=hour, minute=minute, second=0, microsecond=0)
            return base
    # alle HH:MM (oggi se futuro, altrimenti domani)
    if text.startswith("alle "):
        try:
            hour, minute = _parse_hm(text[5:].strip())
        except ValueError:
            return None
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate
    # YYYY-MM-DD HH:MM oppure DD/MM/YYYY HH:MM
    for fmt in ("%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M", "%d-%m-%Y %H:%M"):
        try:
            dt = datetime.strptime(text, fmt)
            return dt.replace(tzinfo=local_tz())
        except ValueError:
            continue
    return None


def _parse_hm(hm: str) -> tuple[int, int]:
    hm = hm.replace(".", ":")
    if ":" in hm:
        h, m = hm.split(":", 1)
        return int(h), int(m)
    if hm.isdigit() and 0 <= int(hm) <= 23:
        return int(hm), 0
    raise ValueError("ora non valida")


def _row(r) -> dict[str, Any]:
    return {
        "id": r["id"],
        "title": r["title"],
        "starts_at": r["starts_at"],
        "ends_at": r["ends_at"],
        "notes": r["notes"],
    }


@register("add_event")
def add_event(title: str, when: str, notes: str | None = None) -> ToolResult:
    title = title.strip()
    if not title:
        return ToolResult(ok=False, summary="Titolo evento obbligatorio", error="args")
    dt = parse_italian_datetime(when)
    if dt is None:
        return ToolResult(
            ok=False,
            summary="Data ambigua. Usa formati come 'domani alle 15:30' o '12/10/2026 09:00'",
            error="ambiguous_date",
        )
    event_id = uuid.uuid4().hex
    with db() as conn:
        conn.execute(
            """
            INSERT INTO events(id, title, starts_at, ends_at, notes, created_at)
            VALUES (?, ?, ?, NULL, ?, ?)
            """,
            (event_id, title, dt.isoformat(), notes, utc_now()),
        )
    return ToolResult(
        ok=True,
        summary=f"Evento creato: {title} ({dt.strftime('%d/%m/%Y %H:%M')})",
        data={"id": event_id, "title": title, "starts_at": dt.isoformat()},
    )


@register("list_agenda")
def list_agenda(day: str | None = None) -> ToolResult:
    if day:
        try:
            target = datetime.strptime(day, "%Y-%m-%d").date()
        except ValueError:
            return ToolResult(ok=False, summary="Giorno non valido (YYYY-MM-DD)", error="args")
    else:
        target = datetime.now().astimezone().date()
    prefix = target.isoformat()
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM events WHERE starts_at LIKE ? ORDER BY starts_at ASC",
            (f"{prefix}%",),
        ).fetchall()
    items = [_row(r) for r in rows]
    return ToolResult(
        ok=True,
        summary=f"Agenda del {target.strftime('%d/%m/%Y')}: {len(items)} eventi",
        data={"day": target.isoformat(), "events": items},
    )
