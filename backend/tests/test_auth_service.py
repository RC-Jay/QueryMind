import pytest
from services.auth_service import (
    hash_password, verify_password, create_access_token, create_refresh_token, decode_token,
)
from exceptions import InvalidTokenError


def test_password_hash_roundtrip():
    h = hash_password("Secret@123")
    assert h != "Secret@123"
    assert verify_password("Secret@123", h)
    assert not verify_password("wrong", h)


def test_access_token_roundtrip():
    tok = create_access_token(user_id=7, is_superuser=True)
    payload = decode_token(tok, expected_type="access")
    assert payload["sub"] == "7"
    assert payload["su"] is True


def test_refresh_token_roundtrip():
    tok = create_refresh_token(user_id=3)
    payload = decode_token(tok, expected_type="refresh")
    assert payload["sub"] == "3"


def test_wrong_token_type_raises():
    access = create_access_token(user_id=1, is_superuser=False)
    with pytest.raises(InvalidTokenError):
        decode_token(access, expected_type="refresh")


def test_garbage_token_raises():
    with pytest.raises(InvalidTokenError):
        decode_token("not.a.jwt", expected_type="access")
