"""Regressões de estado e preservação das revisões."""
import uuid
import pytest

from app.db import SessionLocal
from app.models import Documento, Lote, Pagina
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


def test_reprocessamento_nao_apaga_historico(processado, lote_pdf):
    from app import worker
    c, _ = processado
    with open(lote_pdf, "rb") as f:
        conteudo = f.read() + b"\n% versao de teste\n"
    lote = c.post("/lotes", files={"arquivo": ("versao.pdf", conteudo, "application/pdf")}).json()
    worker.rodar(uma_vez=True)
    docs = c.get(f"/lotes/{lote['id']}/documentos").json()
    doc = docs[0]
    assert c.post(f"/documentos/{doc['id']}/revisao", json={"acao": "aprovar", "usuario": "teste"}).status_code == 200
    antes = c.get(f"/documentos/{doc['id']}/revisoes").json()
    r = c.post(f"/lotes/{lote['id']}/reprocessar?tudo=true")
    assert r.status_code == 200
    assert c.post(f"/documentos/{doc['id']}/revisao", json={"acao": "aprovar"}).status_code == 409
    worker.rodar(uma_vez=True)
    versoes = c.get(f"/lotes/{lote['id']}/versoes").json()
    assert len(versoes) == 1
    assert any(r["id"] == antes[0]["id"] for r in versoes[0]["revisoes"])
    assert c.get(f"/lotes/{lote['id']}/versoes/{versoes[0]['id']}/documentos/{doc['id']}/pdf").status_code == 200
    assert c.get(f"/lotes/{lote['id']}").json()["status"] == "concluido"


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
    for chave in chaves:
        with pytest.raises(FileNotFoundError):
            get_storage().get_bytes(chave)


def test_falha_de_escrita_nao_deixa_arquivo_parcial(tmp_path, monkeypatch):
    import app.storage as storage
    origem = tmp_path / "entrada"
    origem.write_bytes(b"dados")
    st = storage.LocalStorage(str(tmp_path / "dados"))

    def falha(_src, destino):
        with open(destino, "wb") as f:
            f.write(b"incompleto")
        raise OSError("disco cheio simulado")

    monkeypatch.setattr(storage.shutil, "copyfile", falha)
    with pytest.raises(OSError):
        st.put_file("lotes/teste/original.pdf", str(origem))
    pasta = tmp_path / "dados" / "storage" / "lotes" / "teste"
    assert list(pasta.iterdir()) == []


def test_falha_ao_remontar_preserva_documentos_anteriores(processado, monkeypatch):
    import pymupdf
    from app import worker
    c, _ = processado
    pdf = pymupdf.open()
    pagina = pdf.new_page()
    pagina.insert_text((72, 72), "CONTRATO DE PRESTACAO DE SERVICOS " + "clausula " * 12)
    conteudo = pdf.tobytes()
    pdf.close()
    r = c.post("/lotes", files={"arquivo": ("falha.pdf", conteudo, "application/pdf")})
    assert r.status_code == 201
    lote = r.json()["id"]
    worker.rodar(uma_vez=True)
    anterior = c.get(f"/lotes/{lote}/documentos").json()[0]
    pdf_antes = c.get(f"/documentos/{anterior['id']}/pdf").content
    assert c.post(f"/lotes/{lote}/reprocessar?tudo=true").status_code == 200

    def disco_cheio(*_args):
        raise OSError("disco cheio simulado")

    monkeypatch.setattr(orquestrador, "gerar_arquivos", disco_cheio)
    worker.rodar(uma_vez=True)
    assert c.get(f"/lotes/{lote}").json()["status"] == "erro"
    assert c.get(f"/lotes/{lote}/documentos").json()[0]["id"] == anterior["id"]
    assert c.get(f"/documentos/{anterior['id']}/pdf").content == pdf_antes
