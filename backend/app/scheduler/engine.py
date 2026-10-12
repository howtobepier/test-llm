"""Scheduler leggero per routine persistenti."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta
from typing import Any

from app.config import (
    QUIET_HOURS_END,
    QUIET_HOURS_START,
    ROUTINES_CONFIG,
    load_json_config,
)
from app.db import db, log_action, utc_now
from app.tools.registry import execute


ACTION_MAP = {
    "briefing": ("briefing", {}),
    "daily_priorities": ("daily_priorities", {}),
    "metrics_update": ("metrics_update", {}),
    "evening_summary": ("evening_summary", {}),
}


def _parse_hhmm(value: str) -> tuple[int, int]:
    h, m = value.split(":")
    return int(h), int(m)


def in_quiet_hours(now: datetime | None = None) -> bool:
    now = now or datetime.now().astimezone()
    cfg = load_json_config(ROUTINES_CONFIG, {})
    start_s = (cfg.get("quiet_hours") or {}).get("start", QUIET_HOURS_START)
    end_s = (cfg.get("quiet_hours") or {}).get("end", QUIET_HOURS_END)
    sh, sm = _parse_hhmm(start_s)
    eh, em = _parse_hhmm(end_s)
    start = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
    end = now.replace(hour=eh, minute=em, second=0, microsecond=0)
    if start <= end:
        return start <= now < end
    return now >= start or now < end


def load_routines() -> list[dict[str, Any]]:
    data = load_json_config(ROUTINES_CONFIG, {"routines": []})
    return list(data.get("routines") or [])


def planned_key(now: datetime, hour: int, minute: int) -> str:
    return now.replace(hour=hour, minute=minute, second=0, microsecond=0).isoformat()


def next_routines(limit: int = 5) -> list[dict[str, Any]]:
    now = datetime.now().astimezone()
    upcoming: list[dict[str, Any]] = []
    for day_offset in range(0, 3):
        day = now + timedelta(days=day_offset)
        for r in load_routines():
            if not r.get("enabled", True):
                continue
            when = day.replace(hour=int(r["hour"]), minute=int(r["minute"]), second=0, microsecond=0)
            if when < now:
                continue
            upcoming.append(
                {
                    "id": r["id"],
                    "name": r.get("name") or r["id"],
                    "when": when.isoformat(),
                    "action": r.get("action"),
                    "enabled": True,
                }
            )
    upcoming.sort(key=lambda x: x["when"])
    return upcoming[:limit]


def run_routine(routine_id: str, *, force: bool = False) -> dict[str, Any]:
    routines = {r["id"]: r for r in load_routines()}
    routine = routines.get(routine_id)
    if not routine:
        # match by name
        for r in load_routines():
            if str(r.get("name", "")).lower() == routine_id.lower():
                routine = r
                break
    if not routine:
        return {"ok": False, "summary": "Routine non trovata", "error": "not_found"}
    if in_quiet_hours() and not force:
        return {"ok": False, "summary": "Ore silenziose: routine non eseguita", "error": "quiet_hours"}

    now = datetime.now().astimezone()
    planned = planned_key(now, int(routine["hour"]), int(routine["minute"]))
    # Se forziamo manualmente, usa timestamp corrente come planned_for unico.
    if force:
        planned = now.replace(second=0, microsecond=0).isoformat() + "+manual"

    run_id = uuid.uuid4().hex
    with db() as conn:
        try:
            conn.execute(
                """
                INSERT INTO routine_runs(id, routine_id, planned_for, started_at, finished_at, status, detail)
                VALUES (?, ?, ?, ?, NULL, 'running', NULL)
                """,
                (run_id, routine["id"], planned, utc_now()),
            )
        except Exception:
            return {
                "ok": False,
                "summary": "Routine già eseguita per questo slot (anti-duplicato)",
                "error": "duplicate",
            }

    action = routine.get("action")
    mapped = ACTION_MAP.get(str(action))
    if not mapped:
        with db() as conn:
            conn.execute(
                "UPDATE routine_runs SET finished_at=?, status=?, detail=? WHERE id=?",
                (utc_now(), "failed", f"Azione sconosciuta: {action}", run_id),
            )
        return {"ok": False, "summary": f"Azione routine sconosciuta: {action}", "error": "bad_action"}

    tool_name, args = mapped
    result = execute(tool_name, **args)
    status = "ok" if result.ok else "failed"
    with db() as conn:
        conn.execute(
            "UPDATE routine_runs SET finished_at=?, status=?, detail=? WHERE id=?",
            (utc_now(), status, result.summary, run_id),
        )
    log_action("routine", status, f"{routine.get('name')}: {result.summary}")
    return {
        "ok": result.ok,
        "summary": result.summary,
        "data": {"routine_id": routine["id"], "result": result.data, "run_id": run_id},
        "error": result.error,
    }


def catch_up_missed() -> list[dict[str, Any]]:
    """Politica run_once_on_wake: esegue al massimo una routine persa per id oggi."""
    cfg = load_json_config(ROUTINES_CONFIG, {})
    if cfg.get("missed_policy", "run_once_on_wake") == "skip":
        return []
    now = datetime.now().astimezone()
    if in_quiet_hours(now):
        return []
    done = []
    for r in load_routines():
        if not r.get("enabled", True):
            continue
        planned = planned_key(now, int(r["hour"]), int(r["minute"]))
        if datetime.fromisoformat(planned) > now:
            continue
        with db() as conn:
            exists = conn.execute(
                "SELECT 1 FROM routine_runs WHERE routine_id=? AND planned_for=?",
                (r["id"], planned),
            ).fetchone()
        if exists:
            continue
        # Solo se lo slot è passato da meno di 12 ore
        if now - datetime.fromisoformat(planned) > timedelta(hours=12):
            continue
        done.append(run_routine(r["id"], force=False))
    return done


class SchedulerThread:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_notifications: list[dict[str, Any]] = []

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="jarvis-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        # catch-up all'avvio
        try:
            catch_up_missed()
        except Exception as exc:  # noqa: BLE001
            log_action("scheduler", "failed", "Catch-up fallito", str(exc))
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as exc:  # noqa: BLE001
                log_action("scheduler", "failed", "Tick fallito", str(exc))
            self._stop.wait(20)

    def _tick(self) -> None:
        from app.tools import reminders as reminders_tool

        now = datetime.now().astimezone()
        # Promemoria dovuti
        for rem in reminders_tool.due_reminders(now):
            reminders_tool.mark_notified(rem["id"])
            note = {
                "kind": "reminder",
                "title": rem["title"],
                "due_at": rem["due_at"],
                "at": utc_now(),
            }
            self.last_notifications.append(note)
            self.last_notifications = self.last_notifications[-50:]
            log_action("reminder.notify", "ok", f"Promemoria: {rem['title']}")

        if in_quiet_hours(now):
            return
        for r in load_routines():
            if not r.get("enabled", True):
                continue
            if now.hour == int(r["hour"]) and now.minute == int(r["minute"]):
                run_routine(r["id"], force=False)


_scheduler = SchedulerThread()


def get_scheduler() -> SchedulerThread:
    return _scheduler
