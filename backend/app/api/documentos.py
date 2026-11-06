"""Documentos, fila de revisão humana, auditoria, resumo, vencimentos e busca."""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import func, literal_column, select, update
from sqlalchemy.orm import Session

from app.api.deps import UsuarioAtual, analista, revisor
from app.db import E_POSTGRES, get_db
from app.models import Documento, Pagina, Revisao
from app.pipeline import validade
from app.pipeline.orquestrador import gerar_arquivos
from app.pipeline.resumir import nome_prioridade, resumir_documento
from app.schemas import BuscaItem, DocumentoOut, Prioridade, RevisaoIn, RevisaoOut, ValidadeOut
from app.storage import get_storage
from app.tipos import PRIORIDADES, TIPOS, nome_tipo, setor_do_tipo

router = APIRouter(tags=["documentos"])


def doc_out(d: Documento) -> DocumentoOut:
    o = DocumentoOut.model_validate(d)
    o.tipo_nome = nome_tipo(d.tipo)
    o.setor = setor_do_tipo(d.tipo)
    o.codigo = f"DOC-{(d.criado_em or datetime.now()).year}-{d.id[:6].upper()}"
    o.n_paginas = d.pagina_fim - d.pagina_inicio + 1
    st, dias = validade.status(d.validade_data, d.tipo)
    o.validade = ValidadeOut(data=d.validade_data, inicio=d.validade_inicio, status=st, dias_restantes=dias,
                             origem=d.validade_origem, evidencia=d.validade_evidencia)
    return o


def _snapshot(d: Documento) -> dict:
    return {"tipo": d.tipo, "pagina_inicio": d.pagina_inicio, "pagina_fim": d.pagina_fim,
            "status_revisao": d.status_revisao, "prioridade": nome_prioridade(d.prioridade)}


def _paginas(db: Session, doc_id: str) -> list[Pagina]:
    return list(db.scalars(select(Pagina).where(Pagina.documento_id == doc_id).order_by(Pagina.numero)))


def _obter(db: Session, doc_id: str) -> Documento:
    d = db.get(Documento, doc_id)
    if not d:
        raise HTTPException(404, "Documento não encontrado")
    return d


@router.get("/tipos")
def listar_tipos(_u: UsuarioAtual = Depends(analista)):
    return [{"codigo": c, "nome": t["nome"], "descricao": t.get("descricao", ""),
             "prioridade": t.get("prioridade", "media"), "campos": t.get("campos", []),
             "validade": t.get("validade")} for c, t in TIPOS.items()]


