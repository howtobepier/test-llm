import os
from collections.abc import AsyncIterator, Iterator
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama

# Carica le variabili da backend/.env
load_dotenv()

_model_name = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
_base_url = os.getenv("OLLAMA_BASE_URL")  # può essere None


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return int(raw)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return float(raw)


def _chunk_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(content)


_llm_kwargs: dict[str, Any] = {
    "model": _model_name,
    # Contesto ridotto: niente cronologia lato modello → meno lavoro per token.
    "num_ctx": _env_int("OLLAMA_NUM_CTX", 2048),
    # Cap sulla lunghezza della risposta → genera meno token.
    "num_predict": _env_int("OLLAMA_NUM_PREDICT", 512),
    # Evita di scaricare il modello tra una richiesta e l'altra.
    "keep_alive": os.getenv("OLLAMA_KEEP_ALIVE", "30m"),
    "temperature": _env_float("OLLAMA_TEMPERATURE", 0.7),
}
if _base_url:
    _llm_kwargs["base_url"] = _base_url

# Crea il modello una volta sola (quando importi questo file)
_llm = ChatOllama(**_llm_kwargs)


def generate_reply(message: str) -> str:
    """Manda il messaggio a Ollama e torna il testo della risposta completa."""
    result = _llm.invoke([HumanMessage(content=message)])
    return _chunk_text(result.content)


def stream_reply(message: str) -> Iterator[str]:
    """Genera la risposta a pezzi (token/chunk) per lo streaming HTTP."""
    for chunk in _llm.stream([HumanMessage(content=message)]):
        text = _chunk_text(chunk.content)
        if text:
            yield text


async def astream_reply(message: str) -> AsyncIterator[str]:
    """Versione async di stream_reply."""
    async for chunk in _llm.astream([HumanMessage(content=message)]):
        text = _chunk_text(chunk.content)
        if text:
            yield text
