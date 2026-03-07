import uuid
from datetime import datetime, timezone
from typing import List

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from auth import get_current_user
from kms import decrypt_key, encrypt_key
from models import ApiKey, KeyAuditLog

router = APIRouter(prefix="/keys", tags=["keys"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class KeyCreate(BaseModel):
    provider: str
    api_key: str
    label: str = ""


class KeyOut(BaseModel):
    id: str
    provider: str
    label: str
    key_hint: str
    created_at: datetime


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/", response_model=KeyOut, status_code=201)
async def add_key(body: KeyCreate, current_user: dict = Depends(get_current_user)):
    if not body.api_key or len(body.api_key) < 4:
        raise HTTPException(status_code=400, detail="api_key must be at least 4 characters")
    if not body.provider:
        raise HTTPException(status_code=400, detail="provider is required")

    uid = PydanticObjectId(current_user["user_id"])
    encrypted_blob, key_hint = encrypt_key(body.api_key)

    doc = ApiKey(
        user_id=uid,
        provider=body.provider.lower(),
        label=body.label or body.provider,
        encrypted_blob=encrypted_blob,
        key_hint=key_hint,
    )
    await doc.insert()
    return _to_out(doc)


@router.get("/", response_model=List[KeyOut])
async def list_keys(current_user: dict = Depends(get_current_user)):
    uid = PydanticObjectId(current_user["user_id"])
    docs = await ApiKey.find(ApiKey.user_id == uid).sort(-ApiKey.created_at).to_list()
    return [_to_out(d) for d in docs]


@router.delete("/{key_id}", status_code=204)
async def delete_key(key_id: str, current_user: dict = Depends(get_current_user)):
    doc = await ApiKey.get(key_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Key not found")
    if str(doc.user_id) != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your key")
    await doc.delete()


# ── Internal: decrypt for proxy use (audit-logged) ───────────────────────────

async def get_decrypted_key(user_id: str, provider: str, request_id: str | None = None) -> str:
    """
    Decrypt a user's key for a given provider. Writes an audit log entry.
    Call only from within the proxy layer — never expose the return value in a response.
    """
    uid = PydanticObjectId(user_id)
    doc = await ApiKey.find_one(ApiKey.user_id == uid, ApiKey.provider == provider)
    if not doc:
        raise HTTPException(status_code=404, detail=f"No {provider} key registered")

    raw_key = decrypt_key(doc.encrypted_blob)

    await KeyAuditLog(
        user_id=uid,
        key_id=doc.id,
        request_id=request_id or str(uuid.uuid4()),
        action="decrypt",
    ).insert()

    return raw_key


# ── Helper ────────────────────────────────────────────────────────────────────

def _to_out(doc: ApiKey) -> KeyOut:
    return KeyOut(
        id=str(doc.id),
        provider=doc.provider,
        label=doc.label,
        key_hint=doc.key_hint,
        created_at=doc.created_at,
    )
