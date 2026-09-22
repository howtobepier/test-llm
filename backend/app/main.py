import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.llm import astream_reply, generate_reply
from app.schemas import ChatRequest, ChatResponse

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


@app.post("/chat/stream")
async def chat_stream(body: ChatRequest):
    """Server-Sent Events: token in JSON, poi evento done."""

    async def event_gen():
        try:
            async for token in astream_reply(body.message):
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': f'LLM non disponibile: {exc}'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
