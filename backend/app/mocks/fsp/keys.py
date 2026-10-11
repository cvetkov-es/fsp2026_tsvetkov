"""Ключ RS256 мока, JWKS и проверка access token API достижений."""
import json

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from jwt.algorithms import RSAAlgorithm
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.common.clock import now
from app.config.settings import get_settings
from app.mocks.fsp.models import MockFspKey

KID = "fsp-mock-1"
API_AUDIENCE = "fsp-achievements-api"


def private_key(db: Session) -> rsa.RSAPrivateKey:
    row = db.get(MockFspKey, KID)
    if row is None:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption()).decode()
        # Гонка двух воркеров: побеждает первая запись, второй читает её
        db.execute(insert(MockFspKey).values(kid=KID, private_pem=pem, created_at=now())
                   .on_conflict_do_nothing(index_elements=["kid"]))
        db.commit()
        row = db.get(MockFspKey, KID)
    return serialization.load_pem_private_key(row.private_pem.encode(), password=None)


def sign(db: Session, claims: dict) -> str:
    return jwt.encode(claims, private_key(db), algorithm="RS256", headers={"kid": KID})


def jwks(db: Session) -> dict:
    jwk = json.loads(RSAAlgorithm.to_jwk(private_key(db).public_key()))
    return {"keys": [{**jwk, "kid": KID, "alg": "RS256", "use": "sig"}]}


def bearer_claims(db: Session, authorization: str) -> dict:
    """Проверка access token: подпись мока, issuer и audience API достижений."""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Нужен Bearer-токен FSP ID")
    try:
        return jwt.decode(token, private_key(db).public_key(), algorithms=["RS256"], audience=API_AUDIENCE,
                          issuer=get_settings().fsp_issuer)
    except jwt.PyJWTError as e:
        raise HTTPException(401, "Токен FSP ID не прошёл проверку") from e
