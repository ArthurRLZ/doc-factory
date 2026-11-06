import hmac
from dataclasses import dataclass

import jwt
from fastapi import Depends, Header, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Usuario
from app.security import ler_token, perfil_atende

oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def exigir_api_key(x_api_key: str | None = Header(default=None)):
    """Chave única opcional (integrações máquina-a-máquina). Login com perfis: AUTH_ATIVO=true."""
    # comparação em tempo constante: não deixa medir pelo tempo de resposta quantos caracteres acertou
    if settings.API_KEY and not hmac.compare_digest((x_api_key or "").encode(), settings.API_KEY.encode()):
        raise HTTPException(401, "X-API-Key inválida ou ausente")


@dataclass
class UsuarioAtual:
    login: str
    perfil: str
    autenticado: bool


def usuario_atual(token: str | None = Depends(oauth2)) -> UsuarioAtual:
    """Com AUTH_ATIVO=false a API fica aberta (modo demo) e todo mundo é 'admin' anônimo."""
    if not settings.AUTH_ATIVO:
        return UsuarioAtual(login="anonimo", perfil="admin", autenticado=False)
    if not token:
        raise HTTPException(401, "Faça login em /auth/login", headers={"WWW-Authenticate": "Bearer"})
    try:
        dados = ler_token(token)
    except jwt.PyJWTError as e:
        raise HTTPException(401, "Token inválido ou expirado", headers={"WWW-Authenticate": "Bearer"}) from e
    with SessionLocal() as db:
        u = db.scalar(select(Usuario).where(Usuario.login == dados.get("sub")))
        if not u or not u.ativo:
            raise HTTPException(401, "Usuário inativo ou removido")
        return UsuarioAtual(login=u.login, perfil=u.perfil, autenticado=True)


def exigir_perfil(minimo: str):
    def _dep(u: UsuarioAtual = Depends(usuario_atual)) -> UsuarioAtual:
        if not perfil_atende(u.perfil, minimo):
            raise HTTPException(403, f"Requer perfil {minimo} ou superior")
        return u
    return _dep


analista = exigir_perfil("analista")
revisor = exigir_perfil("revisor")
admin = exigir_perfil("admin")
