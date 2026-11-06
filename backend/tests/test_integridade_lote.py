"""Regressões de estado e preservação das revisões."""
import uuid

from app.db import SessionLocal
from app.models import Documento, Lote, Pagina, Revisao
from app.pipeline import orquestrador
from app.storage import get_storage


def test_falha_de_pagina_nao_marca_lote_como_concluido(processado, monkeypatch):
    identificador = uuid.uuid4().hex
    with SessionLocal() as db:
        lote = Lote(id=identificador, nome="falha", arquivo_key="inexistente", hash_sha256=uuid.uuid4().hex,
                    mime="image/tiff", tamanho_bytes=1, total_paginas=1, status="processando")
        db.add(lote)
        db.add(Pagina(lote_id=identificador, numero=0, status="falhou"))
        db.commit()
        monkeypatch.setattr(orquestrador, "segmentar_e_montar", lambda *_: None)
        assert orquestrador.finalizar_lote_se_pronto(db, identificador)
        db.refresh(lote)
        assert lote.status == "erro"
        assert "1 página" in lote.erro


def test_reprocessamento_nao_apaga_historico(processado):
    c, lote = processado
    docs = c.get(f"/lotes/{lote['id']}/documentos").json()
    doc = docs[0]
    assert c.post(f"/documentos/{doc['id']}/revisao", json={"acao": "aprovar", "usuario": "teste"}).status_code == 200
    antes = c.get(f"/documentos/{doc['id']}/revisoes").json()
    r = c.post(f"/lotes/{lote['id']}/reprocessar?tudo=true")
    assert r.status_code == 409
    assert c.get(f"/documentos/{doc['id']}/revisoes").json() == antes


def test_juncao_remove_arquivos_do_documento_substituido(processado):
    c, lote = processado
    docs = c.get(f"/lotes/{lote['id']}/documentos").json()
    documento = next(d for d in docs if d["pagina_fim"] > d["pagina_inicio"])
    r = c.post(f"/documentos/{documento['id']}/revisao",
               json={"acao": "dividir", "usuario": "teste", "pagina_corte": documento["pagina_inicio"] + 1})
    assert r.status_code == 200
    segundo = r.json()[1]["id"]
    with SessionLocal() as db:
        d = db.get(Documento, segundo)
        chaves = [d.pdf_key, d.pdf_anon_key]
    assert all(get_storage().get_bytes(k) for k in chaves)
    assert c.post(f"/documentos/{documento['id']}/revisao",
                  json={"acao": "juntar_proximo", "usuario": "teste"}).status_code == 200
    import pytest
    for chave in chaves:
        with pytest.raises(FileNotFoundError):
            get_storage().get_bytes(chave)
