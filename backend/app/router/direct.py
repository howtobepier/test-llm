"""Percorso diretto: comandi italiani riconoscibili senza modello."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class DirectIntent:
    tool: str
    args: dict[str, Any]
    reply_prefix: str | None = None


_NEGATION = re.compile(
    r"\b(non|niente|senza|evita)\b",
    re.IGNORECASE,
)
_ACTION_VERB = re.compile(
    r"\b(apri|aprire|elimina|eliminare|cancella|crea|aggiungi|completa|avvia|salva)\b",
    re.IGNORECASE,
)
_META = re.compile(
    r"\b(come\s+funziona|che\s+cosa\s+fa|cosa\s+fa|spiegami|documentazione|"
    r"\bhelp\b|aiuto\s+su|esempio\s+di)\b",
    re.IGNORECASE,
)


def _norm(text: str) -> str:
    return " ".join(text.strip().lower().split())


def try_direct(text: str) -> DirectIntent | str | None:
    raw = text.strip()
    t = _norm(raw)
    if not t:
        return None

    if _META.search(t):
        return None
    if _NEGATION.search(t) and _ACTION_VERB.search(t):
        return (
            "Richiesta negata o ambigua: nessuna azione eseguita. "
            "Riformula il comando in forma affermativa se vuoi procedere."
        )

    if re.fullmatch(
        r"(che ore sono|che ora [eè]|ora attuale|data di oggi|che giorno [eè] oggi|oggi che giorno [eè])\??",
        t,
    ):
        return DirectIntent("now", {})

    if re.fullmatch(r"(stato( del)? sistema|stato pc|risorse( di)? sistema|quanto ram)", t):
        return DirectIntent("system_status", {})

    m = re.fullmatch(
        r"(?:salva(?:mi)?|crea|aggiungi)\s+nota(?:\s+titolo)?\s+(.+?)\s*:\s*(.+)",
        t,
        re.DOTALL,
    )
    if m:
        return DirectIntent("save_note", {"title": m.group(1).strip(), "body": m.group(2).strip()})
    if re.match(r"^(?:salva(?:mi)?|crea|aggiungi)\s+nota\b", t):
        return "Per salvare una nota usa: salva nota <titolo>: <testo>"

    m = re.fullmatch(r"(?:cerca|trova|ricerca)\s+note?\s+(.+)", t)
    if m:
        return DirectIntent("search_notes", {"query": m.group(1).strip()})

    m = re.fullmatch(r"(?:aggiungi|crea|nuova)\s+(?:attivit[aà]|todo|task)\s+(.+)", t)
    if m:
        rest = m.group(1).strip()
        priority = 2
        pm = re.search(r"\bpriorit[aà]\s*([123])\b", rest)
        if pm:
            priority = int(pm.group(1))
            rest = (rest[: pm.start()] + rest[pm.end() :]).strip(" ,.-")
        due = None
        dm = re.search(r"\bscadenza\s+(.+)$", rest)
        if dm:
            due = dm.group(1).strip()
            rest = rest[: dm.start()].strip(" ,.-")
        if not rest:
            return "Specifica il titolo dell'attività."
        return DirectIntent("add_todo", {"title": rest, "priority": priority, "due_at": due})

    m = re.fullmatch(r"(?:completa|segna|chiudi)\s+(?:attivit[aà]|todo|task)\s+(.+)", t)
    if m:
        return DirectIntent("complete_todo", {"title_or_id": m.group(1).strip()})

    if re.fullmatch(r"(mostrami |mostra |elenca |lista )?(le )?(attivit[aà]|todo|task)( aperte)?", t):
        return DirectIntent("list_todos", {})

    if re.fullmatch(r"(priorit[aà]( del)? giorno|tre priorit[aà]|prepara le priorit[aà])", t):
        return DirectIntent("daily_priorities", {})

    if re.fullmatch(r"(agenda( di)? oggi|mostra agenda|cosa ho in agenda)", t):
        return DirectIntent("list_agenda", {})

    if t.startswith("aggiungi evento ") or t.startswith("crea evento "):
        if "|" in raw:
            left, when = raw.split("|", 1)
            title = re.sub(r"^(aggiungi|crea)\s+evento\s+", "", left.strip(), flags=re.I).strip()
            return DirectIntent("add_event", {"title": title, "when": when.strip()})
        m2 = re.match(
            r"^(?:aggiungi|crea)\s+evento\s+(.+?)\s+((?:oggi|domani)\s+alle\s+\d{1,2}(?::\d{2})?|alle\s+\d{1,2}(?::\d{2})?|\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2})$",
            t,
        )
        if m2:
            return DirectIntent("add_event", {"title": m2.group(1).strip(), "when": m2.group(2).strip()})
        return "Per un evento usa: crea evento <titolo> | domani alle 15:00"

    if t.startswith("promemoria ") or t.startswith("ricordami "):
        m2 = re.match(
            r"^(?:promemoria|ricordami(?: di)?)\s+(.+?)\s+((?:oggi|domani)\s+alle\s+\d{1,2}(?::\d{2})?|alle\s+\d{1,2}(?::\d{2})?|\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2})$",
            t,
        )
        if m2:
            return DirectIntent("add_reminder", {"title": m2.group(1).strip(), "when": m2.group(2).strip()})
        if re.fullmatch(r"(promemoria|lista promemoria|mostra promemoria)", t):
            return DirectIntent("list_reminders", {})
        return "Per un promemoria usa un orario esplicito, es. 'ricordami caffè alle 15:30'."

    if re.fullmatch(r"(promemoria|lista promemoria|mostra promemoria)", t):
        return DirectIntent("list_reminders", {})

    m = re.fullmatch(r"apri(?:\s+app)?\s+(.+)", t)
    if m:
        return DirectIntent("open_app", {"name": m.group(1).strip()})

    if re.fullmatch(r"(app consentite|elenco app|lista applicazioni)", t):
        return DirectIntent("list_apps", {})

    if re.fullmatch(r"(briefing( mattutino)?|prepara(mi)? il briefing)", t):
        return DirectIntent("briefing", {})
    if re.fullmatch(r"(riepilogo serale|riepilogo della sera)", t):
        return DirectIntent("evening_summary", {})
    if re.fullmatch(r"(aggiorna metriche)", t):
        return DirectIntent("metrics_update", {})
    if re.fullmatch(r"(metriche|statistiche attivit[aà])", t):
        return DirectIntent("metrics_stats", {})

    m = re.fullmatch(r"avvia routine\s+(.+)", t)
    if m:
        return DirectIntent("run_routine", {"routine_id": m.group(1).strip()})

    if re.fullmatch(r"(routine|prossime routine|automazioni)", t):
        return DirectIntent("list_routines", {})

    m = re.fullmatch(r"ricorda che preferisco\s+(.+)", t)
    if m:
        return DirectIntent("save_preference", {"key": "preferenza", "value": m.group(1).strip()})

    return None
