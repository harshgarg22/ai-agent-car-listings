from fastapi import APIRouter

router = APIRouter()

@router.get("/status")
def chat_status():
    """Dummy endpoint to ensure that the router is working"""
    return {
        "status": "API router is active and ready to be integrated into LLMs"
    }