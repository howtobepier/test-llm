"""Pipeline: input → comando diretto / modello locale / degradata senza modello."""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from app.config import MEMORY_BUDGET_CHARS
from app.llm import check_ollama, get_llm_status, stream_reply
from app.memory import vault
from app.router.direct import DirectIntent, try_direct
from app.tools.registry import execute, import_all, list_tools

import_all()

_ACTION_RE = re.compile(
    r"\{[^{}]*\"tool\"\s*:\s*\"([a-z_]+)\"[^{}]*\}",
    re.IGNORECASE | re.DOTALL,
)


@dataclass
class PipelineResult:
    mode: str  # direct | llm | offline | clarify
    reply: str
    used_model: bool = False
    tool: str | None = None
    tool_ok: bool | None = None
    data: dict[str, Any] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)


def _format_tool_reply(tool: str, result) -> str:
    if not result.ok:
        return f"Operazione non riuscita ({tool}): {result.error or result.summary}"
    parts = [result.summary]
    data = result.data or {}
    if tool == "search_notes":
        for hit in data.get("results") or []:
            parts.append(f"- {hit['title']} · {hit['path']}\n  {hit['snippet']}")
        if data.get("sources"):
            parts.append("Fonti: " + "; ".join(data["sources"]))
    elif tool == "list_todos":
        for t in data.get("todos") or []:
            due = f" (scad. {t['due_at']})" if t.get("due_at") else ""
            parts.append(f"- [P{t['priority']}] {t['title']}{due}")
    elif tool == "daily_priorities":
        for t in data.get("priorities") or []:
            parts.append(f"- [P{t['priority']}] {t['title']}")
    elif tool == "list_agenda":
        for e in data.get("events") or []:
            parts.append(f"- {e['starts_at']} · {e['title']}")
    elif tool == "list_reminders":
        for r in data.get("reminders") or []:
            parts.append(f"- {r['due_at']} · {r['title']}")
    elif tool == "briefing" or tool == "evening_summary":
        parts.append(data.get("markdown") or "")
        if data.get("saved"):
            parts.append(f"Salvato in: {data['saved'].get('path')}")
    elif tool == "open_note":
        parts.append(data.get("body") or "")
        parts.append(f"Fonte: {data.get('path')}")
    elif tool == "system_status" and data:
        parts.append(
            f"OS: {data.get('os')}\nOra: {data.get('time')}"
        )
    return "\n".join(p for p in parts if p).strip()


def handle_direct_or_clarify(text: str) -> PipelineResult | None:
    parsed = try_direct(text)
    if parsed is None:
        return None
    if isinstance(parsed, str):
        return PipelineResult(mode="clarify", reply=parsed, used_model=False)
    assert isinstance(parsed, DirectIntent)
    result = execute(parsed.tool, **parsed.args)
    sources = []
    if result.data and isinstance(result.data, dict):
        if "sources" in result.data:
            sources = list(result.data["sources"])
        elif "path" in result.data:
            sources = [str(result.data["path"])]
        elif "saved" in result.data and isinstance(result.data["saved"], dict):
            sources = [str(result.data["saved"].get("path"))]
    return PipelineResult(
        mode="direct",
        reply=_format_tool_reply(parsed.tool, result),
        used_model=False,
        tool=parsed.tool,
        tool_ok=result.ok,
        data=result.data or {},
        sources=sources,
    )


def _extract_tool_proposal(text: str) -> dict[str, Any] | None:
    match = _ACTION_RE.search(text)
    if not match:
        # prova JSON puro
        try:
            obj = json.loads(text.strip())
            if isinstance(obj, dict) and "tool" in obj:
                return obj
        except json.JSONDecodeError:
            return None
        return None
    snippet = match.group(0)
    try:
        return json.loads(snippet)
    except json.JSONDecodeError:
        # un solo tentativo di riparazione: virgolette tipografiche
        repaired = snippet.replace("“", '"').replace("”", '"').replace("'", '"')
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            return None


def _validate_and_run_proposal(proposal: dict[str, Any]) -> PipelineResult | None:
    tool = str(proposal.get("tool") or "").strip()
    args = proposal.get("args") or {}
    if tool not in list_tools():
        return PipelineResult(
            mode="clarify",
            reply=f"Il modello ha proposto uno strumento non consentito ({tool}). Nessuna azione eseguita.",
            used_model=True,
        )
    if not isinstance(args, dict):
        return PipelineResult(
            mode="clarify",
            reply="Argomenti strumento non validi. Nessuna azione eseguita.",
            used_model=True,
        )
    # Non eseguire execute_shell o codice libero: solo registry chiuso.
    result = execute(tool, **args)
    return PipelineResult(
        mode="llm",
        reply=_format_tool_reply(tool, result),
        used_model=True,
        tool=tool,
        tool_ok=result.ok,
        data=result.data or {},
    )


