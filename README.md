# JARVIS — assistente personale locale

Assistente personale utilizzabile sul computer, con interfaccia testuale e vocale, memoria Markdown, attività, agenda, promemoria, routine e modello locale tramite **Ollama**. Nessun fallback a servizi AI cloud.

## Requisiti

- Windows 10/11 (script di avvio PowerShell inclusi)
- Python 3.10+
- Node.js 20+
- [Ollama](https://ollama.com) con un modello locale (predefinito: `llama3.2:3b`)

Internet serve per installazione e download iniziali (dipendenze, modello Ollama, eventuale modello Whisper). Dopo l’installazione le funzioni locali restano disponibili offline.

## Installazione (una tantum)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
copy config\apps.example.json config\apps.json
copy config\routines.example.json config\routines.json

# Modello LLM (già presente se lo hai scaricato)
ollama pull llama3.2:3b

cd ..\frontend
npm install
```

Il primo uso della trascrizione vocale scarica il modello Whisper configurato (`VOICE_STT_MODEL=tiny`, ~75 MB).

## Avvio ordinario

```powershell
.\scripts\start.ps1
```

Oppure in due terminali:

```powershell
# Terminale 1
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminale 2
cd frontend
npm start
```

Apri [http://localhost:4200](http://localhost:4200). API: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

Diagnostica: `.\scripts\diagnose.ps1`

## Cosa fa

| Area | Dettaglio |
| --- | --- |
| Comandi diretti | Ora, note, attività, agenda, promemoria, app consentite, stato sistema, briefing — **senza** modello |
| Modello locale | Conversazione/sintesi via Ollama, streaming, timeout, coda, contesto limitato |
| Memoria | Vault Obsidian in `backend/vault/` (`raw/`, `wiki/`, `outputs/` + preferenze) — se non è nel vault, non è successo |
| Voce | Push-to-talk → STT `faster-whisper` → esecuzione → TTS locale Windows (`pyttsx3`/SAPI) |
| Routine | Scheduler in-process (`backend/config/routines.json`), ore silenziose, anti-duplicato |
| Integrazioni | Email, notizie, calendario esterno, social: **non configurato** (niente dati finti) |

## Dove stanno i dati

- Note/memoria: vault Obsidian `backend/vault/` (`raw` catture, `wiki` conoscenza collegata, `outputs` generati). Apri la cartella in Obsidian per il grafo.
- Attività, eventi, promemoria, metriche, indice note, log azioni, routine: SQLite `backend/data/jarvis.db` (indici/stato ricostruibili)
- App consentite: `backend/config/apps.json`
- Routine: `backend/config/routines.json`
- Metriche CSV opzionali: `backend/data/metrics.csv` (vedi `metrics.csv.example`)

## Modello e prestazioni

Configurazione predefinita: **`llama3.2:3b` (Q4_K_M)** su Ollama locale.

Motivazione tipica su PC senza GPU NVIDIA e ~16 GB RAM: più reattivo di `llama3.1` 8B sulla sola CPU, licenza Meta Llama accettabile per uso locale, italiano utilizzabile. La configurazione precedente resta in `.env` / `.env.example` (es. `llama3.1:latest`).

Parametri rilevanti in `backend/.env`:

- `OLLAMA_NUM_CTX=2048`
- `OLLAMA_NUM_PREDICT=256`
- `OLLAMA_KEEP_ALIVE=30m`
- `OLLAMA_TIMEOUT_S=90`
- `OLLAMA_PRELOAD=true`

Lo streaming migliora la percezione dell’attesa, non la velocità di generazione del modello.

## Sicurezza (implementata nel codice)

- Registro chiuso degli strumenti
- Nessuna shell arbitraria né `eval` dal modello
- Percorsi vincolati al vault
- Servizio in ascolto su `127.0.0.1` di default
- CORS limitato al frontend locale
- Segreti fuori dal repository (`.env` ignorato)
- Nessuna telemetria esterna predefinita

## Routine e avvio automatico

Le routine di esempio (07:00 briefing, 09:00 priorità, 14:00 metriche, 19:00 riepilogo) girano **solo mentre JARVIS è in esecuzione**. Con il computer spento o sospeso non partono; al risveglio può applicarsi la politica `run_once_on_wake` (vedi `routines.json`).

L’avvio automatico di Windows **non** viene abilitato silenziosamente. Se lo desideri, crea tu un’attività Pianificazione o un collegamento a `scripts\start.ps1`.

## Test

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m unittest tests.test_acceptance -v
```

## Dieci comandi da provare

1. `che ore sono`
2. `stato sistema`
3. `salva nota Idee: provare JARVIS oggi`
4. `cerca note Idee`
5. `aggiungi attività scrivere report priorità 1`
6. `attività aperte`
7. `completa attività scrivere report`
8. `ricordami caffè alle 15:30`
9. `agenda oggi`
10. `briefing`

## Licenze componenti principali

- FastAPI, Uvicorn, Pydantic: licenze permissive (BSD/MIT)
- faster-whisper: MIT; modelli Whisper: licenza MIT
- pyttsx3: licenza permissive; voci SAPI: componente Windows
- Ollama / pesi Llama: rispettare i termini Meta Llama e Ollama
