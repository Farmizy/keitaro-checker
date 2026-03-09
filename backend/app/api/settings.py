from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.services.panel_client import PanelClient

router = APIRouter()


class UpdateJwtRequest(BaseModel):
    token: str


def _get_panel(request: Request) -> PanelClient:
    panel = getattr(request.app.state, "panel", None)
    if not panel:
        raise RuntimeError("PanelClient not initialized")
    return panel


@router.post("/panel-jwt")
async def update_panel_jwt(
    body: UpdateJwtRequest,
    request: Request,
):
    """Update Panel API JWT token at runtime without restart."""
    panel = _get_panel(request)
    panel.update_jwt(body.token)
    return {"status": "ok", "message": "Panel JWT token updated"}
