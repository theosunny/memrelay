"""Symmetric encryption for sync blobs. Only devices hold the vault key."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


def generate_vault_key() -> bytes:
    return Fernet.generate_key()


def encrypt_blob(key: bytes, plaintext: bytes) -> bytes:
    return Fernet(key).encrypt(plaintext)


def decrypt_blob(key: bytes, blob: bytes) -> bytes:
    try:
        return Fernet(key).decrypt(blob)
    except (InvalidToken, ValueError, TypeError) as ex:
        raise ValueError("bad blob") from ex
