"""Alertas de vencimento: contatos, prévia do que seria enviado, execução manual e histórico (F6).

No modo simulado (padrão) nada sai do sistema: a mensagem é só registrada e logada. Senhas e chaves dos canais
nunca aparecem nas respostas.
"""
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alertas import canais, servico
from app.api.deps import UsuarioAtual, admin, analista
from app.config import settings
from app.db import get_db
from app.models import AlertaEnviado, ContatoAlerta, Documento
from app.tipos import nome_tipo

router = APIRouter(prefix="/alertas", tags=["alertas de vencimento"])

_RX_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_RX_WHATSAPP = re.compile(r"^\d{10,15}$")


class ContatoIn(BaseModel):
    nome: str = Field(..., min_length=2, max_length=120)
    canal: Literal["email", "whatsapp"]
    destino: str = Field(..., max_length=200, description="e-mail, ou telefone só com dígitos (ex.: 5581999999999)")

    @model_validator(mode="after")
    def _destino_valido(self):
        self.destino = self.destino.strip()
        if self.canal == "email" and not _RX_EMAIL.match(self.destino):
            raise ValueError("e-mail inválido")
        if self.canal == "whatsapp" and not _RX_WHATSAPP.match(self.destino):
            raise ValueError("WhatsApp: use só dígitos, com DDI e DDD (10 a 15 dígitos), ex.: 5581999999999")
        return self


def _contato_out(c: ContatoAlerta) -> dict:
    return {"id": c.id, "nome": c.nome, "canal": c.canal, "destino": c.destino, "ativo": c.ativo,
            "criado_por": c.criado_por, "criado_em": c.criado_em}


@router.get("/config")
def configuracao(_u: UsuarioAtual = Depends(analista)):
    """Estado dos alertas (sem senhas nem chaves)."""
    return {"ativo": settings.ALERTAS_ATIVO, "modo": settings.ALERTAS_MODO, "faixas": settings.alertas_faixas,
            "hora_execucao": settings.ALERTAS_HORA_EXECUCAO,
            "canais_configurados": {"email": canais.email_configurado(), "whatsapp": canais.whatsapp_configurado()}}


@router.get("/contatos")
def listar_contatos(db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    return [_contato_out(c) for c in db.scalars(select(ContatoAlerta).order_by(ContatoAlerta.id))]


@router.post("/contatos", status_code=201)
def criar_contato(body: ContatoIn, db: Session = Depends(get_db), u: UsuarioAtual = Depends(admin)):
    c = ContatoAlerta(nome=body.nome.strip(), canal=body.canal, destino=body.destino, ativo=True, criado_por=u.login)
    db.add(c)
    db.commit()
    return _contato_out(c)


def _obter(db: Session, contato_id: int) -> ContatoAlerta:
    c = db.get(ContatoAlerta, contato_id)
    if not c:
        raise HTTPException(404, "Contato não encontrado")
    return c


@router.delete("/contatos/{contato_id}")
def remover_contato(contato_id: int, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(admin)):
    db.delete(_obter(db, contato_id))
    db.commit()
    return {"apagado": contato_id}


@router.post("/contatos/{contato_id}/testar")
def testar_contato(contato_id: int, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(admin)):
    """Mensagem de teste pelo canal do contato (respeita o modo simulado)."""
    c = _obter(db, contato_id)
    try:
        canais.obter_canal(c.canal).enviar(c.destino, "Document Factory: teste de alerta",
                                           "Teste de alerta do Document Factory. Se você recebeu, o canal está ok.")
    except canais.ErroEnvio as e:
        raise HTTPException(502, f"Falha ao enviar: {e}") from None
    return {"ok": True, "simulado": settings.ALERTAS_MODO != "real"}


@router.get("/pendentes")
def ver_pendentes(db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    """Prévia: o que seria enviado agora para cada contato. Não envia nem grava nada."""
    return servico.pendentes(db)


@router.post("/executar")
def executar_agora(simular: bool | None = None, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(admin)):
    """Roda o envio na hora. Sem `simular`, usa ALERTAS_MODO."""
    return servico.executar(db, simular=simular)


@router.get("/historico")
def historico(limit: int = 100, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    limit = max(1, min(limit, 500))
    linhas = db.execute(select(AlertaEnviado, Documento.tipo, ContatoAlerta.nome)
                        .join(Documento, Documento.id == AlertaEnviado.documento_id)
                        .join(ContatoAlerta, ContatoAlerta.id == AlertaEnviado.contato_id)
                        .order_by(AlertaEnviado.enviado_em.desc(), AlertaEnviado.id.desc()).limit(limit))
    return [{"id": a.id, "documento_id": a.documento_id, "tipo": tipo, "tipo_nome": nome_tipo(tipo), "faixa": a.faixa,
             "canal": a.canal, "contato": nome, "status": a.status, "erro": a.erro, "enviado_em": a.enviado_em}
            for a, tipo, nome in linhas]
