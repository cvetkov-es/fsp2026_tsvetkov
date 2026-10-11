from app.common.security import hash_password, hash_token, new_token, verify_password


def test_password_roundtrip_argon2id():
    h = hash_password("пароль-🔐-очень-длинный" * 10)
    assert h.startswith("$argon2id$")
    assert verify_password(h, "пароль-🔐-очень-длинный" * 10)
    assert not verify_password(h, "wrong")


def test_verify_password_tolerates_garbage_hash():
    assert verify_password("not-a-hash", "x") is False


def test_tokens_random_and_hash_deterministic():
    a, b = new_token(), new_token()
    assert a != b and len(a) >= 40
    assert hash_token(a) == hash_token(a) and hash_token(a) != a and len(hash_token(a)) == 64
