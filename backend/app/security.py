"""Senhas (PBKDF2, só biblioteca padrão) e tokens JWT."""
import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings

PERFIS = ("analista", "revisor", "admin")          # cada perfil inclui os anteriores
_ITERACOES = 200_000
_SEGREDO = settings.JWT_SEGREDO or secrets.token_urlsafe(48)


def hash_senha(senha: str) -> str:
    sal = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", senha.encode(), sal, _ITERACOES)
    return f"pbkdf2_sha256${_ITERACOES}${base64.b64encode(sal).decode()}${base64.b64encode(dk).decode()}"


def verificar_senha(senha: str, guardado: str) -> bool:
    try:
        _alg, it, sal, dk = guardado.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", senha.encode(), base64.b64decode(sal), int(it))
        return hmac.compare_digest(calc, base64.b64decode(dk))
    except Exception:
        return False


def criar_token(login: str, perfil: str) -> str:
    agora = datetime.now(timezone.utc)
    return jwt.encode({"sub": login, "perfil": perfil, "iat": agora,
                       "exp": agora + timedelta(minutes=settings.JWT_EXPIRA_MIN)}, _SEGREDO, algorithm="HS256")


def ler_token(token: str) -> dict:
    return jwt.decode(token, _SEGREDO, algorithms=["HS256"])


def perfil_atende(perfil: str, minimo: str) -> bool:
    return perfil in PERFIS and PERFIS.index(perfil) >= PERFIS.index(minimo)
