import pytest
import os
from cryptography.fernet import Fernet
from src.security.encryption import EncryptionEngine

def test_encryption_roundtrip():
    # Setup test key dynamically to avoid GitGuardian alerts
    os.environ["OMNIKERNAL_SECRET_KEY"] = Fernet.generate_key().decode()
    
    plaintext = "test-api-key-12345!@#"
    ciphertext = EncryptionEngine.encrypt(plaintext)
    
    # Must actually encrypt
    assert ciphertext != plaintext
    assert isinstance(ciphertext, str)
    
    # Must decrypt perfectly
    decrypted = EncryptionEngine.decrypt(ciphertext)
    assert decrypted == plaintext

def test_empty_string_encryption():
    assert EncryptionEngine.encrypt("") == ""
    assert EncryptionEngine.decrypt("") == ""

def test_encryption_generates_temp_key_if_missing(monkeypatch):
    monkeypatch.delenv("OMNIKERNAL_SECRET_KEY", raising=False)
    # Reset singleton for test
    EncryptionEngine._fernet = None
    
    plaintext = "super_secret"
    ciphertext = EncryptionEngine.encrypt(plaintext)
    
    assert ciphertext != plaintext
    
    # Temp key should have been created in env
    assert "OMNIKERNAL_SECRET_KEY" in os.environ
    
    decrypted = EncryptionEngine.decrypt(ciphertext)
    assert decrypted == plaintext
