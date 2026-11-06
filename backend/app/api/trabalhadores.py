"""Dossiê do trabalhador e checklist de documentos exigidos.

O trabalhador é identificado pela impressão digital do CPF — o CPF não é guardado.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import UsuarioAtual, analista
from app.api.documentos import doc_out
from app.db import get_db
from app.models import Documento, Trabalhador
from app.pipeline import checklist
from app.tipos import DOCUMENTOS_EXIGIDOS_TRABALHADOR

router = APIRouter(prefix="/trabalhadores", tags=["dossiê do trabalhador"])
_ORDEM = {"irregular": 0, "atencao": 1, "regular": 2}


def _resumo(t: Trabalhador, c: dict) -> dict:
    return {"id": t.id, "rotulo": f"Trabalhador {t.cpf_mascarado}", "cpf_mascarado": t.cpf_mascarado,
            "documentos": len(t.documentos), "situacao": c["situacao"], "pendencias": c["pendencias"],
            "faltando": c["faltando"], "vencidos": c["vencidos"], "vencendo": c["vencendo"]}


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
    return {"total": len(itens), "exigidos": DOCUMENTOS_EXIGIDOS_TRABALHADOR,
            "irregulares": sum(1 for r in itens if r["situacao"] == "irregular"), "itens": itens}


@router.get("/{trabalhador_id}/dossie")
def dossie(trabalhador_id: int, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    """Tudo de uma pessoa: checklist (faltando / vencido / vencendo / ok), duplicados e os documentos."""
    t = db.get(Trabalhador, trabalhador_id)
    if not t:
        raise HTTPException(404, "Trabalhador não encontrado")
    c = checklist.avaliar(t)
    docs = sorted(t.documentos, key=lambda d: (d.tipo, d.criado_em))
    return _resumo(t, c) | {"checklist": c["checklist"], "outros_alertas": c["outros_alertas"],
                            "duplicados": c["duplicados"], "itens": [doc_out(d).model_dump(mode="json") for d in docs]}
