"""Regras de separação escritas em português: entender (sem gravar), cadastrar, ativar/desativar, remover.

Cada lote guarda um retrato das regras ativas no upload (Lote.regras_aplicadas): mudar uma regra aqui vale para
os PRÓXIMOS lotes; um lote antigo só muda com POST /lotes/{id}/reprocessar?atualizar_regras=true.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import UsuarioAtual, admin, analista, revisor
from app.db import get_db
from app.llm import obter_llm
from app.models import RegraSeparacao
from app.pipeline import regras_separacao as rs

router = APIRouter(prefix="/regras-separacao", tags=["regras de separação"])


class TextoRegra(BaseModel):
    texto: str = Field(..., min_length=3, max_length=500, examples=["mantenha o contrato inteiro junto"])


def _com_descricao(regras: list[dict]) -> list[dict]:
    return [r | {"descricao": rs.descrever(r)} for r in regras]


def _out(r: RegraSeparacao) -> dict:
    return {"id": r.id, "texto": r.texto, "regras": _com_descricao(r.estruturada), "interpretada_por": r.interpretada_por,
            "ativa": r.ativa, "criada_por": r.criada_por, "criado_em": r.criado_em}


def _entender(texto: str) -> tuple[list[dict], str] | JSONResponse:
    regras, por = rs.interpretar(texto, obter_llm())
    if not regras:
        return JSONResponse(status_code=422, content={
            "detail": "Não entendi a regra. Escreva uma instrução sobre como separar os documentos.",
            "exemplos": rs.EXEMPLOS})
    return regras, por


@router.post("/interpretar")
def interpretar(body: TextoRegra, _u: UsuarioAtual = Depends(revisor)):
    """Mostra como o sistema entendeu a frase. NÃO grava."""
    r = _entender(body.texto)
    if isinstance(r, JSONResponse):
        return r
    regras, por = r
    return {"texto": body.texto, "regras": _com_descricao(regras), "interpretada_por": por}


@router.post("", status_code=201)
def criar(body: TextoRegra, db: Session = Depends(get_db), u: UsuarioAtual = Depends(revisor)):
    r = _entender(body.texto)
    if isinstance(r, JSONResponse):
        return r
    regras, por = r
    regra = RegraSeparacao(texto=body.texto.strip(), estruturada=regras, interpretada_por=por, ativa=True,
                           criada_por=u.login)
    db.add(regra)
    db.commit()
    return _out(regra)


@router.get("")
def listar(db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    return [_out(r) for r in db.scalars(select(RegraSeparacao).order_by(RegraSeparacao.id.desc()))]


def _obter(db: Session, regra_id: int) -> RegraSeparacao:
    r = db.get(RegraSeparacao, regra_id)
    if not r:
        raise HTTPException(404, "Regra não encontrada")
    return r


@router.post("/{regra_id}/desativar")
def desativar(regra_id: int, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(revisor)):
    r = _obter(db, regra_id)
    r.ativa = False
    db.commit()
    return _out(r)


@router.post("/{regra_id}/ativar")
def ativar(regra_id: int, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(revisor)):
    r = _obter(db, regra_id)
    r.ativa = True
    db.commit()
    return _out(r)


@router.delete("/{regra_id}")
def remover(regra_id: int, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(admin)):
    db.delete(_obter(db, regra_id))
    db.commit()
    return {"apagada": regra_id}
