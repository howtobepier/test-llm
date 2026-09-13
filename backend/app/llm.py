import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

# Carica le variabili da backend/.env
load_dotenv()

_model_name = os.getenv("OLLAMA_MODEL", "llama3.1")
_base_url = os.getenv("OLLAMA_BASE_URL")  # può essere None

# Crea il modello una volta sola (quando importi questo file)
if _base_url:
    _llm = ChatOllama(model=_model_name, base_url=_base_url)
else:
    _llm = ChatOllama(model=_model_name)


def generate_reply(message: str) -> str:
    """Manda il messaggio a Ollama e torna il testo della risposta."""
    result = _llm.invoke([HumanMessage(content=message)])
    # result.content è di solito una stringa
    return result.content if isinstance(result.content, str) else str(result.content)