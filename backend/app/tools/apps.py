from __future__ import annotations

import subprocess
from pathlib import Path

from app.config import APPS_CONFIG, load_json_config
from app.tools.registry import ToolResult, register


def _catalog() -> list[dict]:
    data = load_json_config(APPS_CONFIG, {"apps": []})
    return list(data.get("apps") or [])


@register("list_apps")
def list_apps() -> ToolResult:
    apps = _catalog()
    return ToolResult(
        ok=True,
        summary=f"{len(apps)} applicazioni consentite",
        data={"apps": [{"id": a.get("id"), "name": a.get("name"), "aliases": a.get("aliases", [])} for a in apps]},
    )


@register("open_app")
def open_app(name: str) -> ToolResult:
    key = name.strip().lower()
    if not key:
        return ToolResult(ok=False, summary="Nome applicazione mancante", error="args")
    for app in _catalog():
        aliases = [str(a).lower() for a in app.get("aliases", [])]
        names = {str(app.get("id", "")).lower(), str(app.get("name", "")).lower(), *aliases}
        if key not in names:
            continue
        path = str(app.get("path") or "").strip()
        if not path:
            return ToolResult(ok=False, summary="Percorso non configurato", error="config")
        try:
            # Solo percorso/eseguibile dalla lista consentita: nessuna shell arbitraria.
            if Path(path).suffix.lower() in {".exe", ".bat", ".cmd"} or path.lower().endswith(".exe"):
                subprocess.Popen([path], shell=False)  # noqa: S603
            else:
                # Comandi di sistema Windows noti nella allowlist (es. notepad.exe senza path).
                subprocess.Popen([path], shell=False)  # noqa: S603
        except OSError as exc:
            return ToolResult(ok=False, summary=f"Impossibile aprire {app.get('name')}", error=str(exc))
        return ToolResult(
            ok=True,
            summary=f"Apertura avviata: {app.get('name')}",
            data={"id": app.get("id"), "name": app.get("name")},
        )
    return ToolResult(
        ok=False,
        summary="Applicazione non presente nella lista consentita",
        error="not_allowed",
        data={"hint": "Modifica backend/config/apps.json"},
    )
