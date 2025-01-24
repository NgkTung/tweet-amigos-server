from pydantic import BaseModel
from uuid import UUID

class Role(BaseModel):
    id: UUID
    name: str