def handle_message(
    text: str,
    history: list[dict[str, str]] | None = None,
) -> PipelineResult:
    direct = handle_direct_or_clarify(text)
    if direct is not None:
        return direct

    status = check_ollama()
    if not status.get("available"):
        return PipelineResult(
            mode="offline",
            reply=(
                "Modello locale non disponibile. "
                "Note, attività, agenda, promemoria e strumenti diretti restano usabili. "
                f"Dettaglio: {status.get('detail')}"
            ),
            used_model=False,
            data={"model_status": status},
        )

    excerpts = vault.relevant_excerpts(text, MEMORY_BUDGET_CHARS)
    # Generazione non streaming per handle_message semplice
    from app.llm import generate_reply

    try:
        reply = generate_reply(text, history=history, memory_excerpts=excerpts)
    except Exception as exc:  # noqa: BLE001
        return PipelineResult(
            mode="offline",
            reply=f"Generazione non disponibile (timeout o errore): {exc}",
            used_model=False,
        )

    proposal = _extract_tool_proposal(reply)
    if proposal:
        ran = _validate_and_run_proposal(proposal)
        if ran:
            ran.reply = reply.strip() + "\n\n" + ran.reply
            ran.sources = [e["path"] for e in excerpts]
            return ran

    sources = [e["path"] for e in excerpts]
    if excerpts:
        reply = reply.rstrip() + "\n\nFonti memoria: " + "; ".join(sources)
    elif "nota" in text.lower() or "ricord" in text.lower():
        reply = reply.rstrip() + "\n\n(Nessun estratto di memoria sufficientemente pertinente.)"

    return PipelineResult(
        mode="llm",
        reply=reply,
        used_model=True,
        sources=sources,
        data={"model_status": get_llm_status()},
    )


def stream_message(
    text: str,
    history: list[dict[str, str]] | None = None,
    cancel_event: threading.Event | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield eventi: meta, token, done/error."""
    direct = handle_direct_or_clarify(text)
    if direct is not None:
        yield {
            "type": "meta",
            "mode": direct.mode,
            "used_model": False,
            "tool": direct.tool,
            "tool_ok": direct.tool_ok,
        }
        yield {"type": "token", "token": direct.reply}
        yield {
            "type": "done",
            "mode": direct.mode,
            "used_model": False,
            "sources": direct.sources,
            "data": direct.data,
        }
        return

    status = check_ollama()
    if not status.get("available"):
        msg = (
            "Modello locale non disponibile. "
            "Gli strumenti diretti restano usabili. "
            f"Dettaglio: {status.get('detail')}"
        )
        yield {"type": "meta", "mode": "offline", "used_model": False}
        yield {"type": "token", "token": msg}
        yield {"type": "done", "mode": "offline", "used_model": False, "sources": [], "data": {"model_status": status}}
        return

    excerpts = vault.relevant_excerpts(text, MEMORY_BUDGET_CHARS)
    yield {
        "type": "meta",
        "mode": "llm",
        "used_model": True,
        "sources": [e["path"] for e in excerpts],
    }
    full: list[str] = []
    try:
        for token in stream_reply(text, history=history, memory_excerpts=excerpts, cancel_event=cancel_event):
            full.append(token)
            yield {"type": "token", "token": token}
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": f"LLM non disponibile: {exc}"}
        return

    reply = "".join(full)
    proposal = _extract_tool_proposal(reply)
    extra = ""
    tool_info: dict[str, Any] = {}
    if proposal:
        ran = _validate_and_run_proposal(proposal)
        if ran:
            extra = "\n\n" + ran.reply
            tool_info = {"tool": ran.tool, "tool_ok": ran.tool_ok, "data": ran.data}
            yield {"type": "token", "token": extra}

    sources = [e["path"] for e in excerpts]
    if sources and "Fonti memoria" not in reply:
        footnote = "\n\nFonti memoria: " + "; ".join(sources)
        yield {"type": "token", "token": footnote}

    yield {
        "type": "done",
        "mode": "llm",
        "used_model": True,
        "sources": sources,
        **tool_info,
    }
