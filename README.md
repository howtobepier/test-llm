# Personal Assistant (test-llm)

Assistente personale: **Python + LangChain + FastAPI** (backend) e **Angular** (frontend), con **Ollama** (LLM locale/gratuito).

## Struttura

```text
test-llm/
├── backend/
│   ├── .env.example
│   ├── requirements.txt
│   ├── app/              # FastAPI + LangChain
│   └── data/docs/        # documenti per RAG (futuro)
└── frontend/             # Angular (da generare con CLI)
```

## Prerequisiti Ollama

1. Installa Ollama: https://ollama.com
2. Scarica un modello, ad esempio:
   ```powershell
   ollama pull llama3.1
   ```
3. Verifica che sia in esecuzione (`ollama list`)

## Config

Copia `backend/.env.example` → `backend/.env` (valori già ok per Ollama locale).

## Prossimi passi

1. Implementare `app/main.py`, `schemas.py`, `llm.py` (ChatOllama)
2. Generare Angular in `frontend/` con `ng new`
