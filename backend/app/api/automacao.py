"""Meta de automação: curva por limiar, acurácia medida pelas revisões e ajuste do limiar ao vivo."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import UsuarioAtual, admin, analista
from app.db import get_db
from app.pipeline import automacao

router = APIRouter(prefix="/automacao", tags=["meta de automação"])


class LimiarIn(BaseModel):
    limiar: float = Field(ge=0.0, le=1.0, description="confiança mínima para aprovar sem revisão humana")
    aplicar: bool = Field(True, description="reavaliar agora os documentos ainda não revisados por uma pessoa")


@router.get("")
def ver_curva(db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    """Para cada limiar: quantos documentos passam sozinhos, quantos vão para revisão e a acurácia
    medida nas revisões humanas (só aparece com amostra suficiente)."""
    return automacao.curva(db)


@router.get("/sugerir")
def sugerir_limiar(meta: float = 95.0, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    """Menor limiar que atinge a acurácia-meta (em %), segundo as revisões já feitas."""
    return automacao.sugerir(db, meta)


@router.put("/limiar")
def definir_limiar(dados: LimiarIn, db: Session = Depends(get_db), u: UsuarioAtual = Depends(admin)):
    """Muda o limiar de revisão em tempo real (vale para API e workers) e, por padrão, reavalia a fila."""
    mudaram = automacao.definir_limiar(db, dados.limiar, u.login, dados.aplicar)
    return {"limiar": dados.limiar, "documentos_reavaliados": mudaram} | {"curva": automacao.curva(db)}


# ------------------------------------------------------------ aprender com as correções
router_aprendizados = APIRouter(prefix="/aprendizados", tags=["meta de automação"])


@router_aprendizados.get("")
def listar_aprendizados(db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    """O que o sistema aprendeu com as correções de tipo: título → tipo correto, quem corrigiu e quantas vezes foi usado."""
    from sqlalchemy import select

    from app.models import Aprendizado
    return [{"id": a.id, "titulo": a.titulo, "tipo_errado": a.tipo_errado, "tipo_certo": a.tipo_certo,
             "usuario": a.usuario, "usos": a.usos, "ativo": a.ativo, "criado_em": a.criado_em}
            for a in db.scalars(select(Aprendizado).order_by(Aprendizado.criado_em.desc()))]


@router_aprendizados.post("/{aprendizado_id}/desativar")
def desativar_aprendizado(aprendizado_id: int, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(admin)):
    """Desfaz um aprendizado (ex.: correção feita por engano)."""
    from fastapi import HTTPException

    from app.models import Aprendizado
    a = db.get(Aprendizado, aprendizado_id)
    if not a:
        raise HTTPException(404, "Aprendizado não encontrado")
    a.ativo = False
    db.commit()
    return {"id": a.id, "ativo": False}
