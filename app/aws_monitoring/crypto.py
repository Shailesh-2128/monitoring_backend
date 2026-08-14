import base64
import hashlib
from django.conf import settings
from cryptography.fernet import Fernet


def _get_fernet():
    key = getattr(settings, 'FERNET_SECRET_KEY', None)
    if not key:
        raw_key = settings.SECRET_KEY.encode('utf-8')
        key = base64.urlsafe_b64encode(hashlib.sha256(raw_key).digest())
    else:
        if isinstance(key, str):
            key = key.encode('utf-8')
    return Fernet(key)


def encrypt_credential(raw_text: str) -> str:
    if not raw_text:
        return ""
    fernet = _get_fernet()
    encrypted_bytes = fernet.encrypt(raw_text.strip().encode('utf-8'))
    return encrypted_bytes.decode('utf-8')


def decrypt_credential(encrypted_text: str) -> str:
    if not encrypted_text:
        return ""
    # If unencrypted text passed by legacy or plain string
    if not (encrypted_text.startswith('gAAAAA') or len(encrypted_text) > 40):
        return encrypted_text
    try:
        fernet = _get_fernet()
        decrypted_bytes = fernet.decrypt(encrypted_text.encode('utf-8'))
        return decrypted_bytes.decode('utf-8')
    except Exception:
        # Fallback return original string if decryption fails
        return encrypted_text
