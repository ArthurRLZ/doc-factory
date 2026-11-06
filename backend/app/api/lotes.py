"""Upload e acompanhamento de lotes."""
import hashlib
import io
import json
import os
import tempfile
import zipfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.deps import UsuarioAtual, analista, revisor
from app.config import settings
from app.db import get_db
from app.models import Lote, Pagina, Revisao, VersaoLote, novo_id
from app.pipeline import fraude
from app.pipeline.rasterizar import contar_paginas
from app.schemas import DocumentoOut, LoteOut, PaginaOut
from app.storage import get_storage, key_original
from app.tipos import PRIORIDADES
from app.api.documentos import doc_out

router = APIRouter(prefix="/lotes", tags=["lotes"])

MIMES = {".pdf": "application/pdf", ".tif": "image/tiff", ".tiff": "image/tiff",
         ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


def lote_out(db: Session, lote: Lote) -> LoteOut:
    feitas = db.scalar(select(func.count()).select_from(Pagina)
                       .where(Pagina.lote_id == lote.id, Pagina.status.in_(("ok", "falhou")))) or 0
    out = LoteOut.model_validate(lote)
    out.paginas_processadas = feitas
    out.progresso = round(feitas / lote.total_paginas, 3) if lote.total_paginas else 0.0
    return out


@router.post("", response_model=LoteOut, status_code=201)
async def criar_lote(arquivo: UploadFile = File(...), nome: str | None = Form(None),
                     prioridade: str = Form("media", description="alta | media | baixa — lotes de prioridade alta são processados primeiro"),
                     db: Session = Depends(get_db), u: UsuarioAtual = Depends(analista)):
    prioridade = (prioridade or "media").lower().replace("normal", "media")
    if prioridade not in PRIORIDADES:
        raise HTTPException(422, "prioridade deve ser alta, media ou baixa")
    ext = os.path.splitext(arquivo.filename or "")[1].lower()
    if ext not in settings.extensoes:
        raise HTTPException(415, f"Extensão {ext or '(nenhuma)'} não suportada. Use: {settings.EXTENSOES_PERMITIDAS}")

    # streaming em blocos de 1 MB: nunca carrega um lote de 1 GB inteiro na memória
    sha, tamanho, limite = hashlib.sha256(), 0, settings.MAX_UPLOAD_MB * 1024 * 1024
    fd, tmp = tempfile.mkstemp(suffix=ext)
    try:
        with os.fdopen(fd, "wb") as f:
            while bloco := await arquivo.read(1024 * 1024):
                tamanho += len(bloco)
                if tamanho > limite:
                    raise HTTPException(413, f"Arquivo maior que {settings.MAX_UPLOAD_MB} MB")
                sha.update(bloco)
                f.write(bloco)
        digest = sha.hexdigest()

        existente = db.scalar(select(Lote).where(Lote.hash_sha256 == digest))
        if existente:
            raise HTTPException(409, {"mensagem": "Este arquivo já foi enviado", "lote_id": existente.id})

        try:
            n = contar_paginas(tmp)
        except Exception as e:
            raise HTTPException(422, f"Não consegui abrir o arquivo: {e}")
        if n == 0:
            raise HTTPException(422, "Arquivo sem páginas")
        alertas_arquivo = fraude.analisar_pdf(tmp)        # metadados do PDF (editor, modificação)

        lote_id = novo_id()
        key = key_original(lote_id, ext)
        get_storage().put_file(key, tmp)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

    lote = Lote(id=lote_id, nome=nome or arquivo.filename or "lote", arquivo_key=key, hash_sha256=digest,
                mime=MIMES.get(ext, "application/octet-stream"), tamanho_bytes=tamanho,
                total_paginas=n, status="processando", prioridade=PRIORIDADES[prioridade],
                enviado_por=u.login, alertas=alertas_arquivo)
    db.add(lote)
    db.add_all(Pagina(lote_id=lote_id, numero=i) for i in range(n))   # fila de trabalho = as páginas
    try:
        db.commit()
    except Exception:
        db.rollback()
        try:
            get_storage().delete(key)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Falha ao remover arquivo após erro ao registrar lote")
        raise
    return lote_out(db, lote)


@router.get("", response_model=list[LoteOut])
def listar_lotes(db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    return [lote_out(db, l) for l in db.scalars(select(Lote).order_by(Lote.criado_em.desc()).limit(100))]


def _obter(db: Session, lote_id: str) -> Lote:
    lote = db.get(Lote, lote_id)
    if not lote:
        raise HTTPException(404, "Lote não encontrado")
    return lote


@router.get("/{lote_id}", response_model=LoteOut)
def obter_lote(lote_id: str, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    return lote_out(db, _obter(db, lote_id))


@router.get("/{lote_id}/paginas", response_model=list[PaginaOut])
def paginas_do_lote(lote_id: str, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    return _obter(db, lote_id).paginas


@router.get("/{lote_id}/documentos", response_model=list[DocumentoOut])
def documentos_do_lote(lote_id: str, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(analista)):
    return [doc_out(d) for d in _obter(db, lote_id).documentos]


@router.post("/{lote_id}/reprocessar", response_model=LoteOut)
def reprocessar(lote_id: str, tudo: bool = False, db: Session = Depends(get_db), u: UsuarioAtual = Depends(revisor)):
    """Recoloca na fila as páginas que falharam (ou todas, com ?tudo=true)."""
    lote = _obter(db, lote_id)
    if lote.status in ("processando", "segmentando"):
        raise HTTPException(409, "Aguarde o processamento atual terminar.")
    cond = [Pagina.lote_id == lote_id]
    if not tudo:
        cond.append(Pagina.status.in_(("erro", "falhou")))
    if not db.scalar(select(func.count()).select_from(Pagina).where(*cond)):
        raise HTTPException(409, "Nenhuma página para reprocessar.")
    if lote.documentos:
        def retrato(obj):
            return json.loads(json.dumps({col.name: getattr(obj, col.name) for col in obj.__table__.columns},
                                         default=str, ensure_ascii=False))
        versao = VersaoLote(lote_id=lote_id, usuario=u.login, dados={
            "documentos": [retrato(d) for d in lote.documentos],
            "paginas": [retrato(p) for p in lote.paginas],
            "revisoes": [retrato(r) for r in db.scalars(select(Revisao).where(Revisao.lote_id == lote_id))],
        })
        db.add(versao)
    db.execute(update(Pagina).where(*cond).values(status="pendente", tentativas=0, erro=None))
    lote.status, lote.erro = "processando", None
    db.commit()
    return lote_out(db, lote)


@router.get("/{lote_id}/versoes")
def versoes_do_lote(lote_id: str, db: Session = Depends(get_db), _u: UsuarioAtual = Depends(revisor)):
    """Resultados e revisões preservados antes de cada reprocessamento."""
    _obter(db, lote_id)
    versoes = db.scalars(select(VersaoLote).where(VersaoLote.lote_id == lote_id).order_by(VersaoLote.id.desc()))
    return [{"id": v.id, "criado_em": v.criado_em, "usuario": v.usuario, **v.dados} for v in versoes]


@router.get("/{lote_id}/versoes/{versao_id}/documentos/{documento_id}/pdf")
def pdf_da_versao(lote_id: str, versao_id: int, documento_id: str, anonimizado: bool = True,
                  db: Session = Depends(get_db), _u: UsuarioAtual = Depends(revisor)):
    versao = db.get(VersaoLote, versao_id)
    if not versao or versao.lote_id != lote_id:
        raise HTTPException(404, "Versão não encontrada")
    documento = next((d for d in versao.dados.get("documentos", []) if d["id"] == documento_id), None)
    key = documento and documento.get("pdf_anon_key" if anonimizado else "pdf_key")
    if not key:
        raise HTTPException(404, "PDF da versão não encontrado")
    try:
        conteudo = get_storage().get_bytes(key)
    except FileNotFoundError:
        raise HTTPException(404, "PDF da versão não encontrado no armazenamento")
    return Response(conteudo, media_type="application/pdf")


@router.get("/{lote_id}/zip")
def baixar_zip(lote_id: str, anonimizado: bool = True, db: Session = Depends(get_db),
               u: UsuarioAtual = Depends(analista)):
    """Todos os documentos do lote num .zip, um PDF por documento, nomeados por ordem e tipo,
    mais um manifesto.json (tipo, páginas, validade, prioridade, resumo)."""
    if not anonimizado and u.autenticado and u.perfil == "analista":
        raise HTTPException(403, "O PDF original (com dados pessoais) exige perfil revisor ou superior")
    lote = _obter(db, lote_id)
    if lote.status != "concluido":
        raise HTTPException(409, f"Lote ainda não concluído (status: {lote.status})")
    st, buf, manifesto = get_storage(), io.BytesIO(), []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for d in lote.documentos:
            key = d.pdf_anon_key if anonimizado else d.pdf_key
            if not key:
                continue
            nome = f"{d.ordem + 1:03d}_{d.tipo.lower()}{'_anon' if anonimizado else ''}.pdf"
            z.writestr(nome, st.get_bytes(key))
            manifesto.append(doc_out(d).model_dump(mode="json") | {"arquivo": nome})
        z.writestr("manifesto.json", json.dumps({"lote": lote.nome, "lote_id": lote.id, "documentos": manifesto},
                                                ensure_ascii=False, indent=2))
    nome_zip = f"{os.path.splitext(lote.nome)[0]}_documentos.zip"
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{nome_zip}"'})


@router.get("/{lote_id}/paginas/{numero}/imagem")
def imagem_pagina(lote_id: str, numero: int, thumb: bool = True, db: Session = Depends(get_db),
                  u: UsuarioAtual = Depends(analista)):
    if u.autenticado and u.perfil == "analista":
        raise HTTPException(403, "As imagens originais e miniaturas exigem perfil revisor ou superior")
    p = db.scalar(select(Pagina).where(Pagina.lote_id == lote_id, Pagina.numero == numero))
    key = p and (p.thumb_key if thumb else p.imagem_key)
    if not key:
        raise HTTPException(404, "Imagem ainda não gerada")
    try:
        conteudo = get_storage().get_bytes(key)
    except FileNotFoundError:
        raise HTTPException(404, "Imagem da página não encontrada no armazenamento")
    return Response(conteudo, media_type="image/jpeg" if thumb else "image/png",
                    headers={"Cache-Control": "private, max-age=3600"})
