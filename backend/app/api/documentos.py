"""Documentos, fila de revisão humana e busca."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import func, literal_column, select, update
from sqlalchemy.orm import Session

from app.db import E_POSTGRES, get_db
from app.models import Documento, Pagina, Revisao
from app.pipeline.orquestrador import gerar_arquivos
from app.schemas import BuscaItem, DocumentoOut, RevisaoIn
from app.storage import get_storage
from app.tipos import TIPOS, nome_tipo

router = APIRouter(tags=["documentos"])


def doc_out(d: Documento) -> DocumentoOut:
    o = DocumentoOut.model_validate(d)
    o.tipo_nome = nome_tipo(d.tipo)
    o.n_paginas = d.pagina_fim - d.pagina_inicio + 1
    return o


def _snapshot(d: Documento) -> dict:
    return {"tipo": d.tipo, "pagina_inicio": d.pagina_inicio, "pagina_fim": d.pagina_fim,
            "status_revisao": d.status_revisao}


def _paginas(db: Session, doc_id: str) -> list[Pagina]:
    return list(db.scalars(select(Pagina).where(Pagina.documento_id == doc_id).order_by(Pagina.numero)))


def _obter(db: Session, doc_id: str) -> Documento:
    d = db.get(Documento, doc_id)
    if not d:
        raise HTTPException(404, "Documento não encontrado")
    return d


@router.get("/tipos")
def listar_tipos():
    return [{"codigo": c, "nome": t["nome"]} for c, t in TIPOS.items()]


@router.get("/documentos/{doc_id}", response_model=DocumentoOut)
def obter_documento(doc_id: str, db: Session = Depends(get_db)):
    return doc_out(_obter(db, doc_id))


@router.get("/documentos/{doc_id}/pdf")
def baixar_pdf(doc_id: str, anonimizado: bool = True, db: Session = Depends(get_db)):
    """Por padrão entrega a versão anonimizada (privacidade por padrão)."""
    d = _obter(db, doc_id)
    key = d.pdf_anon_key if anonimizado else d.pdf_key
    if not key:
        raise HTTPException(404, "PDF ainda não gerado")
    nome = f"{d.ordem + 1:03d}_{d.tipo.lower()}{'_anon' if anonimizado else ''}.pdf"
    return Response(get_storage().get_bytes(key), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{nome}"'})


# ------------------------------------------------------------ revisão humana
@router.get("/revisao/fila", response_model=list[DocumentoOut])
def fila_de_revisao(lote_id: str | None = None, db: Session = Depends(get_db)):
    q = select(Documento).where(Documento.status_revisao == "pendente")
    if lote_id:
        q = q.where(Documento.lote_id == lote_id)
    return [doc_out(d) for d in db.scalars(q.order_by(Documento.confianca.asc()).limit(200))]


@router.post("/documentos/{doc_id}/revisao", response_model=list[DocumentoOut])
def revisar(doc_id: str, r: RevisaoIn, db: Session = Depends(get_db)):
    d = _obter(db, doc_id)
    lote = d.lote
    antes = _snapshot(d)
    afetados = [d]

    if r.acao == "aprovar":
        d.status_revisao = "revisado"

    elif r.acao == "alterar_tipo":
        if r.tipo not in TIPOS:
            raise HTTPException(422, f"tipo deve ser um de {list(TIPOS)}")
        d.tipo, d.status_revisao = r.tipo, "revisado"

    elif r.acao == "dividir":
        pags = _paginas(db, d.id)
        numeros = [p.numero for p in pags]
        if r.pagina_corte is None or r.pagina_corte not in numeros or r.pagina_corte == numeros[0]:
            raise HTTPException(422, "pagina_corte deve ser uma página do documento (exceto a primeira)")
        # abre espaço na ordem para o novo documento
        db.execute(update(Documento).where(Documento.lote_id == lote.id, Documento.ordem > d.ordem)
                   .values(ordem=Documento.ordem + 1))
        novo = Documento(lote_id=lote.id, ordem=d.ordem + 1, tipo=d.tipo, pagina_inicio=r.pagina_corte,
                         pagina_fim=d.pagina_fim, confianca=d.confianca, status_revisao="pendente",
                         motivos=["criado por divisão manual — confirme o tipo"])
        db.add(novo)
        db.flush()
        for p in pags:
            if p.numero >= r.pagina_corte:
                p.documento_id = novo.id
        d.status_revisao = "revisado"
        gerar_arquivos(lote, d, [p for p in pags if p.numero < r.pagina_corte])
        gerar_arquivos(lote, novo, [p for p in pags if p.numero >= r.pagina_corte])
        afetados.append(novo)

    elif r.acao == "juntar_proximo":
        prox = db.scalar(select(Documento).where(Documento.lote_id == lote.id, Documento.ordem == d.ordem + 1))
        if not prox:
            raise HTTPException(422, "Não há documento seguinte para juntar")
        for p in _paginas(db, prox.id):
            p.documento_id = d.id
        db.add(Revisao(documento_id=None, lote_id=lote.id, usuario=r.usuario, acao="removido_por_juncao",
                       antes=_snapshot(prox) | {"id": prox.id}))
        db.delete(prox)
        db.flush()
        db.execute(update(Documento).where(Documento.lote_id == lote.id, Documento.ordem > d.ordem + 1)
                   .values(ordem=Documento.ordem - 1))
        d.status_revisao = "revisado"
        gerar_arquivos(lote, d, _paginas(db, d.id))

    db.add(Revisao(documento_id=d.id, lote_id=lote.id, usuario=r.usuario, acao=r.acao,
                   antes=antes, depois=_snapshot(d)))
    db.commit()
    return [doc_out(x) for x in afetados]


# ------------------------------------------------------------ busca (OCR pesquisável)
@router.get("/busca", response_model=list[BuscaItem])
def buscar(q: str, tipo: str | None = None, db: Session = Depends(get_db)):
    if len(q.strip()) < 2:
        raise HTTPException(422, "Busca muito curta")
    if E_POSTGRES:
        cfg = literal_column("'portuguese'")
        tsq = func.plainto_tsquery(cfg, q)
        vetor = func.to_tsvector(cfg, func.coalesce(Documento.texto, ""))
        trecho = func.ts_headline(cfg, Documento.texto, tsq,
                                  "StartSel=«,StopSel=»,MaxWords=25,MinWords=10")
        stmt = (select(Documento, trecho).where(vetor.op("@@")(tsq))
                .order_by(func.ts_rank(vetor, tsq).desc()))
    else:  # SQLite (dev): LIKE simples
        trecho = func.substr(Documento.texto, func.max(1, func.instr(func.lower(Documento.texto), q.lower()) - 60), 160)
        stmt = select(Documento, trecho).where(Documento.texto.ilike(f"%{q}%"))
    if tipo:
        stmt = stmt.where(Documento.tipo == tipo)
    return [BuscaItem(documento_id=d.id, lote_id=d.lote_id, tipo=d.tipo, trecho=t or "")
            for d, t in db.execute(stmt.limit(50)).all()]
