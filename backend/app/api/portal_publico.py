"""Portal do fornecedor — rotas PÚBLICAS (sem login): a autenticação é o token secreto na URL (F7).

Modelo de segurança:
  - no banco só o sha256 do token; comparação em tempo constante;
  - token inválido, expirado, revogado ou esgotado → SEMPRE o mesmo 404 (não revela se o link existe);
  - o fornecedor só vê lotes do próprio convite e só mensagens da lista branca de veredito_portal
    (nada de fraude, texto/OCR, CPF ou motivos internos);
  - limites de tamanho, páginas, formato (conferido pelo conteúdo) e envios por hora.
"""
import hashlib
import hmac
import os
import tempfile
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import ConviteFornecedor, Documento, Lote, Pagina
from app.pipeline import veredito_portal as vp
from app.status import StatusLote, StatusPagina
from app.tipos import nome_tipo

router = APIRouter(prefix="/portal", tags=["portal do fornecedor (público)"])

LINK_INVALIDO = "Link inválido ou expirado"
EXTENSOES_PORTAL = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}

# limitador de envios em memória por (token, ip): suficiente para um processo de API; atrás de vários
# processos o limite vale por processo (registrado em PREMISSAS_LIMITACOES.md)
_envios: dict[tuple[str, str], deque] = defaultdict(deque)
_trava = threading.Lock()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)      # SQLite devolve sem fuso


def obter_convite(db: Session, token: str) -> ConviteFornecedor:
    """Convite válido para este token, ou 404 genérico (sempre a mesma resposta)."""
    if not settings.PORTAL_ATIVO or not token or len(token) > 200:
        raise HTTPException(404, LINK_INVALIDO)
    h = hash_token(token)
    c = db.scalar(select(ConviteFornecedor).where(ConviteFornecedor.token_hash == h))
    if (c is None or not hmac.compare_digest(c.token_hash, h) or not c.ativo
            or _utc(c.expira_em) <= _agora() or c.usos >= c.usos_max):
        raise HTTPException(404, LINK_INVALIDO)
    return c


def _limitar(token_hash: str, ip: str) -> None:
    agora, janela = time.monotonic(), 3600
    with _trava:
        fila = _envios[(token_hash, ip)]
        while fila and agora - fila[0] > janela:
            fila.popleft()
        if len(fila) >= settings.PORTAL_MAX_ENVIOS_POR_HORA:
            raise HTTPException(429, "Muitos envios em pouco tempo. Tente de novo mais tarde.")
        fila.append(agora)


def documentos_do_convite(db: Session, convite: ConviteFornecedor) -> list[Documento]:
    return list(db.scalars(select(Documento).join(Lote).where(Lote.convite_id == convite.id,
                                                              Lote.status == StatusLote.CONCLUIDO)))


def _paginas_por_doc(db: Session, docs: list[Documento]) -> dict[str, list[Pagina]]:
    saida: dict[str, list[Pagina]] = defaultdict(list)
    if docs:
        for p in db.scalars(select(Pagina).where(Pagina.documento_id.in_([d.id for d in docs]))):
            saida[p.documento_id].append(p)
    return saida


def vereditos(db: Session, docs: list[Documento]) -> dict[str, dict]:
    pags = _paginas_por_doc(db, docs)
    return {d.id: vp.avaliar_documento(d, pags.get(d.id, [])) for d in docs}


def situacao(db: Session, convite: ConviteFornecedor) -> list[dict]:
    docs = documentos_do_convite(db, convite)
    return vp.consolidar(convite.exigidos, vp.mais_recentes_por_exigido(convite.exigidos, docs), vereditos(db, docs))


@router.get("/{token}")
def ver_portal(token: str, db: Session = Depends(get_db)):
    c = obter_convite(db, token)
    return {"fornecedor": c.fornecedor_nome, "expira_em": c.expira_em,
            "exigidos": [{"tipo": t, "tipo_nome": vp.nome_exigido(t),
                          "descricao": vp.TIPOS.get(t, {}).get("descricao")} for t in c.exigidos],
            "situacao": situacao(db, c), "envios_restantes": max(c.usos_max - c.usos, 0)}


