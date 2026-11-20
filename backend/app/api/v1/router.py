#APIRouter lets us organize endpoints into separate files and register them with the main application. 
from fastapi import APIRouter


health_router = APIRouter( prefix="/health", tags=["Health"] )
session_router = APIRouter( prefix="/sessions", tags=["Sessions"] )