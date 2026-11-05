"""Login (JWT) e gestão de usuários com perfis: analista < revisor < admin.

Com AUTH_ATIVO=false a API fica aberta (modo demo) e estas rotas continuam disponíveis
para preparar os usuários antes de ligar o login.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import UsuarioAtual, admin, usuario_atual
from app.config import settings
from app.db import get_db
from app.models import Usuario
from app.schemas import EuOut, TokenOut, UsuarioIn, UsuarioOut
from app.security import criar_token, hash_senha, verificar_senha

log = logging.getLogger(__name__)
router = APIRouter(tags=["login e usuários"])


@router.post("/auth/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Troca login + senha por um token. No Swagger: botão Authorize."""
    u = db.scalar(select(Usuario).where(Usuario.login == form.username))
    if not u or not u.ativo or not verificar_senha(form.password, u.senha_hash):
        raise HTTPException(401, "Login ou senha inválidos", headers={"WWW-Authenticate": "Bearer"})
    return TokenOut(access_token=criar_token(u.login, u.perfil), perfil=u.perfil)


@router.get("/auth/eu", response_model=EuOut)
def quem_sou_eu(u: UsuarioAtual = Depends(usuario_atual)):
    return EuOut(login=u.login, perfil=u.perfil, autenticado=u.autenticado)


@router.get("/usuarios", response_model=list[UsuarioOut])
def listar_usuarios(db: Session = Depends(get_db), _u: UsuarioAtual = Depends(admin)):
    return list(db.scalars(select(Usuario).order_by(Usuario.login)))


@router.post("/usuarios", response_model=UsuarioOut, status_code=201)
def criar_usuario(dados: UsuarioIn, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(admin)):
    if db.scalar(select(Usuario).where(Usuario.login == dados.login)):
        raise HTTPException(409, "Login já existe")
    u = Usuario(login=dados.login, nome=dados.nome, perfil=dados.perfil, senha_hash=hash_senha(dados.senha))
    db.add(u)
    db.commit()
    return u


@router.post("/usuarios/{usuario_id}/desativar", response_model=UsuarioOut)
def desativar_usuario(usuario_id: int, db: Session = Depends(get_db), atual: UsuarioAtual = Depends(admin)):
    u = db.get(Usuario, usuario_id)
    if not u:
        raise HTTPException(404, "Usuário não encontrado")
    if atual.autenticado and u.login == atual.login:
        raise HTTPException(422, "Você não pode desativar a si mesmo")
    u.ativo = False
    db.commit()
    return u


def criar_admin_inicial(db: Session) -> None:
    """Primeiro start: cria o admin a partir de ADMIN_USUARIO/ADMIN_SENHA se não houver usuários."""
    if db.scalar(select(func.count()).select_from(Usuario)):
        return
    if not settings.ADMIN_SENHA:
        if settings.AUTH_ATIVO:
            log.warning("AUTH_ATIVO=true mas nenhum usuário existe e ADMIN_SENHA não foi definida — ninguém consegue logar")
        return
    db.add(Usuario(login=settings.ADMIN_USUARIO, nome="Administrador", perfil="admin",
                   senha_hash=hash_senha(settings.ADMIN_SENHA)))
    db.commit()
    log.info("usuário admin '%s' criado", settings.ADMIN_USUARIO)
