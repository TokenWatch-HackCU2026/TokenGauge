import os
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from auth import (
    create_access_token,
    create_sdk_token,
    get_current_user,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    hash_token,
    verify_password,
    verify_token,
)
from models import User
from schemas import LoginRequest, RefreshRequest, RegisterRequest, UserOut

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        phone=user.phone,
        created_at=user.created_at,
    )


async def _issue_tokens(user: User) -> tuple[str, str]:
    access = create_access_token(str(user.id), user.email)
    refresh = create_refresh_token(str(user.id))
    user.refresh_token_hash = hash_token(refresh)
    await user.save()
    return access, refresh


@router.post("/register", status_code=201)
async def register(body: RegisterRequest):
    if await User.find_one(User.email == body.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
    )
    await user.insert()
    access, refresh = await _issue_tokens(user)
    return {"access_token": access, "refresh_token": refresh, "user": _user_out(user)}


@router.post("/login")
async def login(body: LoginRequest):
    user = await User.find_one(User.email == body.email)
    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    access, refresh = await _issue_tokens(user)
    return {"access_token": access, "refresh_token": refresh, "expires_in": 900, "user": _user_out(user)}


@router.post("/refresh")
async def refresh(body: RefreshRequest):
    payload = decode_refresh_token(body.refresh_token)
    user = await User.get(payload["sub"])
    if not user or not user.refresh_token_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    if not verify_token(body.refresh_token, user.refresh_token_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    access = create_access_token(str(user.id), user.email)
    return {"access_token": access, "expires_in": 900}


@router.post("/logout", status_code=204)
async def logout(body: RefreshRequest):
    try:
        payload = decode_refresh_token(body.refresh_token)
        user = await User.get(payload["sub"])
        if user:
            user.refresh_token_hash = None
            await user.save()
    except HTTPException:
        pass  # Already invalid — treat as success


@router.get("/google")
def google_login():
    params = {
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "redirect_uri": os.environ["GOOGLE_REDIRECT_URI"],
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    return {"url": f"{GOOGLE_AUTH_URL}?{urlencode(params)}"}


@router.get("/google/callback")
async def google_callback(code: str):
    async with httpx.AsyncClient() as client:
        token_res = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "redirect_uri": os.environ["GOOGLE_REDIRECT_URI"],
            "grant_type": "authorization_code",
        })
        if token_res.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google token exchange failed")
        token_data = token_res.json()

        userinfo_res = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
        if userinfo_res.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to fetch Google user info")
        info = userinfo_res.json()

    user = await User.find_one(User.google_id == info["id"])
    if not user:
        # Check if email exists — link accounts
        user = await User.find_one(User.email == info["email"])
        if user:
            user.google_id = info["id"]
            user.google_access_token = token_data.get("access_token")
            user.google_refresh_token = token_data.get("refresh_token")
            await user.save()
        else:
            user = User(
                email=info["email"],
                full_name=info.get("name"),
                avatar_url=info.get("picture"),
                google_id=info["id"],
                google_access_token=token_data.get("access_token"),
                google_refresh_token=token_data.get("refresh_token"),
            )
            await user.insert()

    access, refresh = await _issue_tokens(user)
    return {"access_token": access, "refresh_token": refresh, "user": _user_out(user)}


@router.get("/sdk-token")
async def get_sdk_token(
    regenerate: bool = False,
    current_user: dict = Depends(get_current_user),
):
    """
    Return the user's persistent SDK token (valid 1 year).
    Pass ?regenerate=true to rotate it and invalidate the old one.
    """
    from beanie import PydanticObjectId
    user = await User.get(PydanticObjectId(current_user["user_id"]))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.sdk_token or regenerate:
        user.sdk_token = create_sdk_token(current_user["user_id"], current_user["email"])
        await user.save()

    return {"sdk_token": user.sdk_token}
