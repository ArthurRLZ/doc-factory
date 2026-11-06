"""Aprender com as correções humanas.

Quando o revisor troca o tipo de um documento, o sistema guarda:
  - o TÍTULO do documento (normalizado) → vira regra: página com esse título no topo ganha peso forte
    para o tipo corrigido (funciona mesmo sem modelo);
  - um TRECHO do texto, já anonimizado → vai como exemplo no pedido de classificação ao modelo.
Assim um layout novo é aprendido com UMA correção, e o efeito é rastreável (sinais da página
guardam qual aprendizado decidiu, e cada aprendizado conta seus usos). Dá para desativar um aprendizado.
"""
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import Aprendizado, Documento
from app.pipeline.classificar import normalizar

MAX_EXEMPLOS = 5


def _titulo_normalizado(doc: Documento) -> str:
    titulo = normalizar(doc.titulo or "").strip(" .:-")
    # título genérico demais (ou só um marcador) não vira regra
    if len(titulo) < 8 or titulo.startswith("["):
        return ""
    return titulo[:200]


def registrar(db: Session, doc: Documento, tipo_errado: str, tipo_certo: str, usuario: str) -> Aprendizado | None:
    if tipo_errado == tipo_certo:
        return None
    titulo = _titulo_normalizado(doc)
    existente = db.scalar(select(Aprendizado).where(Aprendizado.titulo == titulo, Aprendizado.ativo.is_(True))) \
        if titulo else None
    if existente:                       # a mesma correção de novo: atualiza em vez de duplicar
        existente.tipo_certo, existente.tipo_errado, existente.usuario = tipo_certo, tipo_errado, usuario
        return existente
    ap = Aprendizado(titulo=titulo, tipo_errado=tipo_errado, tipo_certo=tipo_certo,
                     exemplo=(doc.texto or "")[:600], documento_id=doc.id, usuario=usuario)
    db.add(ap)
    db.flush()
    return ap


def regras(db: Session) -> list[tuple[int, str, str]]:
    """[(id, título, tipo correto)] para o classificador por regras."""
    return [(a.id, a.titulo, a.tipo_certo)
            for a in db.scalars(select(Aprendizado).where(Aprendizado.ativo.is_(True), Aprendizado.titulo != ""))]


def exemplos(db: Session, n: int = MAX_EXEMPLOS) -> list[tuple[str, str]]:
    """[(tipo correto, trecho anonimizado)] das correções mais recentes, para o pedido ao modelo."""
    q = (select(Aprendizado).where(Aprendizado.ativo.is_(True), Aprendizado.exemplo.is_not(None))
         .order_by(Aprendizado.criado_em.desc()).limit(n))
    return [(a.tipo_certo, a.exemplo) for a in db.scalars(q)]


def contar_uso(db: Session, aprendizado_id: int) -> None:
    db.execute(update(Aprendizado).where(Aprendizado.id == aprendizado_id).values(usos=Aprendizado.usos + 1))
