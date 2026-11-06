"""Documentos, fila de revisão humana, auditoria, resumo, vencimentos e busca."""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import String, and_, func, literal, literal_column, or_, select, update
from sqlalchemy.orm import Session

from app import util
from app.api.deps import UsuarioAtual, analista, revisor
from app.config import settings
from app.db import E_POSTGRES, get_db, tem_unaccent
from app.llm import obter_llm
from app.models import Documento, Pagina, Revisao
from app.pipeline import aprendizado, explicabilidade, fraude, pre_revisao, validade
from app.pipeline.orquestrador import atribuir_trabalhador, gerar_arquivos
from app.pipeline.resumir import nome_prioridade, resumir_documento
from app.schemas import (
    BuscaItem,
    DocumentoOut,
    PaginaDocumentos,
    Prioridade,
    RevisaoIn,
    RevisaoOut,
    TrabalhadorRef,
    ValidadeOut,
)
from app.storage import get_storage
from app.tipos import (
    PRIORIDADES,
    SETORES,
    TIPOS,
    TIPOS_COM_VALIDADE,
    nome_tipo,
    setor_do_tipo,
)
from app.status import StatusLote, StatusRevisao

router = APIRouter(tags=["documentos"])

log = logging.getLogger(__name__)


def doc_out(d: Documento) -> DocumentoOut:
    o = DocumentoOut.model_validate(d)
    o.tipo_nome = nome_tipo(d.tipo)
    o.setor = setor_do_tipo(d.tipo)
    o.codigo = f"DOC-{(d.criado_em or datetime.now()).year}-{d.id[:6].upper()}"
    o.n_paginas = d.pagina_fim - d.pagina_inicio + 1
    o.origem_texto = explicabilidade.origem_texto(d.decidido_por)
    st, dias = validade.status(d.validade_data, d.tipo)
    o.validade = ValidadeOut(data=d.validade_data, inicio=d.validade_inicio, status=st, dias_restantes=dias,
                             origem=d.validade_origem, evidencia=d.validade_evidencia)
    if d.trabalhador:
        o.trabalhador = TrabalhadorRef(id=d.trabalhador.id, rotulo=f"Trabalhador {d.trabalhador.cpf_mascarado}",
                                       cpf_mascarado=d.trabalhador.cpf_mascarado)
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
                      q: str | None = None, risco: Literal["confiavel", "atencao", "alto_risco"] | None = None,
                      ordenar: Ordem = "recentes", pagina: int = 1, por_pagina: int = 20,
                      db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    """Lista documentos de todos os lotes — filtros da tela "Documentos" (setor, prioridade, tipo, prazo e busca).

    prazo: vencido | vencendo (até VALIDADE_ALERTA_DIAS) | esta_semana (até 7 dias) | vigente | indeterminado | sem_validade
    ordenar: recentes | prazo (vence primeiro) | prioridade (alta primeiro) | confianca (menor primeiro)
    """
    hoje = util.hoje()
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
    if risco:
        cond.append(Documento.risco == risco)
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
    hoje = util.hoje()
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
    except FileNotFoundError as e:
        raise HTTPException(404, "Arquivo do documento não encontrado no armazenamento") from e
    return Response(conteudo, media_type="application/pdf",
                    headers={"Content-Disposition": util.content_disposition(nome, inline=True)})


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