@router.get("/documentos", response_model=list[DocumentoOut])
def listar_documentos(tipo: str | None = None, status_revisao: str | None = None,
                      prioridade: Prioridade | None = None, lote_id: str | None = None,
                      limite: int = 100, deslocamento: int = 0,
                      db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    """Lista documentos de todos os lotes, com filtros. Mais recentes primeiro."""
    q = select(Documento)
    if tipo:
        q = q.where(Documento.tipo == tipo)
    if status_revisao:
        q = q.where(Documento.status_revisao == status_revisao)
    if prioridade:
        q = q.where(Documento.prioridade == PRIORIDADES[prioridade])
    if lote_id:
        q = q.where(Documento.lote_id == lote_id)
    q = q.order_by(Documento.criado_em.desc(), Documento.ordem).offset(max(0, deslocamento)).limit(min(max(1, limite), 500))
    return [doc_out(d) for d in db.scalars(q)]


@router.get("/vencimentos", response_model=list[DocumentoOut])
def vencimentos(ate_dias: int = 30, incluir_vencidos: bool = True, lote_id: str | None = None,
                db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    """Documentos que vencem nos próximos `ate_dias` dias (e os já vencidos), do mais urgente ao menos."""
    hoje = date.today()
    q = select(Documento).where(Documento.validade_data.is_not(None),
                                Documento.validade_data <= hoje + timedelta(days=max(0, ate_dias)))
    if not incluir_vencidos:
        q = q.where(Documento.validade_data >= hoje)
    if lote_id:
        q = q.where(Documento.lote_id == lote_id)
    return [doc_out(d) for d in db.scalars(q.order_by(Documento.validade_data).limit(500))]


@router.get("/documentos/{doc_id}", response_model=DocumentoOut)
def obter_documento(doc_id: str, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    return doc_out(_obter(db, doc_id))


@router.get("/documentos/{doc_id}/pdf")
def baixar_pdf(doc_id: str, anonimizado: bool = True, db: Session = Depends(get_db),
               u: UsuarioAtual = Depends(analista)):
    """Por padrão entrega a versão anonimizada (privacidade por padrão).
    Com login ativo, o PDF original (sem tarjas) exige perfil revisor ou superior."""
    d = _obter(db, doc_id)
    if not anonimizado and u.autenticado and u.perfil == "analista":
        raise HTTPException(403, "O PDF original (com dados pessoais) exige perfil revisor ou superior")
    key = d.pdf_anon_key if anonimizado else d.pdf_key
    if not key:
        raise HTTPException(404, "PDF ainda não gerado")
    nome = f"{d.ordem + 1:03d}_{d.tipo.lower()}{'_anon' if anonimizado else ''}.pdf"
    return Response(get_storage().get_bytes(key), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{nome}"'})


@router.get("/documentos/{doc_id}/revisoes", response_model=list[RevisaoOut])
def trilha_de_auditoria(doc_id: str, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    """Todas as decisões humanas sobre o documento, da mais antiga para a mais nova."""
    _obter(db, doc_id)
    return list(db.scalars(select(Revisao).where(Revisao.documento_id == doc_id).order_by(Revisao.em, Revisao.id)))


@router.post("/documentos/{doc_id}/resumo", response_model=DocumentoOut)
def gerar_resumo(doc_id: str, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(revisor)):
    """Gera o resumo de novo (ex.: depois de configurar o modelo, ou após uma correção)."""
    d = _obter(db, doc_id)
    resumir_documento(d.lote, d)
    db.commit()
    return doc_out(d)


# ------------------------------------------------------------ revisão humana
@router.get("/revisao/fila", response_model=list[DocumentoOut])
def fila_de_revisao(lote_id: str | None = None, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    """Pendentes: prioridade mais alta primeiro; dentro da mesma prioridade, menor confiança primeiro."""
    q = select(Documento).where(Documento.status_revisao == "pendente")
    if lote_id:
        q = q.where(Documento.lote_id == lote_id)
    q = q.order_by(Documento.prioridade.desc(), Documento.confianca.asc(), Documento.criado_em)
    return [doc_out(d) for d in db.scalars(q.limit(200))]


@router.post("/documentos/{doc_id}/revisao", response_model=list[DocumentoOut])
def revisar(doc_id: str, r: RevisaoIn, db: Session = Depends(get_db), u: UsuarioAtual = Depends(revisor)):
    d = _obter(db, doc_id)
    lote = d.lote
    usuario = u.login if u.autenticado else (r.usuario or "anonimo")
    antes = _snapshot(d)
    afetados = [d]

    if r.acao == "aprovar":
        d.status_revisao = "revisado"

    elif r.acao == "alterar_tipo":
        if r.tipo not in TIPOS:
            raise HTTPException(422, f"tipo deve ser um de {list(TIPOS)}")
        d.tipo, d.status_revisao = r.tipo, "revisado"
        resumir_documento(lote, d)

    elif r.acao == "alterar_prioridade":
        if r.prioridade is None:
            raise HTTPException(422, "informe prioridade: alta, media ou baixa")
        d.prioridade, d.prioridade_motivo = PRIORIDADES[r.prioridade], f"definida manualmente por {usuario}"

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
        resumir_documento(lote, d)
        resumir_documento(lote, novo)
        afetados.append(novo)

    elif r.acao == "juntar_proximo":
        prox = db.scalar(select(Documento).where(Documento.lote_id == lote.id, Documento.ordem == d.ordem + 1))
        if not prox:
            raise HTTPException(422, "Não há documento seguinte para juntar")
        for p in _paginas(db, prox.id):
            p.documento_id = d.id
        db.add(Revisao(documento_id=None, lote_id=lote.id, usuario=usuario, acao="removido_por_juncao",
                       antes=_snapshot(prox) | {"id": prox.id}))
        db.delete(prox)
        db.flush()
        db.execute(update(Documento).where(Documento.lote_id == lote.id, Documento.ordem > d.ordem + 1)
                   .values(ordem=Documento.ordem - 1))
        d.status_revisao = "revisado"
        gerar_arquivos(lote, d, _paginas(db, d.id))
        resumir_documento(lote, d)

    db.add(Revisao(documento_id=d.id, lote_id=lote.id, usuario=usuario, acao=r.acao,
                   antes=antes, depois=_snapshot(d)))
    db.commit()
    return [doc_out(x) for x in afetados]


# ------------------------------------------------------------ busca (OCR pesquisável)
@router.get("/busca", response_model=list[BuscaItem])
def buscar(q: str, tipo: str | None = None, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
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
