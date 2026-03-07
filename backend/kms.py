"""
Key encryption module.

Uses GCP KMS when GCP_KMS_KEY_NAME is set in the environment.
Falls back to local AES-256 (Fernet) encryption for development.

GCP KMS key name format:
  projects/PROJECT/locations/LOCATION/keyRings/RING/cryptoKeys/KEY
"""
import base64
import hashlib
import os


def _fernet():
    from cryptography.fernet import Fernet

    # Prefer an explicit 32-byte base64 ENCRYPTION_KEY; otherwise derive from JWT_SECRET.
    raw = os.getenv("ENCRYPTION_KEY")
    if raw:
        key = raw.encode()
    else:
        secret = os.getenv("JWT_SECRET", "dev-secret")
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt_key(raw_key: str) -> tuple[str, str]:
    """
    Encrypt a raw API key.
    Returns (encrypted_blob, key_hint) where key_hint is the last-4 chars.
    """
    hint = f"...{raw_key[-4:]}" if len(raw_key) >= 4 else "****"

    kms_key_name = os.getenv("GCP_KMS_KEY_NAME")
    if kms_key_name:
        try:
            from google.cloud import kms  # type: ignore

            client = kms.KeyManagementServiceClient()
            response = client.encrypt(
                request={"name": kms_key_name, "plaintext": raw_key.encode()}
            )
            blob = "gcp:" + base64.b64encode(response.ciphertext).decode()
            return blob, hint
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "GCP KMS encrypt failed (%s), falling back to local encryption", exc
            )

    # Local Fernet fallback
    blob = "local:" + _fernet().encrypt(raw_key.encode()).decode()
    return blob, hint


def decrypt_key(encrypted_blob: str) -> str:
    """Decrypt an encrypted blob back to the raw API key (in-memory only)."""
    if encrypted_blob.startswith("gcp:"):
        kms_key_name = os.getenv("GCP_KMS_KEY_NAME")
        from google.cloud import kms  # type: ignore

        client = kms.KeyManagementServiceClient()
        ciphertext = base64.b64decode(encrypted_blob[4:])
        response = client.decrypt(
            request={"name": kms_key_name, "ciphertext": ciphertext}
        )
        return response.plaintext.decode()

    # local: prefix
    return _fernet().decrypt(encrypted_blob[6:].encode()).decode()
