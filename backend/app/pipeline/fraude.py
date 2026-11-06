"""Sinais de fraude e adulteração — veredito explicável: confiavel | atencao | alto_risco.

Cada alerta traz código, gravidade, mensagem e a EVIDÊNCIA (o que foi visto), para o revisor decidir.
Sinais simples e baratos (não substituem perícia):
  - PDF gerado ou alterado por editor de imagem/PDF (metadados producer/creator)
  - PDF modificado muito depois de criado
  - conteúdo idêntico a documento já enviado em OUTRO lote
  - páginas digitais misturadas com páginas escaneadas no mesmo documento
  - datas impossíveis: emissão/exame no futuro, validade anterior à emissão
Alto risco manda o documento para a revisão humana; atenção só sinaliza.
"""
import hashlib
import re
from datetime import datetime, timedelta

import pymupdf
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import util
from app.config import settings
from app.models import Documento, Lote, Pagina
from app.pipeline.classificar import normalizar
from app.status import StatusRevisao

EDITORES = ("photoshop", "gimp", "illustrator", "inkscape", "canva", "ilovepdf", "smallpdf", "sejda",
            "pdfescape", "pdf-xchange editor", "pdfelement", "paint.net", "affinity", "corel")


def _alerta(codigo: str, gravidade: str, mensagem: str, evidencia: str) -> dict:
    return {"codigo": codigo, "gravidade": gravidade, "mensagem": mensagem, "evidencia": evidencia[:300]}


def _data_pdf(s: str | None) -> datetime | None:
    m = re.match(r"D:(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?", s or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4) or 0), int(m.group(5) or 0))
    except ValueError:
        return None


def analisar_pdf(caminho: str) -> list[dict]:
    """Alertas do ARQUIVO enviado (valem para todos os documentos do lote)."""
    try:
        doc = pymupdf.open(caminho)
    except Exception:
        return []
    try:
        if not doc.is_pdf:
            return []
        meta = doc.metadata or {}
        alertas = []
        for campo in ("producer", "creator"):
            valor = (meta.get(campo) or "").strip()
            if any(e in valor.lower() for e in EDITORES):
                alertas.append(_alerta("pdf_editado", "media", "PDF gerado ou alterado por editor de imagem/PDF",
                                       f"{campo} = {valor}"))
                break
        criado, modificado = _data_pdf(meta.get("creationDate")), _data_pdf(meta.get("modDate"))
        if criado and modificado and modificado - criado > timedelta(days=1):
            alertas.append(_alerta("pdf_modificado", "media", "PDF modificado depois de criado",
                                   f"criado em {criado:%d/%m/%Y}, modificado em {modificado:%d/%m/%Y}"))
        return alertas
    finally:
        doc.close()


def hash_texto(texto: str | None) -> str | None:
    t = normalizar(texto or "")
    t = re.sub(r"\[[a-z]+\]", "", t)                # marcadores da anonimização não contam
    return hashlib.sha256(t.encode()).hexdigest()[:32] if len(t.strip()) >= 80 else None


def alertas_documento(db: Session, lote: Lote, doc: Documento, paginas: list[Pagina]) -> list[dict]:
    alertas = list(lote.alertas or [])
    doc.texto_hash = hash_texto(doc.texto)
    if doc.texto_hash:
        outro = db.scalar(select(Documento).where(Documento.texto_hash == doc.texto_hash,
                                                  Documento.lote_id != lote.id).limit(1))
        if outro:
            alertas.append(_alerta("repetido", "media", "conteúdo idêntico a um documento já enviado",
                                   f"lote “{outro.lote.nome}”, documento {outro.ordem + 1} ({outro.tipo})"))
    nativas = [p.numero + 1 for p in paginas if p.nativa]
    if nativas and len(nativas) < len(paginas):
        alertas.append(_alerta("paginas_misturadas", "media", "páginas digitais misturadas com páginas escaneadas",
                               f"páginas digitais: {', '.join(map(str, nativas))}"))
    hoje = util.hoje()
    if doc.validade_inicio and doc.validade_inicio > hoje + timedelta(days=1):
        alertas.append(_alerta("data_futura", "alta", "data de emissão/exame no futuro",
                               f"{doc.validade_inicio:%d/%m/%Y} (hoje é {hoje:%d/%m/%Y})"))
    if doc.validade_inicio and doc.validade_data and doc.validade_data < doc.validade_inicio:
        alertas.append(_alerta("validade_invertida", "alta", "validade termina antes da emissão",
                               f"emissão {doc.validade_inicio:%d/%m/%Y}, validade {doc.validade_data:%d/%m/%Y}"))
    return alertas


def veredito(alertas: list[dict]) -> str:
    if any(a["gravidade"] == "alta" for a in alertas):
        return "alto_risco"
    return "atencao" if alertas else "confiavel"


def aplicar(db: Session, lote: Lote, doc: Documento, paginas: list[Pagina]) -> None:
    doc.alertas = alertas_documento(db, lote, doc, paginas)
    doc.risco = veredito(doc.alertas)
    if doc.risco == "alto_risco":
        motivos = [f"possível fraude: {a['mensagem']}" for a in doc.alertas if a["gravidade"] == "alta"]
    elif doc.risco == "atencao" and settings.FRAUDE_ATENCAO_REVISAO:
        motivos = [f"atenção de fraude: {a['mensagem']}" for a in doc.alertas]
    else:
        motivos = []
    if motivos:
        doc.motivos = list(dict.fromkeys((doc.motivos or []) + motivos))
        if doc.status_revisao == StatusRevisao.AUTO_APROVADO:   # o que um revisor já decidiu continua decidido
            doc.status_revisao = StatusRevisao.PENDENTE
