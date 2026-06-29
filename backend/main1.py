from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from backend.api import router as api_router
from backend.agent import AutomotiveAgent

app = FastAPI(title="Dubizzle Agent Backend")

# Initialize our AI Agent globally so it stays active while the server runs
agent = AutomotiveAgent()

# Define the expected JSON payload for the chat endpoint
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: str = "guest_user"

# Register the router we built in api.py
    session_id: Optional[str] = None
    user_id: str = "guest_user"

# Endpoint for checking the health
@app.get("/health")
def health_check():
    return {"status": "healthy", "message": "Backend is running!"}

@app.get("/")
def root():
    return {"message": "Dubizzle AI Agent Backend is running."}

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        reply, session_id = agent.handle_message(
            user_message=request.message,
            session_id=request.session_id,
            user_id=request.user_id
        )
        return {"reply": reply, "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# You can run this with: uvicorn backend.main:app --reload