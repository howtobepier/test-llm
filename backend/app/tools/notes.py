from __future__ import annotations

from app.memory import vault
from app.tools.registry import ToolResult, register


@register("save_note")
def save_note(title: str, body: str, folder: str = "raw", tags: list[str] | None = None) -> ToolResult:
    if not title.strip() or not body.strip():
        return ToolResult(ok=False, summary="Titolo e testo della nota sono obbligatori", error="args")
    data = vault.build_note(title.strip(), body.strip(), folder=folder, tags=tags or [])
    return ToolResult(ok=True, summary=f"Nota salvata in {data['relative']}", data=data)


@register("search_notes")
def search_notes(query: str, tag: str | None = None, limit: int = 10) -> ToolResult:
    if not query.strip():
        return ToolResult(ok=False, summary="Query vuota", error="args")
    hits = vault.search_notes(query.strip(), tag=tag, limit=max(1, min(limit, 50)))
    if not hits:
        return ToolResult(ok=True, summary="Nessuna nota trovata", data={"results": []})
    return ToolResult(
        ok=True,
        summary=f"Trovate {len(hits)} note",
        data={"results": hits, "sources": [h["path"] for h in hits]},
    )


@register("open_note")
def open_note(path: str) -> ToolResult:
    try:
        data = vault.open_note_path(path)
    except Exception as exc:  # noqa: BLE001
        return ToolResult(ok=False, summary="Impossibile aprire la nota", error=str(exc))
    return ToolResult(ok=True, summary=f"Nota: {data['title']}", data=data)


@register("list_recent_notes")
def list_recent_notes(limit: int = 8) -> ToolResult:
    hits = vault.recent_notes(limit=max(1, min(int(limit or 8), 30)))
    if not hits:
        return ToolResult(ok=True, summary="Nessuna nota nel vault", data={"results": []})
    return ToolResult(ok=True, summary=f"{len(hits)} note recenti", data={"results": hits})
