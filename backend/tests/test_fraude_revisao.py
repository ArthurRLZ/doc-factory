"""F1: documento com risco "atenção" (ex.: conteúdo repetido) vai para a fila de revisão."""
import uuid

import pytest

from app.config import settings
from app.db import SessionLocal
from app.models import Documento, Lote
from app.pipeline import fraude


def _copia_de(db, lote_terceiros):
    c, lote = lote_terceiros
    original = c.get(f"/lotes/{lote['id']}/documentos").json()[0]
    texto = db.get(Documento, original["id"]).texto
    outro = Lote(nome="reenvio.pdf", arquivo_key="x", hash_sha256=uuid.uuid4().hex, mime="application/pdf",
                 tamanho_bytes=1, total_paginas=1, status="concluido")
    db.add(outro)
    db.flush()
    copia = Documento(lote_id=outro.id, ordem=0, tipo="ASO", pagina_inicio=0, pagina_fim=0, confianca=0.99,
                      status_revisao="auto_aprovado", texto=texto)
    db.add(copia)
    db.flush()
    return outro, copia


def test_atencao_vai_para_revisao(lote_terceiros):
    with SessionLocal() as db:
        outro, copia = _copia_de(db, lote_terceiros)
        fraude.aplicar(db, outro, copia, [])
        assert copia.risco == "atencao" and copia.status_revisao == "pendente"
        assert copia.motivos and copia.motivos[0].startswith("atenção de fraude:")
        db.rollback()


def test_flag_desligada_mantem_auto_aprovado(lote_terceiros, monkeypatch):
    monkeypatch.setattr(settings, "FRAUDE_ATENCAO_REVISAO", False)
    with SessionLocal() as db:
        outro, copia = _copia_de(db, lote_terceiros)
        fraude.aplicar(db, outro, copia, [])
        assert copia.risco == "atencao" and copia.status_revisao == "auto_aprovado" and not copia.motivos
        db.rollback()


def test_documento_revisado_nao_reabre(lote_terceiros):
    with SessionLocal() as db:
        outro, copia = _copia_de(db, lote_terceiros)
        copia.status_revisao = "revisado"
        fraude.aplicar(db, outro, copia, [])
        assert copia.status_revisao == "revisado"
        db.rollback()


@pytest.mark.parametrize("limiar", [0.5])
def test_mudar_limiar_nao_reaprova_documento_em_atencao(lote_terceiros, limiar):
    c, _ = lote_terceiros
    with SessionLocal() as db:
        outro, copia = _copia_de(db, lote_terceiros)
        fraude.aplicar(db, outro, copia, [])
        db.commit()
        lote_id, doc_id = outro.id, copia.id
    try:
        assert c.put("/automacao/limiar", json={"limiar": limiar}).status_code == 200
        d = c.get(f"/documentos/{doc_id}").json()
        assert d["status_revisao"] == "pendente" and d["risco"] == "atencao"
    finally:
        c.put("/automacao/limiar", json={"limiar": 0.80})              # volta ao padrão dos testes
        c.delete(f"/lotes/{lote_id}")