@router.post("/{token}/enviar", status_code=201)
async def enviar(token: str, request: Request, arquivo: UploadFile = File(...), db: Session = Depends(get_db)):
    from app.api.lotes import criar_lote_de_arquivo     # import tardio: evita ciclo api.lotes ↔ api.portal_*

    c = obter_convite(db, token)
    _limitar(c.token_hash, request.client.host if request.client else "?")
    ext = os.path.splitext(arquivo.filename or "")[1].lower()
    if ext not in EXTENSOES_PORTAL:
        raise HTTPException(415, "Envie PDF ou imagem (PNG, JPG ou TIFF).")
    fd, tmp = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    try:
        sha, tamanho, limite = hashlib.sha256(), 0, settings.PORTAL_MAX_UPLOAD_MB * 1024 * 1024
        with open(tmp, "wb") as f:
            while bloco := await arquivo.read(1024 * 1024):
                tamanho += len(bloco)
                if tamanho > limite:
                    raise HTTPException(413, f"Arquivo maior que {settings.PORTAL_MAX_UPLOAD_MB} MB")
                sha.update(bloco)
                f.write(bloco)
        digest = sha.hexdigest()
        existente = db.scalar(select(Lote).where(Lote.hash_sha256 == digest))
        if existente:
            if existente.convite_id == c.id:          # o mesmo fornecedor reenviou o mesmo arquivo
                return {"envio_id": existente.id, "status": existente.status}
            raise HTTPException(409, "Arquivo já recebido")          # sem dizer de quem
        # conta o uso na MESMA transação do lote: se o arquivo for recusado, o uso não é gasto
        res = db.execute(update(ConviteFornecedor).where(ConviteFornecedor.id == c.id,
                                                         ConviteFornecedor.usos < ConviteFornecedor.usos_max)
                         .values(usos=ConviteFornecedor.usos + 1))
        if res.rowcount != 1:
            raise HTTPException(404, LINK_INVALIDO)
        try:
            lote = criar_lote_de_arquivo(db, f"{c.fornecedor_nome} — {arquivo.filename or 'envio'}"[:255], tmp, ext,
                                         digest, tamanho, enviado_por=f"portal:{c.id}",
                                         prioridade=settings.PORTAL_PRIORIDADE, origem="portal", convite_id=c.id,
                                         max_paginas=settings.PORTAL_MAX_PAGINAS)
        except Exception:
            db.rollback()
            raise
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return {"envio_id": lote.id, "status": "processando"}


@router.get("/{token}/envios/{envio_id}")
def ver_envio(token: str, envio_id: str, db: Session = Depends(get_db)):
    c = obter_convite(db, token)
    lote = db.get(Lote, envio_id)
    if not lote or lote.convite_id != c.id:
        raise HTTPException(404, "Envio não encontrado")
    feitas = db.scalar(select(func.count()).select_from(Pagina).where(
        Pagina.lote_id == lote.id, Pagina.status.in_((StatusPagina.OK, StatusPagina.FALHOU)))) or 0
    status = {StatusLote.CONCLUIDO: "concluido", StatusLote.ERRO: "erro"}.get(lote.status, "processando")
    corpo = {"envio_id": lote.id, "status": status,
             "progresso": round(feitas / lote.total_paginas, 3) if lote.total_paginas else 0.0,
             "documentos": [], "situacao": situacao(db, c)}
    if status == "erro":
        corpo["mensagem"] = vp.MSG_ERRO_ARQUIVO                      # nunca o erro interno
    elif status == "concluido":
        docs = list(db.scalars(select(Documento).where(Documento.lote_id == lote.id).order_by(Documento.ordem)))
        vs = vereditos(db, docs)
        corpo["documentos"] = [{"ordem": d.ordem + 1, "tipo_nome": nome_tipo(d.tipo), "veredito": vs[d.id]["veredito"],
                                "motivo": vs[d.id]["motivo"], "aviso": vs[d.id]["aviso"]} for d in docs]
    return corpo
