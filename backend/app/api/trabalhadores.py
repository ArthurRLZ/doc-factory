"""Dossiê do trabalhador e checklist de documentos exigidos.

O trabalhador é identificado pela impressão digital do CPF — o CPF não é guardado.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import UsuarioAtual, analista, revisor
from app.api.documentos import doc_out
from app.db import get_db
from app.models import Documento, Trabalhador
from app.pipeline import checklist
from app.tipos import DOCUMENTOS_EXIGIDOS_TRABALHADOR, FUNCOES_NR

router = APIRouter(prefix="/trabalhadores", tags=["dossiê do trabalhador"])
router_funcoes = APIRouter(tags=["dossiê do trabalhador"])
_ORDEM = {"irregular": 0, "atencao": 1, "regular": 2}


def _resumo(t: Trabalhador, c: dict) -> dict:
    return {"id": t.id, "rotulo": f"Trabalhador {t.cpf_mascarado}", "cpf_mascarado": t.cpf_mascarado,
            "documentos": len(t.documentos), "situacao": c["situacao"], "pendencias": c["pendencias"],
            "faltando": c["faltando"], "vencidos": c["vencidos"], "vencendo": c["vencendo"],
            "funcao": FUNCOES_NR[t.funcao_chave]["nome"] if t.funcao_chave in FUNCOES_NR else t.funcao,
            "funcao_chave": t.funcao_chave, "funcao_texto": t.funcao, "funcao_origem": t.funcao_origem,
            "funcao_evidencia": t.funcao_evidencia, "exigidos": c["exigidos"]}


@router.get("")
def listar(lote_id: str | None = None, situacao: str | None = None,
           db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    """Trabalhadores com a situação do checklist (irregular primeiro). Filtros: lote_id, situacao."""
    q = select(Trabalhador)
    if lote_id:
        q = q.where(Trabalhador.id.in_(select(Documento.trabalhador_id).where(Documento.lote_id == lote_id)))
    itens = []
    for t in db.scalars(q):
        if not t.documentos:            # pessoa que ficou sem documentos (ex.: após correção de tipo)
            continue
        r = _resumo(t, checklist.avaliar(t))
        if not situacao or r["situacao"] == situacao:
            itens.append(r)
    itens.sort(key=lambda r: (_ORDEM[r["situacao"]], -r["pendencias"]))
    return {"total": len(itens), "exigidos": DOCUMENTOS_EXIGIDOS_TRABALHADOR, "exigidos_base": DOCUMENTOS_EXIGIDOS_TRABALHADOR,
            "irregulares": sum(1 for r in itens if r["situacao"] == "irregular"), "itens": itens}


def _obter(db: Session, trabalhador_id: int) -> Trabalhador:
    t = db.get(Trabalhador, trabalhador_id)
    if not t:
        raise HTTPException(404, "Trabalhador não encontrado")
    return t


@router.get("/{trabalhador_id}/dossie")
def dossie(trabalhador_id: int, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    """Tudo de uma pessoa: checklist (faltando / vencido / vencendo / ok), duplicados e os documentos."""
    return _dossie(_obter(db, trabalhador_id))


class FuncaoIn(BaseModel):
    funcao_chave: str | None = None      # chave de GET /funcoes, ou null para limpar


@router.put("/{trabalhador_id}/funcao")
def corrigir_funcao(trabalhador_id: int, body: FuncaoIn, db: Session = Depends(get_db),
                    _u: UsuarioAtual = Depends(revisor)):
    """Correção manual da função (vale mais que a leitura automática e não é sobrescrita ao reprocessar)."""
    t = _obter(db, trabalhador_id)
    if body.funcao_chave is not None and body.funcao_chave not in FUNCOES_NR:
        raise HTTPException(422, f"Função '{body.funcao_chave}' não existe (veja GET /funcoes)")
    t.funcao_chave = body.funcao_chave
    t.funcao = FUNCOES_NR[body.funcao_chave]["nome"] if body.funcao_chave else None
    t.funcao_origem, t.funcao_evidencia = "manual", None
    db.commit()
    return _dossie(t)


@router_funcoes.get("/funcoes")
def listar_funcoes(_u: UsuarioAtual = Depends(analista)):
    """Funções conhecidas e as NRs que cada uma exige (premissa demonstrativa: validar com SST)."""
    return [{"chave": k, "nome": f["nome"], "nrs": f["nrs"]} for k, f in FUNCOES_NR.items()]


def _dossie(t: Trabalhador) -> dict:
    c = checklist.avaliar(t)
    docs = sorted(t.documentos, key=lambda d: (d.tipo, d.criado_em))
    return _resumo(t, c) | {"checklist": c["checklist"], "outros_alertas": c["outros_alertas"],
                            "duplicados": c["duplicados"], "itens": [doc_out(d).model_dump(mode="json") for d in docs]}
