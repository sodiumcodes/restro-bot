#APIRouter lets us organize endpoints into separate files and register them with the main application. 
from fastapi import APIRouter

common = "/api/v1"
health_router = APIRouter( prefix=f"{common}/health", tags=["Health"] )
session_router = APIRouter( prefix=f"{common}/sessions", tags=["Sessions"] )
chat_router = APIRouter( prefix=f"{common}/chat", tags=["Chat"] )
cart_router = APIRouter( prefix=f"{common}/cart", tags=["Cart"] )
order_router = APIRouter( prefix=f"{common}/orders", tags=["Orders"] )