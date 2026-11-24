from uuid import UUID
from typing import Literal
from pydantic import BaseModel

class SessionCreateResponse(BaseModel):
    session_id: UUID


class SessionStatusResponse(BaseModel):
    session_id: UUID
    status: Literal["active", "closed"]
