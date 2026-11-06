"""Verifica limpeza e retomada diante de interrupções na ingestão."""
import io
import asyncio
import os
import uuid

import pymupdf
from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile

from app import worker
from app.api import lotes
from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import Pagina
from app.status import StatusPagina


def pdf():
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), 'CONTRATO DE TESTE ' * 8)
    data = doc.tobytes()
    doc.close()
    return data


def test_interrupcao_na_gravacao_remove_temporario(monkeypatch):
    caminhos = []

    async def interromper(_arquivo, caminho):
        caminhos.append(caminho)
        with open(caminho, 'wb') as f:
            f.write(b'arquivo parcial')
        raise OSError('interrupcao simulada')

    monkeypatch.setattr(lotes, '_receber_arquivo', interromper)
    with TestClient(app, raise_server_exceptions=False) as c:
        antes = len(c.get('/lotes').json())
        resposta = c.post('/lotes', files={'arquivo': ('falha.pdf', pdf(), 'application/pdf')})
        assert resposta.status_code == 500
        assert len(c.get('/lotes').json()) == antes
    assert caminhos and not os.path.exists(caminhos[0])


def test_limite_do_arquivo_e_limpeza(monkeypatch):
    monkeypatch.setattr(settings, 'MAX_UPLOAD_MB', 1)
    with TestClient(app) as c:
        antes = len(c.get('/lotes').json())
        resposta = c.post('/lotes', files={'arquivo': ('grande.pdf', b'%PDF-' + b'x' * (1024 * 1024), 'application/pdf')})
        assert resposta.status_code == 413
        assert len(c.get('/lotes').json()) == antes


def test_arquivo_exatamente_no_limite_da_api(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'MAX_UPLOAD_MB', 1)
    arquivo = UploadFile(file=io.BytesIO(b'x' * 1024 * 1024), filename='limite.pdf')
    _, tamanho = asyncio.run(lotes._receber_arquivo(arquivo, str(tmp_path / 'upload')))
    assert tamanho == 1024 * 1024


def test_falha_de_processamento_pode_ser_reprocessada(monkeypatch):
    with TestClient(app) as c:
        # O nome não define o hash; conteúdo único evita colisão com outros testes.
        conteudo = pdf() + uuid.uuid4().hex.encode()
        resposta = c.post('/lotes', files={'arquivo': ('retomada.pdf', conteudo, 'application/pdf')})
        assert resposta.status_code == 201, resposta.text
        lote_id = resposta.json()['id']
        original = worker.processar_pagina

        def falhar(*_args):
            raise RuntimeError('falha simulada')

        monkeypatch.setattr(worker, 'processar_pagina', falhar)
        worker.rodar(uma_vez=True)
        assert c.get(f'/lotes/{lote_id}').json()['status'] == 'erro'
        with SessionLocal() as db:
            pagina = db.query(Pagina).filter_by(lote_id=lote_id).one()
            assert pagina.status == StatusPagina.FALHOU
            assert pagina.tentativas == settings.MAX_TENTATIVAS
        monkeypatch.setattr(worker, 'processar_pagina', original)
        assert c.post(f'/lotes/{lote_id}/reprocessar').status_code == 200
        worker.rodar(uma_vez=True)
        assert c.get(f'/lotes/{lote_id}').json()['status'] == 'concluido'
