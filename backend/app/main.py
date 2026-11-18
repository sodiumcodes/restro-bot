from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

# Initialize FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    version="1.0.0"
)

# Configure CORS so the Next.js frontend can communicate with our FastAPI backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)


# Register API routers
from app.api.v1 import router
from app.api.v1.endpoints import health
app.include_router(router.health_router)

@app.get("/")
async def root():
    return {
        "message": "Welcome to Cafe Chatbot API"
    }
