"""
Secure Key Storage for APIBouncer

Stores API keys in an encrypted local file instead of system keyring.
This prevents AI agents from accessing keys via keyring.get_password().

The encryption key is derived from machine-specific data, making it
harder to decrypt even if the encrypted file is found.
"""

import os
import json
import base64
import hashlib
from pathlib import Path
from typing import Optional, Dict

# Use cryptography library for Fernet encryption
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


def _get_machine_id() -> str:
    """Get a machine-specific identifier for key derivation."""
    # Combine multiple sources for uniqueness
    parts = []

    # Windows machine GUID
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography"
        )
        machine_guid, _ = winreg.QueryValueEx(key, "MachineGuid")
        parts.append(machine_guid)
        winreg.CloseKey(key)
    except Exception:
        pass

    # Username + computer name as fallback
    parts.append(os.environ.get("USERNAME", "user"))
    parts.append(os.environ.get("COMPUTERNAME", "computer"))

    # Combine and hash
    combined = "|".join(parts)
    return hashlib.sha256(combined.encode()).hexdigest()


def _get_data_dir() -> Path:
    """Get the data directory for storing keys."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

    data_dir = base / "APIBouncer"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def _derive_key(salt: bytes) -> bytes:
    """Derive encryption key from machine ID."""
    machine_id = _get_machine_id().encode()

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )

    key = base64.urlsafe_b64encode(kdf.derive(machine_id))
    return key


class SecureKeyStore:
    """Encrypted storage for API keys."""

    def __init__(self):
        if not HAS_CRYPTO:
            raise RuntimeError("cryptography library required: pip install cryptography")

        self.data_dir = _get_data_dir()
        self.keys_file = self.data_dir / ".keys.enc"
        self.salt_file = self.data_dir / ".salt"

        self._salt = self._get_or_create_salt()
        self._fernet = Fernet(_derive_key(self._salt))
        self._keys: Dict[str, str] = {}

        self._load()

    def _get_or_create_salt(self) -> bytes:
        """Get existing salt or create new one."""
        if self.salt_file.exists():
            return self.salt_file.read_bytes()
        else:
            salt = os.urandom(16)
            self.salt_file.write_bytes(salt)
            # Hide the file on Windows
            try:
                import ctypes
                ctypes.windll.kernel32.SetFileAttributesW(str(self.salt_file), 0x02)  # HIDDEN
            except Exception:
                pass
            return salt

    def _load(self):
        """Load and decrypt keys from file."""
        if self.keys_file.exists():
            try:
                encrypted = self.keys_file.read_bytes()
                decrypted = self._fernet.decrypt(encrypted)
                self._keys = json.loads(decrypted.decode())
            except Exception:
                # File corrupted or key changed - start fresh
                self._keys = {}

    def _save(self):
        """Encrypt and save keys to file."""
        data = json.dumps(self._keys).encode()
        encrypted = self._fernet.encrypt(data)

        # Remove hidden attribute before writing (Windows)
        try:
            import ctypes
            # Remove HIDDEN attribute (set to NORMAL)
            ctypes.windll.kernel32.SetFileAttributesW(str(self.keys_file), 0x80)  # NORMAL
        except Exception:
            pass

        self.keys_file.write_bytes(encrypted)

        # Re-hide the file on Windows
        try:
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(str(self.keys_file), 0x02)  # HIDDEN
        except Exception:
            pass

    def set_key(self, provider: str, api_key: str):
        """Store an API key."""
        self._keys[provider] = api_key
        self._save()

    def get_key(self, provider: str) -> Optional[str]:
        """Retrieve an API key."""
        return self._keys.get(provider)

    def delete_key(self, provider: str):
        """Remove an API key."""
        if provider in self._keys:
            del self._keys[provider]
            self._save()

    def list_providers(self) -> list:
        """List all stored providers."""
        return list(self._keys.keys())

    def has_key(self, provider: str) -> bool:
        """Check if a key exists for a provider."""
        return provider in self._keys


# Singleton instance
_store: Optional[SecureKeyStore] = None


def get_keystore() -> SecureKeyStore:
    """Get the global keystore instance."""
    global _store
    if _store is None:
        _store = SecureKeyStore()
    return _store


# Convenience functions matching keyring API
def get_password(service: str, provider: str) -> Optional[str]:
    """Get a key (keyring-compatible API)."""
    return get_keystore().get_key(provider)


def set_password(service: str, provider: str, api_key: str):
    """Set a key (keyring-compatible API)."""
    get_keystore().set_key(provider, api_key)


def delete_password(service: str, provider: str):
    """Delete a key (keyring-compatible API)."""
    get_keystore().delete_key(provider)
