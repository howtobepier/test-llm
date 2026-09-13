from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.schemas import ChatRequest, ChatResponse
from app.llm import generate_reply

app = FastAPI(title="test-llm")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://127.0.0.1:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/statu-model-server")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest):
    try:
        reply = generate_reply(body.message)
        return ChatResponse(reply=reply)
    except Exception as exc:
        # Es. Ollama spento
        raise HTTPException(status_code=503, detail=f"LLM non disponibile: {exc}") from exc