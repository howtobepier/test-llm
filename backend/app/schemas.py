from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Quello che il client ci manda. Mi aspetto un JSON con un campo message."""
    message: str = Field(min_length=1, description="Messaggio dell'utente")


class ChatResponse(BaseModel):
    """Quello che noi restituiamo."""
    reply: str