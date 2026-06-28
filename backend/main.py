from fastapi import FastAPI
from backend.api import router as chat_router

app = FastAPI(
    title= "Car Assistant API",
    description="Backend service for the car marketplace ai agent",
    version="1.0.0"
)

#endpoint for checking the health
@app.get("/health")
def health_check():
    return {"status":"healthy", "message": "Backend is running!"}

#including the router
app.include_router(chat_router, prefix="/api")