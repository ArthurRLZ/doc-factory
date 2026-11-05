"""Upload e acompanhamento de lotes."""
import hashlib
import os
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Lote, Pagina, novo_id
from app.pipeline.rasterizar import contar_paginas
from app.schemas import DocumentoOut, LoteOut, PaginaOut
from app.storage import get_storage, key_original
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
async def criar_lote(arquivo: UploadFile = File(...), nome: str | None = Form(None), db: Session = Depends(get_db)):
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

        lote_id = novo_id()
        key = key_original(lote_id, ext)
        get_storage().put_file(key, tmp)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

    lote = Lote(id=lote_id, nome=nome or arquivo.filename or "lote", arquivo_key=key, hash_sha256=digest,
                mime=MIMES.get(ext, "application/octet-stream"), tamanho_bytes=tamanho,
                total_paginas=n, status="processando")
    db.add(lote)
    db.add_all(Pagina(lote_id=lote_id, numero=i) for i in range(n))   # fila de trabalho = as páginas
    db.commit()
    return lote_out(db, lote)


@router.get("", response_model=list[LoteOut])
def listar_lotes(db: Session = Depends(get_db)):
    return [lote_out(db, l) for l in db.scalars(select(Lote).order_by(Lote.criado_em.desc()).limit(100))]


def _obter(db: Session, lote_id: str) -> Lote:
    lote = db.get(Lote, lote_id)
    if not lote:
        raise HTTPException(404, "Lote não encontrado")
    return lote


@router.get("/{lote_id}", response_model=LoteOut)
def obter_lote(lote_id: str, db: Session = Depends(get_db)):
    return lote_out(db, _obter(db, lote_id))


@router.get("/{lote_id}/paginas", response_model=list[PaginaOut])
def paginas_do_lote(lote_id: str, db: Session = Depends(get_db)):
    return _obter(db, lote_id).paginas


@router.get("/{lote_id}/documentos", response_model=list[DocumentoOut])
def documentos_do_lote(lote_id: str, db: Session = Depends(get_db)):
    return [doc_out(d) for d in _obter(db, lote_id).documentos]


@router.post("/{lote_id}/reprocessar", response_model=LoteOut)
def reprocessar(lote_id: str, tudo: bool = False, db: Session = Depends(get_db)):
    """Recoloca na fila as páginas que falharam (ou todas, com ?tudo=true)."""
    lote = _obter(db, lote_id)
    cond = [Pagina.lote_id == lote_id]
    if not tudo:
        cond.append(Pagina.status.in_(("erro", "falhou")))
    db.execute(update(Pagina).where(*cond).values(status="pendente", tentativas=0, erro=None))
    lote.status, lote.erro = "processando", None
    db.commit()
    return lote_out(db, lote)


@router.get("/{lote_id}/paginas/{numero}/imagem")
def imagem_pagina(lote_id: str, numero: int, thumb: bool = True, db: Session = Depends(get_db)):
    p = db.scalar(select(Pagina).where(Pagina.lote_id == lote_id, Pagina.numero == numero))
    key = p and (p.thumb_key if thumb else p.imagem_key)
    if not key:
        raise HTTPException(404, "Imagem ainda não gerada")
    return Response(get_storage().get_bytes(key), media_type="image/jpeg" if thumb else "image/png",
                    headers={"Cache-Control": "private, max-age=3600"})
