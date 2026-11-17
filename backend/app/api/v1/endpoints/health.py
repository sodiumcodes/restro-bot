from app.api.v1.router import health_router as router

@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "message": "Cafe Chatbot API is running"
    }
