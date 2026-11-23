"""
Main application entry point for Cafe Chatbot.

Responsibilities:
- Initialize the FastAPI application.
- Configure CORS.
- Initialize LLM and menu retrieval services.
- Build and compile the LangGraph workflow.
- Manage application startup and shutdown.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.llm.llm_router import get_llm
from app.llm.graph import build_graph
from app.llm.retrieval import MenuRetriever

# --------------------------------------------------
# Application lifespan
# --------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialize application resources during startup and release them during shutdown.
    """

    print("\nStarting Cafe Chatbot...")

    # Step 1: Initialize LLM router.
    llm = get_llm(temperature=0.0)

    # Step 2: Initialize menu retriever.
    menu_retriever = MenuRetriever()

    # Step 3: Build and compile LangGraph workflow.
    graph = build_graph(
        llm=llm,
        retrieval_fn=menu_retriever.retrieve,
    )

    # Step 4: Store resources in application state.
    app.state.llm = llm
    app.state.menu_retriever = menu_retriever
    app.state.graph = graph

    print("LLM router initialized.")
    print("Menu retriever initialized.")
    print("LangGraph workflow compiled.")
    print("Cafe Chatbot is ready!\n")

    yield

    # Shutdown: release resources.
    menu_retriever.close()

    print("\nCafe Chatbot shut down.")


# --------------------------------------------------
# FastAPI application
# --------------------------------------------------

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    version="1.0.0",
    lifespan=lifespan,
)


# --------------------------------------------------
# CORS configuration
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------
# API router registration
# --------------------------------------------------
from app.api.v1 import router
from app.api.v1.endpoints import health_endpoint, sessions_endpoint, chat_endpoint, cart_endpoint, orders_endpoint, staff
app.include_router(router.health_router)
app.include_router(router.session_router)
app.include_router(router.chat_router)
app.include_router(router.cart_router)
app.include_router(router.order_router)
app.include_router(router.staff_router)

# --------------------------------------------------
# Root endpoint
# --------------------------------------------------
@app.get("/")
async def root():
    return {
        "message": "Welcome to Cafe Chatbot API"
    }
