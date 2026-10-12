from __future__ import annotations

from datetime import datetime

from app.memory import vault
from app.tools import reminders as reminders_tool
from app.tools import todos as todos_tool
from app.tools.calendar_local import list_agenda
from app.tools.registry import ToolResult, register


@register("briefing")
def briefing() -> ToolResult:
    now = datetime.now().astimezone()
    agenda = list_agenda()
    open_todos = todos_tool.list_todos()
    priorities = todos_tool.daily_priorities()
    rems = reminders_tool.list_reminders()
    lines = [
        f"# Briefing {now.strftime('%d/%m/%Y %H:%M')}",
        "",
        "## Agenda di oggi",
    ]
    events = (agenda.data or {}).get("events") or []
    if events:
        for e in events:
            lines.append(f"- {e['starts_at'][11:16]} · {e['title']}")
    else:
        lines.append("- Nessun evento in agenda locale.")

    lines += ["", "## Priorità"]
    for p in (priorities.data or {}).get("priorities") or []:
        lines.append(f"- [P{p['priority']}] {p['title']}")
    if not (priorities.data or {}).get("priorities"):
        lines.append("- Nessuna attività aperta.")

    lines += ["", "## Promemoria aperti"]
    rem_items = (rems.data or {}).get("reminders") or []
    upcoming = [r for r in rem_items if r.get("due_at", "").startswith(now.date().isoformat())]
    if upcoming:
        for r in upcoming:
            lines.append(f"- {r['due_at'][11:16]} · {r['title']}")
    else:
        lines.append("- Nessun promemoria per oggi.")

    lines += [
        "",
        "## Fonti esterne",
        "- Email: non configurato",
        "- Notizie: non configurato",
        "- Calendario esterno: non configurato",
    ]
    body = "\n".join(lines)
    saved = vault.build_note(
        title=f"Briefing {now.strftime('%Y-%m-%d')}",
        body=body,
        folder="outputs",
        tags=["briefing"],
        source="routine",
    )
    return ToolResult(
        ok=True,
        summary="Briefing pronto",
        data={
            "markdown": body,
            "saved": saved,
            "agenda_count": len(events),
            "open_todos": len((open_todos.data or {}).get("todos") or []),
            "integrations": {
                "email": "non_configurato",
                "notizie": "non_configurato",
            },
        },
    )


@register("evening_summary")
def evening_summary(reflection: str | None = None) -> ToolResult:
    now = datetime.now().astimezone()
    done = todos_tool.completed_today()
    open_todos = (todos_tool.list_todos().data or {}).get("todos") or []
    next_prio = (todos_tool.daily_priorities().data or {}).get("priorities") or []
    lines = [
        f"# Riepilogo serale {now.strftime('%d/%m/%Y')}",
        "",
        "## Completate oggi",
    ]
    if done:
        for t in done:
            lines.append(f"- {t['title']}")
    else:
        lines.append("- Nessuna attività completata registrata oggi.")
    lines += ["", "## Ancora aperte"]
    if open_todos:
        for t in open_todos[:10]:
            lines.append(f"- [P{t['priority']}] {t['title']}")
    else:
        lines.append("- Nessuna attività aperta.")
    lines += ["", "## Proposte per dopo"]
    for t in next_prio:
        lines.append(f"- {t['title']}")
    if reflection and reflection.strip():
        lines += ["", "## Riflessione", reflection.strip()]
    body = "\n".join(lines)
    saved = vault.build_note(
        title=f"Riepilogo serale {now.strftime('%Y-%m-%d')}",
        body=body,
        folder="outputs",
        tags=["riepilogo", "sera"],
        source="routine",
    )
    return ToolResult(ok=True, summary="Riepilogo serale salvato", data={"markdown": body, "saved": saved})
