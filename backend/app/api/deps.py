from fastapi import Header, HTTPException

from app.config import settings


def exigir_api_key(x_api_key: str | None = Header(default=None)):
    """Autenticação simples por chave. Em produção: OAuth2/JWT com perfis (analista, revisor, admin)."""
    if settings.API_KEY and x_api_key != settings.API_KEY:
        raise HTTPException(401, "X-API-Key inválida ou ausente")
