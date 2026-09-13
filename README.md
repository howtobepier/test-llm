# Personal Assistant (test-llm)

Assistente personale: **Python + LangChain + FastAPI** (backend) e **Angular Material** (frontend), con **Ollama** (LLM locale/gratuito).

## Struttura

```text
test-llm/
├── backend/
│   ├── .env.example
│   ├── requirements.txt
│   ├── app/              # FastAPI + LangChain
│   └── data/docs/        # documenti per RAG (futuro)
└── frontend/             # Angular 20 + Angular Material
```

## Prerequisiti

1. Installa Ollama: https://ollama.com
2. Scarica un modello, ad esempio:
   ```powershell
   ollama pull llama3.1
   ```
3. Verifica che sia in esecuzione (`ollama list`)
4. Node.js 20+ per il frontend

## Config backend

Copia `backend/.env.example` → `backend/.env` (valori già ok per Ollama locale).

## Avvio

Terminale 1 — backend:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

Terminale 2 — frontend:

```powershell
cd frontend
npm start
```

Poi apri `http://localhost:4200`. La chat chiama `POST http://localhost:8000/chat`.

API utili:
- `GET /statu-model-server` — health
- `POST /chat` — `{ "message": "..." }` → `{ "reply": "..." }`
- Swagger: `http://localhost:8000/docs`
