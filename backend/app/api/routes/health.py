#APIRouter lets us organize endpoints into separate files and register them with the main application. 
from fastapi import APIRouter

# Create a router for health-related endpoints
router = APIRouter(tags=["Health"])

@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "message": "Cafe Chatbot API is running"
    }
