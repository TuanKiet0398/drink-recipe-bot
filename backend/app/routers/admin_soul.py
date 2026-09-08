from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agent.nodes import SOUL_PATH
from app.auth import log_admin_action, require_admin
from app.db.base import get_db

router = APIRouter(prefix="/admin/soul")


class SoulPayload(BaseModel):
    content: str


@router.get("")
def read_soul(admin_user: str = Depends(require_admin)):
    try:
        content = SOUL_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        content = ""
    return {"content": content}


@router.put("")
def update_soul(
    payload: SoulPayload,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    SOUL_PATH.write_text(payload.content, encoding="utf-8")
    log_admin_action(
        db,
        action="soul.update",
        target="SOUL.md",
        ip=request.client.host if request.client else "",
    )
    return {"content": payload.content}
