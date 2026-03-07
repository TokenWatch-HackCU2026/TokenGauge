import os
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    pwd_context,
    verify_password,
)
from database import get_db
from models import User
from schemas import LoginRequest, RefreshRequest, RegisterRequest, UserOut

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


def _issue_tokens(user: User) -> tuple[str, str]:
    access = create_access_token(user.id, user.org_id, user.email)
    refresh = create_refresh_token(user.id)
    user.refresh_token_hash = pwd_context.hash(refresh)
    return access, refresh


@router.post("/register", status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
    )
    db.add(user)
    db.flush()
    access, refresh = _issue_tokens(user)
    db.commit()
    db.refresh(user)
    return {"access_token": access, "refresh_token": refresh, "user": UserOut.model_validate(user)}


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    access, refresh = _issue_tokens(user)
    db.commit()
    return {"access_token": access, "refresh_token": refresh, "expires_in": 900}


@router.post("/refresh")
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_refresh_token(body.refresh_token)
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or not user.refresh_token_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    if not pwd_context.verify(body.refresh_token, user.refresh_token_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    access = create_access_token(user.id, user.org_id, user.email)
    return {"access_token": access, "expires_in": 900}


@router.post("/logout", status_code=204)
def logout(body: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_refresh_token(body.refresh_token)
        user = db.query(User).filter(User.id == int(payload["sub"])).first()
        if user:
            user.refresh_token_hash = None
            db.commit()
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
async def google_callback(code: str, db: Session = Depends(get_db)):
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

    user = db.query(User).filter(User.google_id == info["id"]).first()
    if not user:
        # Check if the email already exists — link the accounts
        user = db.query(User).filter(User.email == info["email"]).first()
        if user:
            user.google_id = info["id"]
            user.google_access_token = token_data.get("access_token")
            user.google_refresh_token = token_data.get("refresh_token")
        else:
            user = User(
                email=info["email"],
                full_name=info.get("name"),
                avatar_url=info.get("picture"),
                google_id=info["id"],
                google_access_token=token_data.get("access_token"),
                google_refresh_token=token_data.get("refresh_token"),
            )
            db.add(user)
            db.flush()

    access, refresh = _issue_tokens(user)
    db.commit()
    db.refresh(user)
    return {"access_token": access, "refresh_token": refresh, "user": UserOut.model_validate(user)}
