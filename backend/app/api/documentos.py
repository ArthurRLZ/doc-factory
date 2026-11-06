"""Documentos, fila de revisão humana, auditoria, resumo, vencimentos e busca."""
import logging
from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import and_, func, literal_column, or_, select, update
from sqlalchemy.orm import Session

from app.api.deps import UsuarioAtual, analista, revisor
from app.db import E_POSTGRES, get_db
from app.models import Documento, Pagina, Revisao
from app.pipeline import validade
from app.pipeline.orquestrador import gerar_arquivos
from app.pipeline.resumir import nome_prioridade, resumir_documento
from app.config import settings
from app.schemas import (BuscaItem, DocumentoOut, PaginaDocumentos, Prioridade, RevisaoIn, RevisaoOut,
                         ValidadeOut)
from app.storage import get_storage
from app.tipos import PRIORIDADES, SETORES, TIPOS, TIPOS_COM_VALIDADE, nome_tipo, setor_do_tipo

router = APIRouter(tags=["documentos"])
log = logging.getLogger(__name__)


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


Prazo = Literal["vencido", "vencendo", "vigente", "indeterminado", "sem_validade", "esta_semana"]
Ordem = Literal["recentes", "prazo", "prioridade", "confianca"]


@router.get("/documentos", response_model=PaginaDocumentos)
def listar_documentos(tipo: str | None = None, setor: str | None = None, prioridade: Prioridade | None = None,
                      status_revisao: str | None = None, prazo: Prazo | None = None, lote_id: str | None = None,
                      q: str | None = None, ordenar: Ordem = "recentes", pagina: int = 1, por_pagina: int = 20,
                      db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    """Lista documentos de todos os lotes — filtros da tela "Documentos" (setor, prioridade, tipo, prazo e busca).

    prazo: vencido | vencendo (até VALIDADE_ALERTA_DIAS) | esta_semana (até 7 dias) | vigente | indeterminado | sem_validade
    ordenar: recentes | prazo (vence primeiro) | prioridade (alta primeiro) | confianca (menor primeiro)
    """
    hoje = date.today()
    cond = []
    if tipo:
        cond.append(Documento.tipo == tipo)
    if setor:
        cond.append(Documento.tipo.in_([t for t, s in SETORES.items() if s == setor] or ["__nenhum__"]))
    if prioridade:
        cond.append(Documento.prioridade == PRIORIDADES[prioridade])
    if status_revisao:
        cond.append(Documento.status_revisao == status_revisao)
    if lote_id:
        cond.append(Documento.lote_id == lote_id)
    if q and q.strip():
        termo = f"%{q.strip()}%"
        cond.append(or_(Documento.titulo.ilike(termo), Documento.texto.ilike(termo), Documento.resumo.ilike(termo),
                        Documento.tipo.ilike(termo)))
    if prazo:
        data, alerta = Documento.validade_data, hoje + timedelta(days=settings.VALIDADE_ALERTA_DIAS)
        cond.append({
            "vencido": data < hoje,
            "vencendo": and_(data >= hoje, data <= alerta),
            "esta_semana": and_(data >= hoje, data <= hoje + timedelta(days=7)),
            "vigente": data > alerta,
            "indeterminado": and_(data.is_(None), Documento.tipo.in_(TIPOS_COM_VALIDADE)),
            "sem_validade": and_(data.is_(None), Documento.tipo.not_in(TIPOS_COM_VALIDADE)),
        }[prazo])
    total = db.scalar(select(func.count()).select_from(Documento).where(*cond)) or 0
    ordem = {
        "recentes": (Documento.criado_em.desc(), Documento.ordem),
        "prazo": (Documento.validade_data.is_(None), Documento.validade_data, Documento.criado_em.desc()),
        "prioridade": (Documento.prioridade.desc(), Documento.confianca.asc()),
        "confianca": (Documento.confianca.asc(),),
    }[ordenar]
    pagina, por_pagina = max(1, pagina), min(max(1, por_pagina), 200)
    itens = db.scalars(select(Documento).where(*cond).order_by(*ordem)
                       .offset((pagina - 1) * por_pagina).limit(por_pagina))
    return PaginaDocumentos(total=total, pagina=pagina, por_pagina=por_pagina,
                            paginas=max(1, -(-total // por_pagina)), itens=[doc_out(d) for d in itens])


@router.get("/setores")
def listar_setores(_u: UsuarioAtual = Depends(analista)):
    """Setores para o filtro da tela, com os tipos de cada um."""
    por_setor: dict[str, list[str]] = {}
    for t, s in SETORES.items():
        por_setor.setdefault(s, []).append(t)
    return [{"setor": s, "tipos": ts} for s, ts in por_setor.items()]


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
    try:
        conteudo = get_storage().get_bytes(key)
    except FileNotFoundError:
        raise HTTPException(404, "Arquivo do documento não encontrado no armazenamento")
    return Response(conteudo, media_type="application/pdf",
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
    arquivos_obsoletos = []

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
        arquivos_obsoletos = [k for k in (prox.pdf_key, prox.pdf_anon_key) if k]
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
    for key in arquivos_obsoletos:
        try:
            get_storage().delete(key)
        except Exception:
            log.exception("Não foi possível remover arquivo obsoleto após junção: %s", key)
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