@router.post("/documentos/{doc_id}/pre-revisao", response_model=DocumentoOut)
def gerar_pre_revisao(doc_id: str, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    """(Re)gera a explicação + sugestão para o revisor. Só sugere: nada é aplicado."""
    d = _obter(db, doc_id)
    d.pre_revisao = pre_revisao.gerar(db, d.lote, d, _paginas(db, d.id), obter_llm())
    db.commit()
    return doc_out(d)


# ------------------------------------------------------------ revisão humana
@router.get("/revisao/fila", response_model=list[DocumentoOut])
def fila_de_revisao(lote_id: str | None = None, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    """Pendentes: prioridade mais alta primeiro; dentro da mesma prioridade, menor confiança primeiro."""
    q = select(Documento).where(Documento.status_revisao == StatusRevisao.PENDENTE)
    if lote_id:
        q = q.where(Documento.lote_id == lote_id)
    q = q.order_by(Documento.prioridade.desc(), Documento.confianca.asc(), Documento.criado_em)
    return [doc_out(d) for d in db.scalars(q.limit(200))]


@dataclass
class _Resultado:
    """O que uma ação de revisão produziu."""
    afetados: list[Documento]
    conteudo_mudou: bool = False                       # páginas/tipo mudaram → refaz os sinais de fraude
    obsoletos: list[str] = field(default_factory=list)  # arquivos a apagar DEPOIS do commit


def _aprovar(db: Session, d: Documento, r: RevisaoIn, usuario: str) -> _Resultado:
    d.status_revisao = StatusRevisao.REVISADO
    return _Resultado([d])


def _alterar_tipo(db: Session, d: Documento, r: RevisaoIn, usuario: str) -> _Resultado:
    if r.tipo not in TIPOS:
        raise HTTPException(422, f"tipo deve ser um de {list(TIPOS)}")
    aprendizado.registrar(db, d, d.tipo, r.tipo, usuario)   # o sistema aprende com a correção
    d.tipo, d.status_revisao = r.tipo, StatusRevisao.REVISADO
    atribuir_trabalhador(db, d, _paginas(db, d.id))      # o tipo decide se entra no dossiê
    resumir_documento(d.lote, d)
    return _Resultado([d], conteudo_mudou=True)


def _alterar_prioridade(db: Session, d: Documento, r: RevisaoIn, usuario: str) -> _Resultado:
    if r.prioridade is None:
        raise HTTPException(422, "informe prioridade: alta, media ou baixa")
    d.prioridade, d.prioridade_motivo = PRIORIDADES[r.prioridade], f"definida manualmente por {usuario}"
    d.prioridade_manual = True
    return _Resultado([d])


def _dividir(db: Session, d: Documento, r: RevisaoIn, usuario: str) -> _Resultado:
    lote, pags = d.lote, _paginas(db, d.id)
    numeros = [p.numero for p in pags]
    if r.pagina_corte is None or r.pagina_corte not in numeros or r.pagina_corte == numeros[0]:
        raise HTTPException(422, "pagina_corte deve ser uma página do documento (exceto a primeira)")
    # abre espaço na ordem para o novo documento
    db.execute(update(Documento).where(Documento.lote_id == lote.id, Documento.ordem > d.ordem)
               .values(ordem=Documento.ordem + 1))
    novo = Documento(lote_id=lote.id, ordem=d.ordem + 1, tipo=d.tipo, pagina_inicio=r.pagina_corte,
                     pagina_fim=d.pagina_fim, confianca=d.confianca, status_revisao=StatusRevisao.PENDENTE,
                     motivos=["criado por divisão manual — confirme o tipo"])
    db.add(novo)
    db.flush()
    antes_do_corte = [p for p in pags if p.numero < r.pagina_corte]
    depois_do_corte = [p for p in pags if p.numero >= r.pagina_corte]
    for p in depois_do_corte:
        p.documento_id = novo.id
    d.status_revisao = StatusRevisao.REVISADO
    for doc, paginas in ((d, antes_do_corte), (novo, depois_do_corte)):
        gerar_arquivos(lote, doc, paginas)
        atribuir_trabalhador(db, doc, paginas)
        resumir_documento(lote, doc)
    return _Resultado([d, novo], conteudo_mudou=True)


def _juntar_proximo(db: Session, d: Documento, r: RevisaoIn, usuario: str) -> _Resultado:
    lote = d.lote
    prox = db.scalar(select(Documento).where(Documento.lote_id == lote.id, Documento.ordem == d.ordem + 1))
    if not prox:
        raise HTTPException(422, "Não há documento seguinte para juntar")
    for p in _paginas(db, prox.id):
        p.documento_id = d.id
    obsoletos = [k for k in (prox.pdf_key, prox.pdf_anon_key) if k]
    db.add(Revisao(documento_id=None, lote_id=lote.id, usuario=usuario, acao="removido_por_juncao",
                   antes=_snapshot(prox) | {"id": prox.id}))
    db.delete(prox)
    db.flush()
    db.execute(update(Documento).where(Documento.lote_id == lote.id, Documento.ordem > d.ordem + 1)
               .values(ordem=Documento.ordem - 1))
    d.status_revisao = StatusRevisao.REVISADO
    paginas = _paginas(db, d.id)
    gerar_arquivos(lote, d, paginas)
    atribuir_trabalhador(db, d, paginas)
    resumir_documento(lote, d)
    return _Resultado([d], conteudo_mudou=True, obsoletos=obsoletos)


_ACOES = {"aprovar": _aprovar, "alterar_tipo": _alterar_tipo, "alterar_prioridade": _alterar_prioridade,
          "dividir": _dividir, "juntar_proximo": _juntar_proximo}


def _apagar_arquivos(chaves: list[str]) -> None:
    for key in chaves:
        try:
            get_storage().delete(key)
        except Exception:
            log.exception("Não foi possível remover arquivo obsoleto após junção: %s", key)


@router.post("/documentos/{doc_id}/revisao", response_model=list[DocumentoOut])
def revisar(doc_id: str, r: RevisaoIn, db: Session = Depends(get_db), u: UsuarioAtual = Depends(revisor)):
    """Ação do revisor: aprovar · alterar_tipo · alterar_prioridade · dividir · juntar_proximo.
    Toda ação fica na trilha de auditoria (antes/depois, quem, quando)."""
    d = _obter(db, doc_id)
    if d.lote.status in (StatusLote.PROCESSANDO, StatusLote.SEGMENTANDO):
        raise HTTPException(409, "Aguarde o processamento do lote terminar antes de revisar.")
    usuario = u.login if u.autenticado else (r.usuario or "anonimo")
    antes = _snapshot(d)
    seguiu = pre_revisao.seguiu(d.pre_revisao, r.acao, r.tipo)     # mede se a sugestão da pré-revisão ajuda
    res = _ACOES[r.acao](db, d, r, usuario)
    if r.acao in ("alterar_tipo", "dividir", "juntar_proximo"):   # aprovar confirma a decisão que já havia
        for x in res.afetados:
            x.decidido_por = "humano"
    if res.conteudo_mudou:
        db.flush()
        for x in res.afetados:             # conteúdo ou datas mudaram: sinais de fraude de novo
            fraude.aplicar(db, d.lote, x, _paginas(db, x.id))
    db.add(Revisao(documento_id=d.id, lote_id=d.lote_id, usuario=usuario, acao=r.acao,
                   antes=antes, depois=_snapshot(d) | ({"seguiu_sugestao": seguiu} if seguiu is not None else {})))
    db.commit()
    _apagar_arquivos(res.obsoletos)        # só depois do commit: se o banco falhar, os arquivos continuam
    return [doc_out(x) for x in res.afetados]


# ------------------------------------------------------------ busca (OCR pesquisável)
@router.get("/busca", response_model=list[BuscaItem])
def buscar(q: str, tipo: str | None = None, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    if len(q.strip()) < 2:
        raise HTTPException(422, "Busca muito curta")
    if E_POSTGRES:
        # palavra inteira pelo radical ("contrato" acha "contratada") OU pedaço de palavra ("certid"),
        # e sem diferenciar acento ("certidao" acha "certidão") quando a extensão unaccent existe
        cfg = literal_column("'portuguese'")
        def sem_acento(x):
            return func.unaccent(x) if tem_unaccent() else x
        texto = func.coalesce(Documento.texto, "")
        termo = literal(q.strip(), String)
        tsq = func.plainto_tsquery(cfg, sem_acento(termo))
        vetor = func.to_tsvector(cfg, sem_acento(texto))
        pedaco = func.lower(sem_acento(texto)).contains(func.lower(sem_acento(termo)))
        trecho = func.ts_headline(cfg, Documento.texto, func.plainto_tsquery(cfg, termo),
                                  "StartSel=«,StopSel=»,MaxWords=25,MinWords=10")
        stmt = (select(Documento, trecho).where(or_(vetor.op("@@")(tsq), pedaco))
                .order_by(func.ts_rank(vetor, tsq).desc()))
    else:  # SQLite (dev): LIKE simples
        trecho = func.substr(Documento.texto, func.max(1, func.instr(func.lower(Documento.texto), q.lower()) - 60), 160)
        stmt = select(Documento, trecho).where(Documento.texto.ilike(f"%{q}%"))
    if tipo:
        stmt = stmt.where(Documento.tipo == tipo)
    return [BuscaItem(documento_id=d.id, lote_id=d.lote_id, tipo=d.tipo, trecho=t or "")
            for d, t in db.execute(stmt.limit(50)).all()]
