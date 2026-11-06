"""Portal do fornecedor — rotas INTERNAS (com login): criar, listar e revogar convites, ver os envios (F7).

O token aparece UMA vez, na resposta da criação; depois disso só existe o hash dele no banco.
"""
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import UsuarioAtual, analista, revisor
from app.api.portal_publico import documentos_do_convite, hash_token, situacao, vereditos
from app.config import settings
from app.db import get_db
from app.models import ConviteFornecedor, Documento, Lote
from app.pipeline import veredito_portal as vp
from app.tipos import nome_tipo

router = APIRouter(prefix="/portal/convites", tags=["portal do fornecedor (interno)"])


class ConviteIn(BaseModel):
    fornecedor_nome: str = Field(..., min_length=2, max_length=200, examples=["Construtora Exemplo LTDA"])
    contato_email: str | None = Field(None, max_length=200)
    exigidos: list[str] = Field(..., min_length=1, examples=[["CND_FEDERAL", "CRF_FGTS", "CNDT", "CONTRATO"]])
    expira_dias: int | None = Field(None, ge=1, le=365)
    usos_max: int = Field(20, ge=1, le=500)


def _resumo(lista: list[dict]) -> dict:
    return {"aprovados": sum(1 for s in lista if s["situacao"] == "aprovado"),
            "pendentes": sum(1 for s in lista if s["situacao"] in ("em_analise", "reprovado")),
            "faltando": sum(1 for s in lista if s["situacao"] == "nao_enviado")}


def _out(db: Session, c: ConviteFornecedor) -> dict:
    return {"id": c.id, "fornecedor_nome": c.fornecedor_nome, "contato_email": c.contato_email,
            "exigidos": c.exigidos, "expira_em": c.expira_em, "usos": c.usos, "usos_max": c.usos_max,
            "ativo": c.ativo, "criado_por": c.criado_por, "criado_em": c.criado_em,
            "situacao_resumo": _resumo(situacao(db, c))}


@router.post("", status_code=201)
def criar_convite(body: ConviteIn, db: Session = Depends(get_db), u: UsuarioAtual = Depends(revisor)):
    """Cria o link privado. A resposta traz o token UMA única vez — guarde/envie o link agora."""
    invalidos = [e for e in body.exigidos if not vp.exigido_valido(e)]
    if invalidos:
        raise HTTPException(422, f"Tipos exigidos inexistentes: {', '.join(invalidos)} (veja GET /tipos)")
    token = secrets.token_urlsafe(32)
    expira = datetime.now(timezone.utc) + timedelta(days=body.expira_dias or settings.PORTAL_VALIDADE_DIAS)
    c = ConviteFornecedor(token_hash=hash_token(token), fornecedor_nome=body.fornecedor_nome.strip(),
                          contato_email=body.contato_email, exigidos=list(dict.fromkeys(body.exigidos)),
                          expira_em=expira, usos_max=body.usos_max, usos=0, ativo=True, criado_por=u.login)
    db.add(c)
    db.commit()
    return {"id": c.id, "token": token, "url": f"{settings.PORTAL_URL_BASE.rstrip('/')}/portal/{token}",
            "expira_em": c.expira_em}


@router.get("")
def listar_convites(db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    return [_out(db, c) for c in db.scalars(select(ConviteFornecedor).order_by(ConviteFornecedor.id.desc()))]


def _obter(db: Session, convite_id: int) -> ConviteFornecedor:
    c = db.get(ConviteFornecedor, convite_id)
    if not c:
        raise HTTPException(404, "Convite não encontrado")
    return c


@router.post("/{convite_id}/revogar")
def revogar(convite_id: int, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(revisor)):
    c = _obter(db, convite_id)
    c.ativo = False
    db.commit()
    return _out(db, c)


@router.get("/{convite_id}/envios")
def envios(convite_id: int, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    """Visão INTERNA: lotes do convite com status e o veredito que o fornecedor vê em cada documento."""
    c = _obter(db, convite_id)
    lotes = list(db.scalars(select(Lote).where(Lote.convite_id == c.id).order_by(Lote.criado_em.desc())))
    docs = documentos_do_convite(db, c)
    vs = vereditos(db, docs)
    por_lote: dict[str, list[Documento]] = {}
    for d in docs:
        por_lote.setdefault(d.lote_id, []).append(d)
    return [{"lote_id": lt.id, "nome": lt.nome, "status": lt.status, "criado_em": lt.criado_em,
             "documentos": [{"id": d.id, "ordem": d.ordem, "tipo": d.tipo, "tipo_nome": nome_tipo(d.tipo),
                             "status_revisao": d.status_revisao, "risco": d.risco} | vs[d.id]
                            for d in sorted(por_lote.get(lt.id, []), key=lambda x: x.ordem)]}
            for lt in lotes]
