import asyncio
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ..config import get_settings
from ..schemas import LoginIn
from ..security import (
    COOKIE_NAME,
    check_origin,
    read_session,
    require_admin,
    serializer,
    throttle_login,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/login")
async def login(body: LoginIn, request: Request, response: Response):
    check_origin(request)
    throttle_login(request)
    settings = get_settings()
    valid = await asyncio.to_thread(verify_password, body.password, settings.admin_password_hash)
    if not valid or body.username != settings.admin_username:
        raise HTTPException(401, "Invalid username or password")
    session = {"username": settings.admin_username, "csrf": secrets.token_urlsafe(32)}
    response.set_cookie(
        COOKIE_NAME,
        serializer().dumps(session),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=settings.session_seconds,
        path="/",
    )
    return {"authenticated": True, **session}


@router.get("/me")
async def me(request: Request):
    session = read_session(request)
    return {"authenticated": bool(session), **(session or {})}


@router.post("/logout", dependencies=[Depends(require_admin)])
async def logout(response: Response):
    response.delete_cookie(
        COOKIE_NAME, path="/", secure=get_settings().cookie_secure, httponly=True, samesite="strict"
    )
    return {"authenticated": False}
