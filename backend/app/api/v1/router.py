#APIRouter lets us organize endpoints into separate files and register them with the main application. 
from fastapi import APIRouter

health_router = APIRouter(tags=["Health"])