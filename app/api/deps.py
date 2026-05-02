import uuid
from dataclasses import dataclass

from fastapi import HTTPException, Request


@dataclass
class CurrentUser:
    user_id: uuid.UUID
    role: str


def get_current_user(request: Request) -> CurrentUser:
    user_id = getattr(request.state, "user_id", None)
    role = getattr(request.state, "role", "")

    if not user_id:
        raise HTTPException(status_code=401, detail="No autenticado")

    try:
        uid = uuid.UUID(user_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=401, detail="Token inválido")

    return CurrentUser(user_id=uid, role=role)
