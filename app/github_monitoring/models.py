import base64
import hashlib
from cryptography.fernet import Fernet
from django.conf import settings
from django.db import models


def get_cipher():
    key = getattr(settings, 'ENCRYPTION_KEY', None)
    if not key:
        derived = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        key = base64.urlsafe_b64encode(derived)
    elif isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def encrypt_token(plain_text: str) -> str:
    if not plain_text:
        return ''
    # Avoid double encryption if already looks encrypted
    cipher = get_cipher()
    return cipher.encrypt(plain_text.encode()).decode()


def decrypt_token(cipher_text: str) -> str:
    if not cipher_text:
        return ''
    try:
        cipher = get_cipher()
        return cipher.decrypt(cipher_text.encode()).decode()
    except Exception:
        # If decryption fails (e.g. unencrypted string), return as is
        return cipher_text


class Project(models.Model):
    name = models.CharField(max_length=255, help_text="Project Display Name")
    github_owner = models.CharField(max_length=255, help_text="GitHub Account or Organization Name (e.g. Shailesh-2128)")
    github_repo = models.CharField(max_length=255, help_text="Repository Name (e.g. king_wins_backend)")
    github_token = models.TextField(blank=True, default="", help_text="Encrypted GitHub Personal Access Token")
    default_branch = models.CharField(max_length=100, default="main", help_text="Default Branch (e.g. main, master)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['github_owner', 'github_repo']

    def __str__(self):
        return f"{self.name} ({self.github_owner}/{self.github_repo})"

    def set_token(self, raw_token: str):
        if raw_token:
            self.github_token = encrypt_token(raw_token)
        else:
            self.github_token = ""

    def get_decrypted_token(self) -> str:
        return decrypt_token(self.github_token)

    @property
    def has_token(self) -> bool:
        return bool(self.github_token)

    @property
    def masked_token(self) -> str:
        dec = self.get_decrypted_token()
        if not dec:
            return ""
        if len(dec) <= 8:
            return "****"
        return f"{dec[:4]}...{dec[-4:]}"
